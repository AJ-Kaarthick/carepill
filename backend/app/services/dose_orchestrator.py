from typing import Tuple, Optional, Dict, Any, List
from datetime import datetime, timedelta
import uuid
from sqlalchemy.orm import Session
from app.config import settings
from app.models.models import (
    DoseOccurrence, DispensingOperation, Cartridge, Medication, Schedule,
    CaregiverAlert, InventoryTransaction, SensorReading, DeviceState
)
from app.services.clock_service import system_clock
from app.services.inventory_service import InventoryService
from app.services.notification_service import NotificationService
from app.services.device_service import DeviceService

class DoseOrchestrator:
    @staticmethod
    def generate_daily_doses_if_needed(
        db: Session,
        target_date: Optional[datetime] = None,
        device_id: str = "ESP32_PILLBOX_01"
    ) -> List[DoseOccurrence]:
        """
        Generates daily dose occurrences from active schedules if they do not exist yet.
        Respects device's configured cartridge count.
        """
        now = target_date or system_clock.now()
        dev = DeviceService.get_or_create_device(db, device_id)
        max_cartridges = dev.cartridge_count or 4

        schedules = db.query(Schedule).filter(Schedule.is_active == True).all()
        created_doses = []

        for sched in schedules:
            med = db.query(Medication).filter(Medication.id == sched.medication_id).first()
            if not med or not med.is_active:
                continue

            # PRN / As-Needed Safety Guard:
            # PRN medications are taken on demand based on clinical symptoms and must NEVER
            # be automatically scheduled into recurring rotary carousel dispensing occurrences.
            if (sched.time_of_day_label and sched.time_of_day_label.lower() in ["as_needed", "prn"]) or \
               (sched.recurrence and sched.recurrence.lower() in ["prn", "as_needed"]):
                continue

            # Check start_date and end_date bounds
            today_str = now.strftime("%Y-%m-%d")
            if sched.start_date and today_str < sched.start_date:
                continue
            if sched.end_date and today_str > sched.end_date:
                continue

            # Check recurrence and applicable days of week
            weekday = now.weekday()  # 0=Monday, 6=Sunday
            if sched.recurrence == "weekdays" and weekday >= 5:
                continue
            if sched.recurrence == "specific_days" and sched.days_of_week and sched.days_of_week != "all":
                try:
                    allowed = [int(x.strip()) for x in sched.days_of_week.split(",") if x.strip().isdigit()]
                    if weekday not in allowed:
                        continue
                except Exception:
                    pass

            cartridge = db.query(Cartridge).filter(
                Cartridge.device_id == device_id,
                Cartridge.medication_id == sched.medication_id
            ).first()

            # Ignore schedules mapped to cartridges beyond current device configuration
            if cartridge and cartridge.cartridge_number > max_cartridges:
                continue

            try:
                hour, minute = map(int, sched.scheduled_time_str.split(":"))
                sched_dt = datetime(now.year, now.month, now.day, hour, minute)
            except Exception:
                sched_dt = now

            start_of_day = datetime(now.year, now.month, now.day, 0, 0, 0)
            end_of_day = datetime(now.year, now.month, now.day, 23, 59, 59)

            existing = db.query(DoseOccurrence).filter(
                DoseOccurrence.schedule_id == sched.id,
                DoseOccurrence.scheduled_for >= start_of_day,
                DoseOccurrence.scheduled_for <= end_of_day
            ).first()

            if not existing:
                dose = DoseOccurrence(
                    schedule_id=sched.id,
                    medication_id=sched.medication_id,
                    cartridge_id=cartridge.id if cartridge else None,
                    scheduled_for=sched_dt,
                    scheduled_time_local=sched.scheduled_time_str,
                    meal_context_snapshot=sched.meal_timing,
                    requested_pills=sched.dose_quantity,
                    confirmed_pills=0,
                    status="scheduled",
                    created_at=system_clock.now()
                )
                db.add(dose)
                created_doses.append(dose)

        if created_doses:
            db.commit()
            for d in created_doses:
                db.refresh(d)
        return created_doses

    @staticmethod
    def trigger_dispense(
        db: Session,
        dose_id: str,
        auto_simulate: bool = False
    ) -> Tuple[bool, str, Optional[DoseOccurrence]]:
        """
        Initiates physical or simulated dispensing process.
        Transitions state: scheduled -> dispensing.
        In auto_simulate mode, immediately simulates Sensor 1 optical count.
        Validates against active device configuration.
        """
        dose = db.query(DoseOccurrence).filter(DoseOccurrence.id == dose_id).first()
        if not dose:
            return False, "Dose occurrence not found", None

        if dose.status in ["collected", "confirmed_taken", "dispensed", "awaiting_collection"]:
            return False, f"Dose is already in state: {dose.status}. Cannot re-dispense.", dose

        if not dose.cartridge_id:
            dose.status = "dispensing_fault"
            dose.fault_reason = "No cartridge assigned for this medication."
            db.commit()
            return False, "No cartridge assigned", dose

        cartridge = db.query(Cartridge).filter(Cartridge.id == dose.cartridge_id).first()
        if not cartridge:
            dose.status = "dispensing_fault"
            dose.fault_reason = "Cartridge not found."
            db.commit()
            return False, "Cartridge not found", dose

        # Stock Reconciliation Guard: Prevent dispensing from quarantined slots
        if getattr(cartridge, "needs_reconciliation", False):
            dose.status = "dispensing_fault"
            dose.fault_reason = f"Cartridge {cartridge.cartridge_number} is locked pending physical stock reconciliation: {cartridge.quarantine_reason}"
            db.commit()
            return False, "Cartridge requires physical stock reconciliation", dose

        if not cartridge.is_configured:
            dose.status = "dispensing_fault"
            dose.fault_reason = f"Cartridge {cartridge.cartridge_number} is not configured."
            db.commit()
            return False, "Cartridge not configured", dose

        # Validate cartridge is within active device cartridge count
        dev = DeviceService.get_or_create_device(db, cartridge.device_id)
        if cartridge.cartridge_number > dev.cartridge_count:
            dose.status = "dispensing_fault"
            dose.fault_reason = f"Cartridge {cartridge.cartridge_number} exceeds active hardware configuration ({dev.cartridge_count} slots)."
            db.commit()
            return False, "Cartridge exceeds active hardware configuration", dose

        if cartridge.current_stock < dose.requested_pills:
            dose.status = "dispensing_fault"
            dose.fault_reason = f"Insufficient stock: requested {dose.requested_pills}, but only {cartridge.current_stock} available."
            db.commit()
            time_str = system_clock.now().strftime("%H:%M")
            NotificationService.dispatch_caregiver_alert(
                db=db,
                alert_type="low_stock",
                message=f"CarePill alert: Cartridge {cartridge.cartridge_number} has insufficient pills ({cartridge.current_stock} left). Time: {time_str}.",
                dose=dose
            )
            return False, "Insufficient stock", dose

        cmd_id = str(uuid.uuid4())
        dose.command_id = cmd_id
        dose.dispense_initiated_at = system_clock.now()
        dose.status = "dispensing"
        db.commit()
        DeviceService.set_pattern_state(db, "DISPENSING", active_dose_id=dose.id)

        if auto_simulate:
            # Auto-simulate Sensor 1 drop pulses for the full requested dose
            return DoseOrchestrator.process_sensor1_drop_result(
                db=db,
                dose_id=dose.id,
                detected_pills_in_this_step=dose.requested_pills,
                sensor_status="ok",
                raw_telemetry="simulated_auto_drop"
            )

        return True, "Dispensing operation initiated", dose

    @staticmethod
    def process_sensor1_drop_result(
        db: Session,
        dose_id: str,
        detected_pills_in_this_step: int,
        sensor_status: str = "ok",
        raw_telemetry: Optional[str] = None
    ) -> Tuple[bool, str, DoseOccurrence]:
        """
        Processes feedback from Sensor 1 (Optical / Breakbeam pill counter).
        Implements correction logic, over-dispense safety halt, and auditable inventory decrement.
        """
        dose = db.query(DoseOccurrence).filter(DoseOccurrence.id == dose_id).first()
        if not dose:
            raise ValueError(f"Dose {dose_id} not found")

        reading = SensorReading(
            sensor_type="sensor1_drop_counter",
            dose_occurrence_id=dose.id,
            value=float(detected_pills_in_this_step),
            details=f"Status: {sensor_status} | Telemetry: {raw_telemetry or 'N/A'}",
            timestamp=system_clock.now()
        )
        db.add(reading)

        # Check for sensor uncertainty / fault
        if sensor_status in ["uncertain", "fault"]:
            dose.status = "sensor_fault"
            dose.fault_reason = f"Sensor 1 telemetry uncertain/faulty: {raw_telemetry}"
            DeviceService.set_pattern_state(db, "SENSOR_FAULT", active_dose_id=dose.id)
            time_str = system_clock.now().strftime("%H:%M")
            NotificationService.dispatch_caregiver_alert(
                db=db,
                alert_type="sensor_fault",
                message=f"CarePill alert: Sensor 1 optical fault occurred. Please check on patient. Time: {time_str}.",
                dose=dose
            )
            db.commit()
            db.refresh(dose)
            return False, "Sensor 1 reported uncertain count or fault. Mechanism halted.", dose

        # Update confirmed count
        current_attempt = dose.correction_attempts_used + 1
        dose.correction_attempts_used = current_attempt
        new_total_confirmed = dose.confirmed_pills + detected_pills_in_this_step
        dose.confirmed_pills = new_total_confirmed

        # Record this specific dispensing operation attempt
        operation = DispensingOperation(
            dose_occurrence_id=dose.id,
            attempt_number=current_attempt,
            target_pills_this_attempt=max(1, dose.requested_pills - (dose.confirmed_pills - detected_pills_in_this_step)),
            sensor1_detected_count=detected_pills_in_this_step,
            status="success" if new_total_confirmed == dose.requested_pills else (
                "over_dispense" if new_total_confirmed > dose.requested_pills else "under_dispense"
            ),
            raw_telemetry=raw_telemetry,
            created_at=system_clock.now()
        )
        db.add(operation)

        # 1. OVER-DISPENSE SAFETY: More pills than prescribed
        if new_total_confirmed > dose.requested_pills:
            dose.status = "dispensing_fault"
            dose.fault_reason = (
                f"Over-dispense safety halt: Prescribed {dose.requested_pills}, but Sensor 1 detected "
                f"{new_total_confirmed} pills. Mechanism stopped. Do not swallow."
            )
            InventoryService.decrement_stock_for_dose(db, dose, new_total_confirmed, sensor_id="sensor1_drop_counter")
            DeviceService.set_pattern_state(db, "DISPENSING_FAULT", active_dose_id=dose.id)
            time_str = system_clock.now().strftime("%H:%M")
            NotificationService.dispatch_caregiver_alert(
                db=db,
                alert_type="dispensing_fault",
                message=f"CarePill alert: Over-dispense detected ({new_total_confirmed}/{dose.requested_pills} pills). Mechanism halted. Time: {time_str}.",
                dose=dose
            )
            db.commit()
            db.refresh(dose)
            return False, "Over-dispense detected! Mechanism halted safely.", dose

        # 2. EXACT DOSE CONFIRMED
        if new_total_confirmed == dose.requested_pills:
            dose.status = "awaiting_collection"
            dose.dispensed_at = system_clock.now()
            InventoryService.decrement_stock_for_dose(db, dose, new_total_confirmed, sensor_id="sensor1_drop_counter")
            DeviceService.set_pattern_state(db, "AWAITING_COLLECTION", active_dose_id=dose.id)
            db.commit()
            db.refresh(dose)
            return True, f"Dispensing successful. {new_total_confirmed}/{dose.requested_pills} pills confirmed by Sensor 1. Awaiting pickup.", dose

        # 3. UNDER-DISPENSE: Fewer pills than prescribed
        missing = dose.requested_pills - new_total_confirmed
        if current_attempt < settings.MAX_CORRECTION_ATTEMPTS:
            dose.status = "corrective_dispensing"
            DeviceService.set_pattern_state(db, "CORRECTIVE_DISPENSING", active_dose_id=dose.id)
            db.commit()
            db.refresh(dose)
            return True, f"Under-dispensed ({new_total_confirmed}/{dose.requested_pills}). Requesting corrective dispensing for {missing} missing tablet(s) (Attempt {current_attempt}/{settings.MAX_CORRECTION_ATTEMPTS}).", dose
        else:
            dose.status = "dispensing_fault"
            dose.fault_reason = (
                f"Under-dispense limit reached: Confirmed {new_total_confirmed} of {dose.requested_pills} pills after "
                f"{current_attempt} attempts. Mechanism stopped for patient safety."
            )
            if new_total_confirmed > 0:
                InventoryService.decrement_stock_for_dose(db, dose, new_total_confirmed, sensor_id="sensor1_drop_counter")
            DeviceService.set_pattern_state(db, "DISPENSING_FAULT", active_dose_id=dose.id)
            time_str = system_clock.now().strftime("%H:%M")
            NotificationService.dispatch_caregiver_alert(
                db=db,
                alert_type="dispensing_fault",
                message=f"CarePill alert: Dispensing incomplete after {current_attempt} attempts ({new_total_confirmed}/{dose.requested_pills} pills). Time: {time_str}.",
                dose=dose
            )
            db.commit()
            db.refresh(dose)
            return False, f"Maximum correction attempts reached ({current_attempt}). Dispensing halted with fault.", dose

    @staticmethod
    def process_sensor2_pickup_event(
        db: Session,
        dose_id: Optional[str] = None,
        is_collected: bool = True,
        raw_val: Optional[float] = None
    ) -> Tuple[bool, str, Optional[DoseOccurrence]]:
        """
        Processes feedback from Sensor 2 (Pickup Area / Pill Cup Detection).
        When collected: cancels pending pickup reminders and caregiver escalation.
        """
        if not dose_id:
            active_dose = db.query(DoseOccurrence).filter(
                DoseOccurrence.status.in_(["awaiting_collection", "collection_reminder", "escalated"])
            ).order_by(DoseOccurrence.dispensed_at.desc()).first()
        else:
            active_dose = db.query(DoseOccurrence).filter(DoseOccurrence.id == dose_id).first()

        if not active_dose:
            return False, "No active dose currently awaiting collection.", None

        reading = SensorReading(
            sensor_type="sensor2_pickup",
            dose_occurrence_id=active_dose.id,
            value=1.0 if is_collected else 0.0,
            details=f"Pickup detected: {is_collected} | Raw: {raw_val or 'N/A'}",
            timestamp=system_clock.now()
        )
        db.add(reading)

        if is_collected:
            active_dose.status = "collected"
            active_dose.collected_at = system_clock.now()
            DeviceService.set_pattern_state(db, "COLLECTED", active_dose_id=None)
            db.commit()
            db.refresh(active_dose)
            return True, f"Medicine pickup confirmed by Sensor 2 at {active_dose.collected_at.strftime('%H:%M:%S')}.", active_dose

        db.commit()
        return True, "Sensor 2 detected cup still present / not collected.", active_dose

    @staticmethod
    def cancel_dispense(db: Session, dose_id: str) -> Tuple[bool, str, Optional[DoseOccurrence]]:
        """
        Safely cancels/recovers an in-progress or faulted dispense operation.
        If 0 pills have been confirmed by Sensor 1, resets back to 'scheduled'.
        If partial pills were already confirmed, preserves them and moves to 'awaiting_collection'.
        """
        dose = db.query(DoseOccurrence).filter(DoseOccurrence.id == dose_id).first()
        if not dose:
            return False, "Dose not found", None

        if dose.status in ["collected", "confirmed_taken"]:
            return False, f"Dose has already completed ({dose.status}). Cannot cancel.", dose

        if dose.confirmed_pills == 0:
            dose.status = "scheduled"
            dose.command_id = None
            dose.dispense_initiated_at = None
            dose.fault_reason = None
            DeviceService.set_pattern_state(db, "IDLE", active_dose_id=None)
            db.commit()
            db.refresh(dose)
            return True, "Dispense operation cancelled safely. Dose reset to scheduled.", dose
        else:
            dose.status = "awaiting_collection"
            DeviceService.set_pattern_state(db, "AWAITING_COLLECTION", active_dose_id=dose.id)
            db.commit()
            db.refresh(dose)
            return True, f"Partial pills ({dose.confirmed_pills}) were confirmed by Sensor 1 and are in the tray. Status moved to awaiting collection.", dose

    @staticmethod
    def record_manual_take_confirmation(
        db: Session,
        dose_id: str,
        confirmed_by: str = "Patient",
        notes: Optional[str] = None
    ) -> Tuple[bool, str, Optional[DoseOccurrence]]:
        """
        Allows patient or caregiver to explicitly confirm medication ingestion.
        Transitions state to 'confirmed_taken' with auditable timestamp and actor.
        """
        dose = db.query(DoseOccurrence).filter(DoseOccurrence.id == dose_id).first()
        if not dose:
            return False, "Dose not found", None

        dose.status = "confirmed_taken"
        dose.manual_confirmed_at = system_clock.now()
        if not dose.collected_at:
            dose.collected_at = system_clock.now()
        dose.manual_confirmation_by = confirmed_by
        dose.manual_confirmation_notes = notes or "Manually confirmed taken in application."
        DeviceService.set_pattern_state(db, "IDLE", active_dose_id=None)
        db.commit()
        db.refresh(dose)
        return True, f"Medication confirmed taken by {confirmed_by}.", dose

    @staticmethod
    def evaluate_timeouts_and_escalations(db: Session) -> Dict[str, Any]:
        """
        Evaluates all reminder, timing, and timeout states based on the system clock:
        1. Pre-dose reminder 1: 10 minutes before scheduled dose (-10m)
        2. Pre-dose reminder 2: 5 minutes before scheduled dose (-5m)
        3. Physical dispense timeout: 30s unacknowledged hardware dispense (+30s)
        4. Post-dispense collection reminder: 5 minutes uncollected (+5m)
        5. Post-dispense caregiver escalation: 10 minutes uncollected (+10m)
        """
        now = system_clock.now()
        pre_dose_reminders_triggered = 0
        reminders_triggered = 0
        escalations_triggered = 0
        dispense_timeouts_triggered = 0

        # A. PRE-DOSE REMINDERS (-10m and -5m before scheduled_for)
        upcoming_doses = db.query(DoseOccurrence).filter(
            DoseOccurrence.status.in_(["scheduled", "pre_dose_reminder"])
        ).all()

        for dose in upcoming_doses:
            minutes_until = (dose.scheduled_for - now).total_seconds() / 60.0

            # 5 minutes before scheduled dose (-5m)
            if 0 <= minutes_until <= settings.DEFAULT_PRE_DOSE_5M_MINUTES and not dose.pre_dose_5m_sent_at:
                dose.status = "pre_dose_reminder"
                dose.pre_dose_5m_sent_at = now
                DeviceService.set_pattern_state(db, "PRE_DOSE_REMINDER", active_dose_id=dose.id)
                pre_dose_reminders_triggered += 1

            # 10 minutes before scheduled dose (-10m)
            elif settings.DEFAULT_PRE_DOSE_5M_MINUTES < minutes_until <= settings.DEFAULT_PRE_DOSE_10M_MINUTES and not dose.pre_dose_10m_sent_at:
                dose.status = "pre_dose_reminder"
                dose.pre_dose_10m_sent_at = now
                DeviceService.set_pattern_state(db, "PRE_DOSE_REMINDER", active_dose_id=dose.id)
                pre_dose_reminders_triggered += 1

        # B. PHYSICAL DISPENSE TIMEOUT (30s without physical hardware acknowledgment)
        dispensing_doses = db.query(DoseOccurrence).filter(
            DoseOccurrence.status == "dispensing"
        ).all()

        for dose in dispensing_doses:
            if not dose.dispense_initiated_at:
                continue
            elapsed_sec = (now - dose.dispense_initiated_at).total_seconds()
            if elapsed_sec >= settings.DISPENSE_TIMEOUT_SECONDS:
                dose.status = "dispensing_fault"
                dose.fault_reason = f"Dispensing timed out after {settings.DISPENSE_TIMEOUT_SECONDS}s without physical Sensor 1 confirmation."
                DeviceService.set_pattern_state(db, "DISPENSING_FAULT", active_dose_id=dose.id)
                time_str = dose.dispense_initiated_at.strftime("%H:%M")
                NotificationService.dispatch_caregiver_alert(
                    db=db,
                    alert_type="dispensing_fault",
                    message=f"CarePill alert: Hardware dispensing timed out ({settings.DISPENSE_TIMEOUT_SECONDS}s elapsed without drop confirmation). Please check dispenser.",
                    dose=dose
                )
                dispense_timeouts_triggered += 1

        # C. POST-DISPENSE UNCOLLECTED TIMERS (+5m and +10m after dispensed_at)
        active_doses = db.query(DoseOccurrence).filter(
            DoseOccurrence.status.in_(["awaiting_collection", "collection_reminder"])
        ).all()

        for dose in active_doses:
            if not dose.dispensed_at:
                continue

            elapsed_minutes = (now - dose.dispensed_at).total_seconds() / 60.0

            # 10 minutes -> Caregiver Escalation (+10m)
            if elapsed_minutes >= settings.DEFAULT_ESCALATION_MINUTES and dose.status != "escalated":
                dose.status = "escalated"
                dose.escalated_at = now
                DeviceService.set_pattern_state(db, "ESCALATED", active_dose_id=dose.id)
                time_str = dose.dispensed_at.strftime("%H:%M")
                NotificationService.dispatch_caregiver_alert(
                    db=db,
                    alert_type="uncollected_dose",
                    message=f"CarePill alert: A scheduled medication has not been collected. Please check on the patient. Time: {time_str}.",
                    dose=dose
                )
                escalations_triggered += 1

            # 5 minutes -> Collection Reminder (+5m)
            elif elapsed_minutes >= settings.DEFAULT_REMINDER_MINUTES and dose.status == "awaiting_collection":
                dose.status = "collection_reminder"
                dose.pickup_reminder_sent_at = now
                DeviceService.set_pattern_state(db, "COLLECTION_REMINDER", active_dose_id=dose.id)
                reminders_triggered += 1

        db.commit()
        return {
            "pre_dose_reminders_triggered": pre_dose_reminders_triggered,
            "dispense_timeouts_triggered": dispense_timeouts_triggered,
            "reminders_triggered": reminders_triggered,
            "escalations_triggered": escalations_triggered,
            "evaluated_at": now.isoformat()
        }
