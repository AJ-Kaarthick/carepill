from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import datetime, timedelta
from app.database import get_db
from app.models.models import DoseOccurrence, Medication, Cartridge, DispensingOperation
from app.schemas.schemas import DoseOccurrenceResponse, ManualConfirmRequest
from app.services.dose_orchestrator import DoseOrchestrator
from app.services.clock_service import system_clock

router = APIRouter(prefix="/doses", tags=["Doses & Daily Timeline"])

def serialize_dose(d: DoseOccurrence, db: Session) -> DoseOccurrenceResponse:
    med = db.query(Medication).filter(Medication.id == d.medication_id).first()
    cart = db.query(Cartridge).filter(Cartridge.id == d.cartridge_id).first() if d.cartridge_id else None
    ops = db.query(DispensingOperation).filter(DispensingOperation.dose_occurrence_id == d.id).order_by(DispensingOperation.attempt_number.asc()).all()

    now = system_clock.now()
    minutes_until = (d.scheduled_for - now).total_seconds() / 60.0

    # Active in-progress states
    is_in_progress = d.status in ["dispensing", "corrective_dispensing", "awaiting_collection", "collection_reminder", "escalated"]

    # Eligible if in-progress or within -10m pre-dose window or overdue
    is_due = is_in_progress or (d.status in ["scheduled", "pre_dose_reminder"] and minutes_until <= 10.0)

    # Actionable dispense button eligibility
    can_dispense = (d.status in ["scheduled", "pre_dose_reminder"] and minutes_until <= 10.0)

    seconds_until_due = max(0, int((d.scheduled_for - now).total_seconds())) if not is_due else 0

    return DoseOccurrenceResponse(
        id=d.id,
        schedule_id=d.schedule_id,
        medication_id=d.medication_id,
        cartridge_id=d.cartridge_id,
        medication_name=med.name if med else "Unknown",
        medication_strength=med.strength if med else None,
        cartridge_number=cart.cartridge_number if cart else None,
        scheduled_for=d.scheduled_for,
        scheduled_time_local=d.scheduled_time_local,
        meal_context_snapshot=d.meal_context_snapshot,
        requested_pills=d.requested_pills,
        confirmed_pills=d.confirmed_pills,
        status=d.status,
        is_due=is_due,
        can_dispense=can_dispense,
        seconds_until_due=seconds_until_due,
        command_id=d.command_id,
        dispense_initiated_at=d.dispense_initiated_at,
        manual_confirmed_at=d.manual_confirmed_at,
        dispensed_at=d.dispensed_at,
        collected_at=d.collected_at,
        pickup_reminder_sent_at=d.pickup_reminder_sent_at,
        escalated_at=d.escalated_at,
        manual_confirmation_by=d.manual_confirmation_by,
        manual_confirmation_notes=d.manual_confirmation_notes,
        fault_reason=d.fault_reason,
        correction_attempts_used=d.correction_attempts_used,
        created_at=d.created_at,
        operations=ops
    )

@router.get("/today", response_model=List[DoseOccurrenceResponse])
def get_today_doses(db: Session = Depends(get_db)):
    DoseOrchestrator.evaluate_timeouts_and_escalations(db)
    DoseOrchestrator.generate_daily_doses_if_needed(db)

    now = system_clock.now()
    start_of_day = datetime(now.year, now.month, now.day, 0, 0, 0)
    end_of_day = datetime(now.year, now.month, now.day, 23, 59, 59)

    doses = db.query(DoseOccurrence).filter(
        DoseOccurrence.scheduled_for >= start_of_day,
        DoseOccurrence.scheduled_for <= end_of_day
    ).order_by(DoseOccurrence.scheduled_for.asc()).all()

    return [serialize_dose(d, db) for d in doses]

@router.get("/current", response_model=Optional[DoseOccurrenceResponse])
def get_current_or_next_dose(db: Session = Depends(get_db)):
    DoseOrchestrator.evaluate_timeouts_and_escalations(db)
    DoseOrchestrator.generate_daily_doses_if_needed(db)

    now = system_clock.now()

    # 1. Any active dose currently in progress (dispensing, awaiting_collection, collection_reminder, escalated)
    active = db.query(DoseOccurrence).filter(
        DoseOccurrence.status.in_(["dispensing", "corrective_dispensing", "awaiting_collection", "collection_reminder", "escalated"])
    ).order_by(DoseOccurrence.scheduled_for.asc()).first()
    if active:
        return serialize_dose(active, db)

    # 2. Due or pre-dose window dose (scheduled_for <= now + 10m)
    due_window = now + timedelta(minutes=10)
    due_dose = db.query(DoseOccurrence).filter(
        DoseOccurrence.status.in_(["scheduled", "pre_dose_reminder"]),
        DoseOccurrence.scheduled_for <= due_window
    ).order_by(DoseOccurrence.scheduled_for.asc()).first()
    if due_dose:
        return serialize_dose(due_dose, db)

    # 3. Next upcoming scheduled dose today (is_due will be False)
    next_sched = db.query(DoseOccurrence).filter(
        DoseOccurrence.status == "scheduled",
        DoseOccurrence.scheduled_for > due_window
    ).order_by(DoseOccurrence.scheduled_for.asc()).first()
    if next_sched:
        return serialize_dose(next_sched, db)

    return None

@router.post("/{dose_id}/dispense")
def trigger_dose_dispense(
    dose_id: str,
    auto_simulate: bool = False,
    db: Session = Depends(get_db)
):
    success, msg, dose = DoseOrchestrator.trigger_dispense(db, dose_id, auto_simulate=auto_simulate)
    if not success:
        raise HTTPException(status_code=400, detail=msg)
    return {"status": "success", "message": msg, "dose": serialize_dose(dose, db)}

@router.post("/{dose_id}/simulate-dispense")
def simulate_dose_dispense(dose_id: str, db: Session = Depends(get_db)):
    """
    Demo/Simulated mode: triggers dispense and automatically simulates Sensor 1 drop pulses
    and idempotent inventory decrement, transitioning cleanly to awaiting_collection.
    """
    success, msg, dose = DoseOrchestrator.trigger_dispense(db, dose_id, auto_simulate=True)
    if not success:
        raise HTTPException(status_code=400, detail=msg)
    return {"status": "success", "message": msg, "dose": serialize_dose(dose, db)}

@router.post("/{dose_id}/cancel-dispense")
def cancel_dose_dispense(dose_id: str, db: Session = Depends(get_db)):
    """
    Recovers from a stuck or faulted dispense. If 0 pills confirmed, resets to scheduled.
    """
    success, msg, dose = DoseOrchestrator.cancel_dispense(db, dose_id)
    if not success:
        raise HTTPException(status_code=400, detail=msg)
    return {"status": "success", "message": msg, "dose": serialize_dose(dose, db)}

@router.post("/{dose_id}/sensor1-drop")
def record_sensor1_drop(
    dose_id: str,
    detected_count: int = 1,
    sensor_status: str = "ok",
    telemetry: Optional[str] = None,
    db: Session = Depends(get_db)
):
    try:
        success, msg, dose = DoseOrchestrator.process_sensor1_drop_result(
            db=db,
            dose_id=dose_id,
            detected_pills_in_this_step=detected_count,
            sensor_status=sensor_status,
            raw_telemetry=telemetry
        )
        return {
            "success": success,
            "message": msg,
            "dose": serialize_dose(dose, db)
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.post("/{dose_id}/pickup")
def record_pickup_event(
    dose_id: str,
    is_collected: bool = True,
    db: Session = Depends(get_db)
):
    success, msg, dose = DoseOrchestrator.process_sensor2_pickup_event(
        db=db,
        dose_id=dose_id,
        is_collected=is_collected
    )
    if not success:
        raise HTTPException(status_code=400, detail=msg)
    return {"status": "success", "message": msg, "dose": serialize_dose(dose, db) if dose else None}

@router.post("/{dose_id}/manual-confirm")
def manual_confirm_dose(
    dose_id: str,
    req: ManualConfirmRequest,
    db: Session = Depends(get_db)
):
    success, msg, dose = DoseOrchestrator.record_manual_take_confirmation(
        db=db,
        dose_id=dose_id,
        confirmed_by=req.confirmed_by,
        notes=req.notes
    )
    if not success:
        raise HTTPException(status_code=400, detail=msg)
    return {"status": "success", "message": msg, "dose": serialize_dose(dose, db)}
