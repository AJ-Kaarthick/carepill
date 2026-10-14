from typing import Dict, Any, Optional, List, Tuple
from datetime import timedelta
from sqlalchemy.orm import Session
from app.config import settings
from app.models.models import DeviceState, Cartridge, Schedule, Medication
from app.services.clock_service import system_clock

# Documented Sound & LED mapping table (specification requirement #3)
PATTERNS = {
    "IDLE": {
        "led": "OFF",
        "buzzer": "SILENT",
        "desc": "Device ready in standby"
    },
    "PRE_DOSE_REMINDER": {
        "led": "AMBER_SOFT_PULSE",
        "buzzer": "BEEP_GENTLE_2",
        "desc": "Gentle pre-dose reminder (-10m / -5m)"
    },
    "DISPENSING": {
        "led": "BLUE_RUNNING_SWEEP",
        "buzzer": "TICK_MOTOR_OPERATION",
        "desc": "Servo rotary dispensing underway"
    },
    "DISPENSING_VERIFY": {
        "led": "BLUE_SOLID",
        "buzzer": "CLICK_SENSOR1",
        "desc": "Sensor 1 optical count verification"
    },
    "CORRECTIVE_DISPENSING": {
        "led": "AMBER_BLUE_ALTERNATE",
        "buzzer": "BEEP_SHORT_CORRECTION",
        "desc": "Corrective dispensing of missing tablets only"
    },
    "AWAITING_COLLECTION": {
        "led": "AMBER_SLOW_BREATHE",
        "buzzer": "SILENT",
        "desc": "Pills in cup, awaiting patient pickup"
    },
    "COLLECTION_REMINDER": {
        "led": "AMBER_RAPID_FLASH",
        "buzzer": "BEEP_REPEAT_3",
        "desc": "5-minute reminder: pills still waiting in cup"
    },
    "COLLECTED": {
        "led": "GREEN_PULSE_2S",
        "buzzer": "CHIME_SUCCESS_ASCENDING",
        "desc": "Sensor 2 detected cup pickup"
    },
    "ESCALATED": {
        "led": "RED_RAPID_STROBE",
        "buzzer": "SIREN_URGENT_HI_LO",
        "desc": "10-minute uncollected escalation to caregiver"
    },
    "DISPENSING_FAULT": {
        "led": "RED_SOLID",
        "buzzer": "BUZZ_FAULT_CONTINUOUS",
        "desc": "Servo jam, over-dispense, or sensor mismatch"
    },
    "SENSOR_FAULT": {
        "led": "RED_SLOW_BLINK",
        "buzzer": "BEEP_ERROR_CADENCE",
        "desc": "Sensor 1 or 2 telemetry uncertain"
    }
}

class DeviceService:
    @staticmethod
    def get_or_create_device(
        db: Session,
        device_id: str = "ESP32_PILLBOX_01",
        default_cartridge_count: int = 4
    ) -> DeviceState:
        dev = db.query(DeviceState).filter(DeviceState.device_id == device_id).first()
        if not dev:
            dev = DeviceState(
                device_id=device_id,
                cartridge_count=default_cartridge_count,
                is_online=True,
                last_heartbeat=system_clock.now(),
                firmware_version="v1.0.0-idp",
                current_led_pattern=PATTERNS["IDLE"]["led"],
                current_buzzer_pattern=PATTERNS["IDLE"]["buzzer"],
                is_simulated=True,
                updated_at=system_clock.now()
            )
            db.add(dev)
            db.flush()
            DeviceService.ensure_cartridges_for_device(db, device_id, default_cartridge_count)
            db.commit()
            db.refresh(dev)
        return dev

    @staticmethod
    def ensure_cartridges_for_device(db: Session, device_id: str, count: int):
        """
        Ensures cartridges 1..count exist for the specified device.
        Preserves existing medication mapping and inventory.
        """
        existing = db.query(Cartridge).filter(Cartridge.device_id == device_id).all()
        existing_numbers = {c.cartridge_number for c in existing}

        for num in range(1, count + 1):
            if num not in existing_numbers:
                new_cart = Cartridge(
                    device_id=device_id,
                    cartridge_number=num,
                    medication_id=None,
                    current_stock=0,
                    capacity=30,
                    low_stock_threshold=5,
                    is_configured=False,
                    calibration_offset_deg=float((num - 1) * (360.0 / count))
                )
                db.add(new_cart)
        db.flush()

    @staticmethod
    def configure_device_cartridges(
        db: Session,
        device_id: str,
        target_count: int,
        force: bool = False
    ) -> Tuple[bool, str, List[Dict[str, Any]]]:
        """
        Reconfigures patient-specific device cartridge count (4, 6, or 8).
        Validates against data loss when reducing count.
        """
        if target_count not in settings.SUPPORTED_CARTRIDGE_COUNTS:
            return False, f"Unsupported cartridge count {target_count}. Must be one of {settings.SUPPORTED_CARTRIDGE_COUNTS}.", []

        dev = DeviceService.get_or_create_device(db, device_id)
        current_count = dev.cartridge_count or 4

        # If reducing cartridge count, check for affected active medications or stock
        if target_count < current_count:
            affected_cartridges = db.query(Cartridge).filter(
                Cartridge.device_id == device_id,
                Cartridge.cartridge_number > target_count
            ).all()

            assigned_or_stocked = [
                c for c in affected_cartridges
                if c.medication_id is not None or c.current_stock > 0
            ]

            if assigned_or_stocked and not force:
                details = []
                for c in assigned_or_stocked:
                    med = db.query(Medication).filter(Medication.id == c.medication_id).first() if c.medication_id else None
                    details.append({
                        "cartridge_number": c.cartridge_number,
                        "medication_name": med.name if med else "Unassigned",
                        "current_stock": c.current_stock
                    })
                cart_nums = [str(c.cartridge_number) for c in assigned_or_stocked]
                msg = (
                    f"Cannot reduce hardware to {target_count} cartridges: Cartridge(s) {', '.join(cart_nums)} "
                    f"contain active medication assignments or remaining pill stock. "
                    f"Please review and reassign them, or confirm force reduction."
                )
                return False, msg, details

        # Apply target count
        dev.cartridge_count = target_count
        dev.updated_at = system_clock.now()

        # If reducing, delete the excess cartridge slots
        if target_count < current_count:
            db.query(Cartridge).filter(
                Cartridge.device_id == device_id,
                Cartridge.cartridge_number > target_count
            ).delete()

        # If increasing, instantiate the new cartridge slots
        if target_count > current_count:
            DeviceService.ensure_cartridges_for_device(db, device_id, target_count)

        db.commit()
        db.refresh(dev)
        return True, f"Hardware configuration updated to {target_count} circular cartridges.", []

    @staticmethod
    def set_pattern_state(db: Session, state_key: str, active_dose_id: Optional[str] = None):
        dev = DeviceService.get_or_create_device(db)
        pat = PATTERNS.get(state_key, PATTERNS["IDLE"])
        dev.current_led_pattern = pat["led"]
        dev.current_buzzer_pattern = pat["buzzer"]
        if active_dose_id is not None:
            dev.active_dose_id = active_dose_id
        dev.updated_at = system_clock.now()
        db.commit()

    @staticmethod
    def record_heartbeat(db: Session, device_id: str, firmware: str, status: str = "idle") -> DeviceState:
        dev = DeviceService.get_or_create_device(db, device_id)
        dev.is_online = True
        dev.last_heartbeat = system_clock.now()
        dev.firmware_version = firmware
        dev.updated_at = system_clock.now()
        db.commit()
        db.refresh(dev)
        return dev

    @staticmethod
    def get_offline_schedule_payload(db: Session, device_id: str = "ESP32_PILLBOX_01") -> Dict[str, Any]:
        """
        Returns compact JSON schedule payload for ESP32 to store
        in local EEPROM / LittleFS for 100% autonomous operation
        during internet outages.
        """
        dev = DeviceService.get_or_create_device(db, device_id)
        schedules = db.query(Schedule).filter(Schedule.is_active == True).all()
        items = []
        for s in schedules:
            # PRN / As-Needed Safety Guard:
            # PRN medications must never be loaded into autonomous hardware schedule memory
            if (s.time_of_day_label and s.time_of_day_label.lower() in ["as_needed", "prn"]) or \
               (s.recurrence and s.recurrence.lower() in ["prn", "as_needed"]):
                continue

            # Verify parent medication is active
            med = db.query(Medication).filter(Medication.id == s.medication_id).first()
            if not med or not med.is_active:
                continue

            cart = db.query(Cartridge).filter(
                Cartridge.device_id == device_id,
                Cartridge.medication_id == s.medication_id
            ).first()
            if cart and cart.cartridge_number <= dev.cartridge_count and not getattr(cart, "needs_reconciliation", False):
                items.append({
                    "schedule_id": s.id,
                    "cartridge_number": cart.cartridge_number,
                    "scheduled_time": s.scheduled_time_str,
                    "dose_qty": s.dose_quantity,
                    "tod_label": s.time_of_day_label
                })
        return {
            "sync_timestamp": system_clock.now().isoformat(),
            "device_id": device_id,
            "cartridge_count": dev.cartridge_count,
            "max_correction_attempts": 3,
            "pre_dose_10m_sec": 600,
            "pre_dose_5m_sec": 300,
            "reminder_delay_sec": 300,    # 5 min
            "escalation_delay_sec": 600,  # 10 min
            "schedules": items
        }

    @staticmethod
    def set_operating_mode(db: Session, device_id: str, is_simulated: bool) -> DeviceState:
        dev = DeviceService.get_or_create_device(db, device_id)
        dev.is_simulated = is_simulated
        dev.updated_at = system_clock.now()
        db.commit()
        db.refresh(dev)
        return dev

    @staticmethod
    def get_authoritative_status(db: Session, device_id: str = "ESP32_PILLBOX_01") -> Dict[str, Any]:
        """
        Truthful hardware connectivity model:
        - Demo/Simulated mode: Never claims real hardware is connected.
        - Physical mode: Reports online, stale (>60s), offline (>300s), or fault.
        """
        dev = DeviceService.get_or_create_device(db, device_id)
        now = system_clock.now()
        age = (now - dev.last_heartbeat).total_seconds() if dev.last_heartbeat else 999999.0

        if dev.is_simulated:
            return {
                "status": "demo_simulated",
                "badge_label": "Demo Mode (Simulated)",
                "badge_color": "violet",
                "is_simulated": True,
                "is_online": False,
                "telemetry_age_seconds": 0.0,
                "device_id": dev.device_id,
                "firmware_version": dev.firmware_version,
                "cartridge_count": dev.cartridge_count,
                "current_led_pattern": dev.current_led_pattern,
                "current_buzzer_pattern": dev.current_buzzer_pattern,
                "explanation": "Virtual hardware simulation active. Dispensing operations, drop counter, and tray sensor are simulated in software. No physical ESP32 required."
            }

        # Physical mode checks
        if dev.current_led_pattern in ["RED_SOLID", "RED_SLOW_BLINK"]:
            return {
                "status": "hardware_fault",
                "badge_label": "ESP32 Hardware Fault",
                "badge_color": "red",
                "is_simulated": False,
                "is_online": dev.is_online,
                "telemetry_age_seconds": round(age, 1),
                "device_id": dev.device_id,
                "firmware_version": dev.firmware_version,
                "cartridge_count": dev.cartridge_count,
                "current_led_pattern": dev.current_led_pattern,
                "current_buzzer_pattern": dev.current_buzzer_pattern,
                "explanation": "Physical ESP32 reported a sensor, motor, or dispense fault."
            }

        if age <= settings.DEVICE_OFFLINE_THRESHOLD_SECONDS and dev.is_online:
            return {
                "status": "physical_online",
                "badge_label": "ESP32 Hardware Online",
                "badge_color": "emerald",
                "is_simulated": False,
                "is_online": True,
                "telemetry_age_seconds": round(age, 1),
                "device_id": dev.device_id,
                "firmware_version": dev.firmware_version,
                "cartridge_count": dev.cartridge_count,
                "current_led_pattern": dev.current_led_pattern,
                "current_buzzer_pattern": dev.current_buzzer_pattern,
                "explanation": "Physical ESP32 connected and streaming real-time telemetry."
            }

        if age <= settings.TELEMETRY_STALE_THRESHOLD_SECONDS and dev.is_online:
            return {
                "status": "physical_stale",
                "badge_label": "ESP32 Stale Telemetry",
                "badge_color": "amber",
                "is_simulated": False,
                "is_online": True,
                "telemetry_age_seconds": round(age, 1),
                "device_id": dev.device_id,
                "firmware_version": dev.firmware_version,
                "cartridge_count": dev.cartridge_count,
                "current_led_pattern": dev.current_led_pattern,
                "current_buzzer_pattern": dev.current_buzzer_pattern,
                "explanation": f"Physical ESP32 heartbeat delayed (last seen {int(age)}s ago)."
            }

        return {
            "status": "physical_offline",
            "badge_label": "ESP32 Offline",
            "badge_color": "rose",
            "is_simulated": False,
            "is_online": False,
            "telemetry_age_seconds": round(age, 1),
            "device_id": dev.device_id,
            "firmware_version": dev.firmware_version,
            "cartridge_count": dev.cartridge_count,
            "current_led_pattern": dev.current_led_pattern,
            "current_buzzer_pattern": dev.current_buzzer_pattern,
            "explanation": f"Physical ESP32 is offline. Last heartbeat was {int(age)}s ago."
        }
