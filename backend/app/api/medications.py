from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List, Optional
from app.database import get_db
from app.models.models import Medication, Cartridge, Schedule, DoseOccurrence, InventoryTransaction
from app.schemas.schemas import (
    MedicationResponse, MedicationCreate, MedicationUpdate,
    MedicationDependencyResponse, MedicationDeactivateResponse,
    ScheduleResponse
)
from app.services.dose_orchestrator import DoseOrchestrator
from app.services.clock_service import system_clock

router = APIRouter(prefix="/medications", tags=["Medications"])

def build_medication_response(m: Medication, db: Session) -> MedicationResponse:
    cart = db.query(Cartridge).filter(Cartridge.medication_id == m.id).first()
    schedules = db.query(Schedule).filter(Schedule.medication_id == m.id).all()
    sched_responses = [
        ScheduleResponse(
            id=s.id,
            medication_id=s.medication_id,
            time_of_day_label=s.time_of_day_label,
            scheduled_time_str=s.scheduled_time_str,
            meal_timing=s.meal_timing,
            custom_meal_note=s.custom_meal_note,
            dose_quantity=s.dose_quantity,
            start_date=s.start_date,
            end_date=s.end_date,
            recurrence=s.recurrence or "daily",
            days_of_week=s.days_of_week or "all",
            is_active=s.is_active,
            created_at=s.created_at,
            medication_name=m.name,
            cartridge_number=cart.cartridge_number if cart else None
        )
        for s in schedules
    ]
    return MedicationResponse(
        id=m.id,
        name=m.name,
        strength=m.strength,
        dosage_form=m.dosage_form,
        instructions=m.instructions,
        meal_context=m.meal_context,
        low_stock_threshold=m.low_stock_threshold,
        prescribed_dose_qty=m.prescribed_dose_qty or 1,
        is_active=m.is_active,
        created_at=m.created_at,
        assigned_cartridge_number=cart.cartridge_number if cart else None,
        current_stock=cart.current_stock if cart else None,
        schedules=sched_responses
    )

@router.get("/", response_model=List[MedicationResponse])
def list_medications(include_inactive: bool = True, db: Session = Depends(get_db)):
    query = db.query(Medication)
    if not include_inactive:
        query = query.filter(Medication.is_active == True)
    meds = query.order_by(Medication.created_at.desc()).all()
    return [build_medication_response(m, db) for m in meds]

@router.post("/", response_model=MedicationResponse)
def create_medication(med_in: MedicationCreate, db: Session = Depends(get_db)):
    med_dict = med_in.dict(exclude={"schedules"})
    med = Medication(**med_dict, created_at=system_clock.now())
    db.add(med)
    db.flush()

    if med_in.schedules:
        for s_data in med_in.schedules:
            sched = Schedule(
                medication_id=med.id,
                time_of_day_label=s_data.time_of_day_label,
                scheduled_time_str=s_data.scheduled_time_str,
                meal_timing=s_data.meal_timing,
                custom_meal_note=s_data.custom_meal_note,
                dose_quantity=s_data.dose_quantity,
                start_date=s_data.start_date,
                end_date=s_data.end_date,
                recurrence=s_data.recurrence,
                days_of_week=s_data.days_of_week,
                is_active=True,
                created_at=system_clock.now()
            )
            db.add(sched)

    db.commit()
    db.refresh(med)

    # Generate daily doses if schedule added
    if med_in.schedules and med.is_active:
        DoseOrchestrator.generate_daily_doses_if_needed(db)

    return build_medication_response(med, db)

@router.get("/{med_id}", response_model=MedicationResponse)
def get_medication(med_id: str, db: Session = Depends(get_db)):
    med = db.query(Medication).filter(Medication.id == med_id).first()
    if not med:
        raise HTTPException(status_code=404, detail="Medication not found")
    return build_medication_response(med, db)

@router.put("/{med_id}", response_model=MedicationResponse)
def update_medication(med_id: str, med_in: MedicationUpdate, db: Session = Depends(get_db)):
    med = db.query(Medication).filter(Medication.id == med_id).first()
    if not med:
        raise HTTPException(status_code=404, detail="Medication not found")

    update_data = med_in.dict(exclude_unset=True, exclude={"schedules"})
    for field, val in update_data.items():
        setattr(med, field, val)

    if med_in.schedules is not None:
        # Deactivate previous schedules
        existing_schedules = db.query(Schedule).filter(Schedule.medication_id == med.id).all()
        for s in existing_schedules:
            s.is_active = False

        for s_data in med_in.schedules:
            sched = Schedule(
                medication_id=med.id,
                time_of_day_label=s_data.time_of_day_label,
                scheduled_time_str=s_data.scheduled_time_str,
                meal_timing=s_data.meal_timing,
                custom_meal_note=s_data.custom_meal_note,
                dose_quantity=s_data.dose_quantity,
                start_date=s_data.start_date,
                end_date=s_data.end_date,
                recurrence=s_data.recurrence,
                days_of_week=s_data.days_of_week,
                is_active=True,
                created_at=system_clock.now()
            )
            db.add(sched)

    db.commit()
    db.refresh(med)

    if med.is_active:
        DoseOrchestrator.generate_daily_doses_if_needed(db)

    return build_medication_response(med, db)

@router.get("/{med_id}/dependencies", response_model=MedicationDependencyResponse)
def get_medication_dependencies(med_id: str, db: Session = Depends(get_db)):
    med = db.query(Medication).filter(Medication.id == med_id).first()
    if not med:
        raise HTTPException(status_code=404, detail="Medication not found")

    cart = db.query(Cartridge).filter(Cartridge.medication_id == med.id).first()
    schedules = db.query(Schedule).filter(Schedule.medication_id == med.id, Schedule.is_active == True).all()
    all_doses = db.query(DoseOccurrence).filter(DoseOccurrence.medication_id == med.id).all()
    historical_doses = [d for d in all_doses if d.status != "scheduled"]
    pending_doses = [d for d in all_doses if d.status == "scheduled"]
    txs = db.query(InventoryTransaction).filter(InventoryTransaction.medication_id == med.id).all()

    can_delete = (len(all_doses) == 0 and len(txs) == 0)
    recommendation = "delete" if can_delete else "archive"

    warn_parts = []
    if cart and cart.current_stock > 0:
        warn_parts.append(f"Cartridge {cart.cartridge_number} holds {cart.current_stock} pills.")
    if len(historical_doses) > 0:
        warn_parts.append(f"{len(historical_doses)} dose records on file.")
    if len(schedules) > 0:
        warn_parts.append(f"{len(schedules)} active daily schedule times will be stopped.")

    warning_msg = " ".join(warn_parts) if warn_parts else "No dependencies detected. Safe to remove completely."

    return MedicationDependencyResponse(
        medication_id=med.id,
        medication_name=med.name,
        can_hard_delete=can_delete,
        has_active_cartridge=cart is not None,
        cartridge_number=cart.cartridge_number if cart else None,
        current_stock=cart.current_stock if cart else 0,
        schedules_count=len(schedules),
        historical_doses_count=len(historical_doses),
        pending_doses_count=len(pending_doses),
        inventory_transactions_count=len(txs),
        recommendation=recommendation,
        warning_message=warning_msg
    )

@router.delete("/{med_id}", response_model=MedicationDeactivateResponse)
def remove_or_deactivate_medication(
    med_id: str,
    force: bool = False,
    caregiver_name: str = "Marcus Vance (Caregiver)",
    reason: Optional[str] = None,
    db: Session = Depends(get_db)
):
    med = db.query(Medication).filter(Medication.id == med_id).first()
    if not med:
        raise HTTPException(status_code=404, detail="Medication not found")

    cart = db.query(Cartridge).filter(Cartridge.medication_id == med.id).first()
    all_doses = db.query(DoseOccurrence).filter(DoseOccurrence.medication_id == med.id).all()
    txs = db.query(InventoryTransaction).filter(InventoryTransaction.medication_id == med.id).all()
    schedules = db.query(Schedule).filter(Schedule.medication_id == med.id).all()

    has_audit_history = (len(all_doses) > 0) or (len(txs) > 0)

    # Physical Stock Guard: Prevent silent deallocation when physical pills remain in slot
    if cart and cart.current_stock > 0 and not force:
        raise HTTPException(
            status_code=400,
            detail=f"Cannot remove medication while Cartridge {cart.cartridge_number} contains {cart.current_stock} pills. Please unload cartridge or confirm with force=true."
        )

    # If force-archived while stock remains, record inventory audit trail and quarantine the cartridge
    if cart and cart.current_stock > 0 and force:
        remaining_pills = cart.current_stock
        audit_reason = reason or "Prescription discontinued / modified with remaining stock"
        tx = InventoryTransaction(
            cartridge_id=cart.id,
            medication_id=med.id,
            delta=-remaining_pills,
            previous_stock=remaining_pills,
            new_stock=0,
            reason="archival_quarantine",
            confirmed_sensor_id=None,
            dose_occurrence_id=None,
            timestamp=system_clock.now()
        )
        db.add(tx)
        cart.needs_reconciliation = True
        cart.quarantine_reason = (
            f"Medication '{med.name}' was archived by {caregiver_name} while {remaining_pills} physical pills remained. "
            f"Reason: {audit_reason}. Physical unloading and verification required before reassignment or dispensing."
        )
        cart.is_configured = False
        cart.medication_id = None
        cart.current_stock = 0
    elif cart:
        cart.is_configured = False
        cart.medication_id = None
        cart.current_stock = 0

    if has_audit_history:
        # Safe Archival / Deactivation to preserve medical record and inventory audit
        med.is_active = False
        for s in schedules:
            s.is_active = False

        # Cancel unperformed scheduled doses
        pending_doses = db.query(DoseOccurrence).filter(
            DoseOccurrence.medication_id == med.id,
            DoseOccurrence.status == "scheduled"
        ).all()
        for d in pending_doses:
            d.status = "missed"
            d.fault_reason = f"Medication archived by {caregiver_name}"

        db.commit()
        return MedicationDeactivateResponse(
            status="archived",
            message=f"Medication '{med.name}' safely archived. Audit history and {len(all_doses)} dose records preserved.",
            medication_id=med.id,
            is_active=False
        )
    else:
        # Completely unreferenced draft -> safe hard delete
        for s in schedules:
            db.delete(s)
        db.delete(med)
        db.commit()
        return MedicationDeactivateResponse(
            status="deleted",
            message=f"Draft medication '{med.name}' successfully deleted.",
            medication_id=med_id,
            is_active=False
        )

@router.post("/{med_id}/reactivate", response_model=MedicationResponse)
def reactivate_medication(med_id: str, db: Session = Depends(get_db)):
    med = db.query(Medication).filter(Medication.id == med_id).first()
    if not med:
        raise HTTPException(status_code=404, detail="Medication not found")

    med.is_active = True
    schedules = db.query(Schedule).filter(Schedule.medication_id == med.id).all()
    for s in schedules:
        s.is_active = True

    db.commit()
    db.refresh(med)

    DoseOrchestrator.generate_daily_doses_if_needed(db)
    return build_medication_response(med, db)
