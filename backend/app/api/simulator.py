from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import Dict, Any, Optional
from datetime import timedelta
from app.database import get_db
from app.models.models import DoseOccurrence, Cartridge, DeviceState
from app.schemas.schemas import SimulationStepRequest
from app.services.dose_orchestrator import DoseOrchestrator
from app.services.clock_service import system_clock
from app.services.device_service import DeviceService
from app.services.inventory_service import InventoryService
from app.services.notification_service import NotificationService

router = APIRouter(prefix="/simulator", tags=["Hardware Simulation Engine"])

@router.get("/state")
def get_simulator_state(db: Session = Depends(get_db)):
    DoseOrchestrator.evaluate_timeouts_and_escalations(db)
    dev = DeviceService.get_or_create_device(db)
    now = system_clock.now()

    active_dose = db.query(DoseOccurrence).filter(
        DoseOccurrence.status.in_(["pre_dose_reminder", "dispensing", "corrective_dispensing", "awaiting_collection", "collection_reminder", "escalated"])
    ).first()

    return {
        "virtual_clock_now": now.isoformat(),
        "device_online": dev.is_online,
        "cartridge_count": dev.cartridge_count,
        "current_led_pattern": dev.current_led_pattern,
        "current_buzzer_pattern": dev.current_buzzer_pattern,
        "active_dose_id": active_dose.id if active_dose else None,
        "active_dose_status": active_dose.status if active_dose else None,
        "active_dose_requested": active_dose.requested_pills if active_dose else None,
        "active_dose_confirmed": active_dose.confirmed_pills if active_dose else None,
        "dispensed_at": active_dose.dispensed_at.isoformat() if active_dose and active_dose.dispensed_at else None,
        "minutes_elapsed_since_dispense": (
            round((now - active_dose.dispensed_at).total_seconds() / 60.0, 1)
            if active_dose and active_dose.dispensed_at else 0.0
        )
    }

@router.post("/action")
def execute_simulator_action(req: SimulationStepRequest, db: Session = Depends(get_db)):
    scenario = req.scenario

    # 1. TRIGGER DOSE DUE
    if scenario == "scheduled_due":
        DoseOrchestrator.generate_daily_doses_if_needed(db)
        dose = db.query(DoseOccurrence).filter(DoseOccurrence.status == "scheduled").first()
        if not dose:
            return {"status": "info", "message": "No scheduled doses available to trigger."}
        success, msg, d = DoseOrchestrator.trigger_dispense(db, dose.id)
        return {"status": "success", "message": f"Dose {dose.id} is now due and dispensing started.", "dose_id": dose.id}

    # 2. PERFECT DISPENSE (2 tablets requested -> 2 dispensed)
    elif scenario == "dispense_perfect_2":
        dose = db.query(DoseOccurrence).filter(DoseOccurrence.status.in_(["scheduled", "dispensing"])).first()
        if not dose:
            return {"status": "error", "message": "No scheduled or dispensing dose found."}
        if dose.status == "scheduled":
            DoseOrchestrator.trigger_dispense(db, dose.id)

        # Sensor 1 reports full count
        success, msg, d = DoseOrchestrator.process_sensor1_drop_result(
            db=db,
            dose_id=dose.id,
            detected_pills_in_this_step=dose.requested_pills,
            sensor_status="ok",
            raw_telemetry="Breakbeam Sensor 1: 2 clean optical drop pulses"
        )
        return {"status": "success", "message": msg, "dose_status": d.status}

    # 3. UNDER-DISPENSE (Delivers 1 pill when 2 requested)
    elif scenario == "dispense_under_1":
        dose = db.query(DoseOccurrence).filter(DoseOccurrence.status.in_(["scheduled", "dispensing", "corrective_dispensing"])).first()
        if not dose:
            return {"status": "error", "message": "No active dose available."}
        if dose.status == "scheduled":
            DoseOrchestrator.trigger_dispense(db, dose.id)

        success, msg, d = DoseOrchestrator.process_sensor1_drop_result(
            db=db,
            dose_id=dose.id,
            detected_pills_in_this_step=1,
            sensor_status="ok",
            raw_telemetry="Breakbeam Sensor 1: 1 pulse detected (1 pill still missing)"
        )
        return {"status": "success", "message": msg, "dose_status": d.status}

    # 4. CORRECTIVE STEP (Delivers the missing pill)
    elif scenario == "dispense_corrective_step":
        dose = db.query(DoseOccurrence).filter(DoseOccurrence.status == "corrective_dispensing").first()
        if not dose:
            return {"status": "error", "message": "No dose is currently awaiting corrective dispensing."}

        missing = dose.requested_pills - dose.confirmed_pills
        success, msg, d = DoseOrchestrator.process_sensor1_drop_result(
            db=db,
            dose_id=dose.id,
            detected_pills_in_this_step=missing,
            sensor_status="ok",
            raw_telemetry=f"Breakbeam Sensor 1: Corrective rotary nudge delivered final {missing} pill(s)"
        )
        return {"status": "success", "message": msg, "dose_status": d.status}

    # 5. OVER-DISPENSE FAULT
    elif scenario == "dispense_over_fault":
        dose = db.query(DoseOccurrence).filter(DoseOccurrence.status.in_(["scheduled", "dispensing"])).first()
        if not dose:
            return {"status": "error", "message": "No dose available."}
        if dose.status == "scheduled":
            DoseOrchestrator.trigger_dispense(db, dose.id)

        excess_count = dose.requested_pills + 2
        success, msg, d = DoseOrchestrator.process_sensor1_drop_result(
            db=db,
            dose_id=dose.id,
            detected_pills_in_this_step=excess_count,
            sensor_status="ok",
            raw_telemetry=f"Breakbeam Sensor 1: Rapid multi-drop {excess_count} pills detected!"
        )
        return {"status": "warning", "message": msg, "dose_status": d.status}

    # 6. SENSOR JAM / UNCERTAIN FAULT
    elif scenario == "sensor_fault":
        dose = db.query(DoseOccurrence).filter(DoseOccurrence.status.in_(["scheduled", "dispensing"])).first()
        if not dose:
            return {"status": "error", "message": "No dose available."}
        if dose.status == "scheduled":
            DoseOrchestrator.trigger_dispense(db, dose.id)

        success, msg, d = DoseOrchestrator.process_sensor1_drop_result(
            db=db,
            dose_id=dose.id,
            detected_pills_in_this_step=0,
            sensor_status="uncertain",
            raw_telemetry="Breakbeam Sensor 1: Beam blocked continuously > 3000ms (potential chute jam)"
        )
        return {"status": "warning", "message": msg, "dose_status": d.status}

    # 7. PICKUP DETECTED (Sensor 2)
    elif scenario == "pickup_detected":
        success, msg, d = DoseOrchestrator.process_sensor2_pickup_event(db, is_collected=True)
        return {"status": "success", "message": msg, "dose_status": d.status if d else None}

    # 8. FAST FORWARD 5 MINUTES (Trigger collection reminder)
    elif scenario == "fast_forward_5m":
        system_clock.advance_minutes(5)
        res = DoseOrchestrator.evaluate_timeouts_and_escalations(db)
        return {
            "status": "success",
            "message": f"Virtual clock advanced by 5 minutes. Evaluated: {res['reminders_triggered']} reminder(s) triggered.",
            "new_time": system_clock.now().isoformat()
        }

    # 9. FAST FORWARD 10 MINUTES (Trigger caregiver escalation)
    elif scenario == "fast_forward_10m":
        system_clock.advance_minutes(10)
        res = DoseOrchestrator.evaluate_timeouts_and_escalations(db)
        return {
            "status": "success",
            "message": f"Virtual clock advanced by 10 minutes. Evaluated: {res['escalations_triggered']} caregiver escalation(s) triggered.",
            "new_time": system_clock.now().isoformat()
        }

    # 10. FAST FORWARD PRE-DOSE 10M (-10m)
    elif scenario == "fast_forward_pre_dose_10m":
        DoseOrchestrator.generate_daily_doses_if_needed(db)
        upcoming = db.query(DoseOccurrence).filter(DoseOccurrence.status == "scheduled").order_by(DoseOccurrence.scheduled_for.asc()).first()
        if upcoming:
            target_time = upcoming.scheduled_for - timedelta(minutes=9, seconds=30)
            if target_time > system_clock.now():
                delta_minutes = (target_time - system_clock.now()).total_seconds() / 60.0
                system_clock.advance_minutes(delta_minutes)
        else:
            system_clock.advance_minutes(10)
        res = DoseOrchestrator.evaluate_timeouts_and_escalations(db)
        return {
            "status": "success",
            "message": f"Virtual clock aligned to -10m pre-dose reminder window. Triggered: {res['pre_dose_reminders_triggered']} pre-dose reminder(s).",
            "new_time": system_clock.now().isoformat()
        }

    # 11. FAST FORWARD PRE-DOSE 5M (-5m)
    elif scenario == "fast_forward_pre_dose_5m":
        DoseOrchestrator.generate_daily_doses_if_needed(db)
        upcoming = db.query(DoseOccurrence).filter(DoseOccurrence.status.in_(["scheduled", "pre_dose_reminder"])).order_by(DoseOccurrence.scheduled_for.asc()).first()
        if upcoming:
            target_time = upcoming.scheduled_for - timedelta(minutes=4, seconds=30)
            if target_time > system_clock.now():
                delta_minutes = (target_time - system_clock.now()).total_seconds() / 60.0
                system_clock.advance_minutes(delta_minutes)
        else:
            system_clock.advance_minutes(5)
        res = DoseOrchestrator.evaluate_timeouts_and_escalations(db)
        return {
            "status": "success",
            "message": f"Virtual clock aligned to -5m pre-dose reminder window. Triggered: {res['pre_dose_reminders_triggered']} pre-dose reminder(s).",
            "new_time": system_clock.now().isoformat()
        }

    # 12. TEST NOTIFICATION
    elif scenario == "test_notification":
        alert = NotificationService.dispatch_caregiver_alert(
            db=db,
            alert_type="simulator_test",
            message="CarePill alert: Simulated hardware verification check. Dispenser operational.",
            channel_override="simulated"
        )
        return {
            "status": "success",
            "message": f"Simulated caregiver notification dispatched (ID: {alert.id}).",
            "alert_id": alert.id
        }

    # 13. TOGGLE WI-FI OFFLINE / ONLINE
    elif scenario == "toggle_offline":
        dev = DeviceService.get_or_create_device(db)
        dev.is_online = not dev.is_online
        db.commit()
        return {"status": "success", "message": f"Device is now {'ONLINE' if dev.is_online else 'OFFLINE (Simulated Outage)'}."}

    # 14. RESET CLOCK & REGENERATE
    elif scenario == "reset":
        system_clock.reset()
        DeviceService.set_pattern_state(db, "IDLE")
        return {"status": "success", "message": "Virtual clock reset to current time."}

    raise HTTPException(status_code=400, detail=f"Unknown scenario '{scenario}'")
