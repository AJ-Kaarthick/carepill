from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List
from app.database import get_db
from app.models.models import Schedule, Medication, Cartridge
from app.schemas.schemas import ScheduleResponse, ScheduleCreate, ScheduleUpdate
from app.services.dose_orchestrator import DoseOrchestrator
from app.services.clock_service import system_clock

router = APIRouter(prefix="/schedules", tags=["Schedules & Meals"])

@router.get("/", response_model=List[ScheduleResponse])
def get_schedules(db: Session = Depends(get_db)):
    schedules = db.query(Schedule).all()
    results = []
    for s in schedules:
        med = db.query(Medication).filter(Medication.id == s.medication_id).first()
        cart = db.query(Cartridge).filter(Cartridge.medication_id == s.medication_id).first() if med else None
        results.append(ScheduleResponse(
            id=s.id,
            medication_id=s.medication_id,
            time_of_day_label=s.time_of_day_label,
            scheduled_time_str=s.scheduled_time_str,
            meal_timing=s.meal_timing,
            custom_meal_note=s.custom_meal_note,
            dose_quantity=s.dose_quantity,
            is_active=s.is_active,
            created_at=s.created_at,
            medication_name=med.name if med else "Unknown",
            cartridge_number=cart.cartridge_number if cart else None
        ))
    return results

@router.post("/", response_model=ScheduleResponse)
def create_schedule(data: ScheduleCreate, db: Session = Depends(get_db)):
    med = db.query(Medication).filter(Medication.id == data.medication_id).first()
    if not med:
        raise HTTPException(status_code=404, detail="Medication not found")

    sched = Schedule(**data.dict(), created_at=system_clock.now())
    db.add(sched)
    db.commit()
    db.refresh(sched)

    # Regenerate daily doses so new schedule takes effect immediately
    DoseOrchestrator.generate_daily_doses_if_needed(db)

    cart = db.query(Cartridge).filter(Cartridge.medication_id == med.id).first()
    return ScheduleResponse(
        id=sched.id,
        medication_id=sched.medication_id,
        time_of_day_label=sched.time_of_day_label,
        scheduled_time_str=sched.scheduled_time_str,
        meal_timing=sched.meal_timing,
        custom_meal_note=sched.custom_meal_note,
        dose_quantity=sched.dose_quantity,
        is_active=sched.is_active,
        created_at=sched.created_at,
        medication_name=med.name,
        cartridge_number=cart.cartridge_number if cart else None
    )

@router.put("/{schedule_id}", response_model=ScheduleResponse)
def update_schedule(schedule_id: str, data: ScheduleUpdate, db: Session = Depends(get_db)):
    sched = db.query(Schedule).filter(Schedule.id == schedule_id).first()
    if not sched:
        raise HTTPException(status_code=404, detail="Schedule not found")

    for field, val in data.dict(exclude_unset=True).items():
        setattr(sched, field, val)

    db.commit()
    db.refresh(sched)

    med = db.query(Medication).filter(Medication.id == sched.medication_id).first()
    cart = db.query(Cartridge).filter(Cartridge.medication_id == sched.medication_id).first() if med else None
    return ScheduleResponse(
        id=sched.id,
        medication_id=sched.medication_id,
        time_of_day_label=sched.time_of_day_label,
        scheduled_time_str=sched.scheduled_time_str,
        meal_timing=sched.meal_timing,
        custom_meal_note=sched.custom_meal_note,
        dose_quantity=sched.dose_quantity,
        is_active=sched.is_active,
        created_at=sched.created_at,
        medication_name=med.name if med else "Unknown",
        cartridge_number=cart.cartridge_number if cart else None
    )

@router.delete("/{schedule_id}")
def delete_schedule(schedule_id: str, db: Session = Depends(get_db)):
    sched = db.query(Schedule).filter(Schedule.id == schedule_id).first()
    if not sched:
        raise HTTPException(status_code=404, detail="Schedule not found")
    sched.is_active = False
    db.commit()
    return {"status": "success", "message": "Schedule deactivated."}
