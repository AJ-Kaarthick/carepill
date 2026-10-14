import os
import json
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Response
from sqlalchemy.orm import Session
from typing import List, Dict, Any, Optional
from app.database import get_db
from app.models.models import Prescription, PrescriptionCandidate, Medication, Cartridge, Schedule, InventoryTransaction
from app.schemas.schemas import (
    PrescriptionResponse, PrescriptionReviewSubmission,
    PrescriptionPasteRequest, DraftReviewSubmission,
    PhysicalLoadingSubmission, PrescriptionActivateSubmission
)
from app.services.ocr_service import OCRService
from app.services.prescription_intelligence import PrescriptionIntelligenceService
from app.services.device_service import DeviceService
from app.services.dose_orchestrator import DoseOrchestrator
from app.services.inventory_service import InventoryService
from app.services.clock_service import system_clock

router = APIRouter(prefix="/prescriptions", tags=["Prescriptions & Guided Setup"])

UPLOAD_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "uploads")
os.makedirs(UPLOAD_DIR, exist_ok=True)

ALLOWED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".pdf", ".txt"}
MAX_FILE_SIZE_BYTES = 10 * 1024 * 1024  # 10MB

@router.get("/", response_model=List[PrescriptionResponse])
def list_prescriptions(db: Session = Depends(get_db)):
    return db.query(Prescription).order_by(Prescription.uploaded_at.desc()).all()

@router.get("/{prescription_id}", response_model=PrescriptionResponse)
def get_prescription(prescription_id: str, db: Session = Depends(get_db)):
    prescription = db.query(Prescription).filter(Prescription.id == prescription_id).first()
    if not prescription:
        raise HTTPException(status_code=404, detail="Prescription not found")
    return prescription

@router.get("/{prescription_id}/draft")
def get_prescription_draft(prescription_id: str, db: Session = Depends(get_db)):
    """
    Returns the structured Care Plan Draft JSON for the 4-step wizard.
    """
    prescription = db.query(Prescription).filter(Prescription.id == prescription_id).first()
    if not prescription:
        raise HTTPException(status_code=404, detail="Prescription not found")

    if prescription.draft_json:
        try:
            return json.loads(prescription.draft_json)
        except Exception:
            pass

    # If draft_json wasn't set yet, generate it dynamically from raw text
    draft = PrescriptionIntelligenceService.generate_care_plan_draft(
        prescription.raw_ocr_text or "",
        prescription.filename
    )
    prescription.draft_json = json.dumps(draft)
    db.commit()
    return draft

@router.get("/{prescription_id}/export-json")
def export_prescription_draft_json(prescription_id: str, db: Session = Depends(get_db)):
    """
    Exports structured care plan draft as a downloadable JSON file.
    """
    prescription = db.query(Prescription).filter(Prescription.id == prescription_id).first()
    if not prescription:
        raise HTTPException(status_code=404, detail="Prescription not found")

    if prescription.draft_json:
        payload = prescription.draft_json
    else:
        draft = PrescriptionIntelligenceService.generate_care_plan_draft(
            prescription.raw_ocr_text or "",
            prescription.filename
        )
        payload = json.dumps(draft, indent=2)

    filename = f"care_plan_draft_{prescription.id[:8]}.json"
    return Response(
        content=payload,
        media_type="application/json",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'}
    )

@router.post("/paste", response_model=PrescriptionResponse)
def paste_prescription_text(data: PrescriptionPasteRequest, db: Session = Depends(get_db)):
    """
    Intake Step 1 (Paste): Parses raw doctor prescription text into a structured Care Plan Draft.
    """
    if not data.raw_text or len(data.raw_text.strip()) < 5:
        raise HTTPException(status_code=400, detail="Prescription text is too short or empty.")

    prescription = PrescriptionIntelligenceService.create_prescription_with_draft(
        db=db,
        raw_text=data.raw_text,
        filename=data.filename or "Pasted Prescription"
    )
    return prescription

@router.post("/upload", response_model=PrescriptionResponse)
async def upload_prescription(file: UploadFile = File(...), db: Session = Depends(get_db)):
    """
    Intake Step 1 (Upload): Accepts PDF or image, runs OCR / text extraction, generates Care Plan Draft.
    """
    ext = os.path.splitext(file.filename)[1].lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file extension '{ext}'. Allowed formats: {', '.join(ALLOWED_EXTENSIONS)}"
        )

    file_content = await file.read()
    if len(file_content) > MAX_FILE_SIZE_BYTES:
        raise HTTPException(status_code=400, detail="File exceeds maximum allowed size of 10MB.")

    save_path = os.path.join(UPLOAD_DIR, f"{file.filename}")
    with open(save_path, "wb") as f:
        f.write(file_content)

    prescription = OCRService.process_prescription_file(
        db=db,
        filename=file.filename,
        file_path=save_path
    )
    return prescription

@router.post("/{prescription_id}/review-draft")
def review_prescription_draft(
    prescription_id: str,
    data: DraftReviewSubmission,
    db: Session = Depends(get_db)
):
    """
    Wizard Step 2: Caregiver reviews extracted medications, validates proposed 4/6/8 cartridge count,
    and approves scheduled dose times.
    """
    prescription = db.query(Prescription).filter(Prescription.id == prescription_id).first()
    if not prescription:
        raise HTTPException(status_code=404, detail="Prescription not found")

    # Update device hardware configuration if requested
    if data.target_cartridge_count in [4, 6, 8]:
        DeviceService.configure_device_cartridges(
            db=db,
            device_id="ESP32_PILLBOX_01",
            target_count=data.target_cartridge_count,
            force=True
        )

    # Update draft JSON with caregiver modifications
    current_draft = {}
    if prescription.draft_json:
        try:
            current_draft = json.loads(prescription.draft_json)
        except Exception:
            pass

    current_draft["extracted_medications"] = data.medications
    current_draft["proposed_schedules"] = data.schedules
    if "hardware_proposal" not in current_draft:
        current_draft["hardware_proposal"] = {}
    current_draft["hardware_proposal"]["cartridge_assignments"] = data.cartridge_assignments
    current_draft["hardware_proposal"]["recommended_cartridge_count"] = data.target_cartridge_count

    prescription.draft_json = json.dumps(current_draft)
    prescription.review_status = "schedule_reviewed"
    prescription.reviewed_by = data.reviewed_by
    prescription.reviewed_at = system_clock.now()

    db.commit()
    db.refresh(prescription)
    return {
        "status": "success",
        "review_status": prescription.review_status,
        "message": "Prescription draft and schedule approved. Proceed to physical cartridge loading.",
        "draft": current_draft
    }

@router.post("/{prescription_id}/confirm-loading")
def confirm_physical_loading(
    prescription_id: str,
    data: PhysicalLoadingSubmission,
    db: Session = Depends(get_db)
):
    """
    Wizard Step 3: Physical Loading Confirmation.
    Caregiver must enter actual physical pill counts (1-30) and check the physical verification checkbox.
    No silent defaulting or guessing stock is permitted!
    """
    prescription = db.query(Prescription).filter(Prescription.id == prescription_id).first()
    if not prescription:
        raise HTTPException(status_code=404, detail="Prescription not found")

    dev = DeviceService.get_or_create_device(db, "ESP32_PILLBOX_01")

    # Validate all loading items
    for item in data.cartridge_loads:
        if not item.confirm_physical_loaded:
            raise HTTPException(
                status_code=400,
                detail=f"Cartridge {item.cartridge_number} verification checkbox must be checked to confirm pills were physically placed in the slot."
            )
        if item.pill_count < 1 or item.pill_count > 30:
            raise HTTPException(
                status_code=400,
                detail=f"Cartridge {item.cartridge_number} must have an explicit pill count between 1 and 30. (Entered: {item.pill_count})"
            )

    # Apply loading to database cartridges
    loaded_summary = []
    for item in data.cartridge_loads:
        if item.cartridge_number > dev.cartridge_count:
            continue

        # Find or create Medication
        med = db.query(Medication).filter(Medication.name.ilike(item.medication_name.strip())).first()
        if not med:
            med = Medication(
                name=item.medication_name.strip(),
                dosage_form="tablet",
                instructions=f"Prescription {prescription.filename}",
                low_stock_threshold=5,
                is_active=True,
                created_at=system_clock.now()
            )
            db.add(med)
            db.flush()

        # Update cartridge
        cart = db.query(Cartridge).filter(
            Cartridge.device_id == "ESP32_PILLBOX_01",
            Cartridge.cartridge_number == item.cartridge_number
        ).first()

        if not cart:
            cart = Cartridge(
                device_id="ESP32_PILLBOX_01",
                cartridge_number=item.cartridge_number,
                medication_id=med.id,
                current_stock=item.pill_count,
                capacity=30,
                low_stock_threshold=5,
                is_configured=True,
                last_refilled_at=system_clock.now()
            )
            db.add(cart)
            db.flush()
        else:
            prev_stock = cart.current_stock
            cart.medication_id = med.id
            cart.current_stock = item.pill_count
            cart.is_configured = True
            cart.last_refilled_at = system_clock.now()

            # Record inventory transaction
            tx = InventoryTransaction(
                cartridge_id=cart.id,
                medication_id=med.id,
                delta=item.pill_count - prev_stock,
                previous_stock=prev_stock,
                new_stock=item.pill_count,
                reason="initial_prescription_load",
                timestamp=system_clock.now()
            )
            db.add(tx)

        loaded_summary.append({
            "cartridge_number": item.cartridge_number,
            "medication_name": med.name,
            "confirmed_stock": item.pill_count
        })

    prescription.review_status = "loaded"
    prescription.reviewed_by = data.loaded_by
    prescription.reviewed_at = system_clock.now()

    db.commit()
    return {
        "status": "success",
        "review_status": prescription.review_status,
        "message": f"Successfully verified and loaded {len(loaded_summary)} circular cartridges with physical pill stock.",
        "loaded_cartridges": loaded_summary
    }

@router.post("/{prescription_id}/activate")
def activate_prescription(
    prescription_id: str,
    data: PrescriptionActivateSubmission,
    db: Session = Depends(get_db)
):
    """
    Wizard Step 4: Final verification and activation.
    Activates schedules, syncs offline LittleFS cache, marks prescription confirmed.
    DOES NOT trigger an immediate unprompted dispense.
    """
    prescription = db.query(Prescription).filter(Prescription.id == prescription_id).first()
    if not prescription:
        raise HTTPException(status_code=404, detail="Prescription not found")

    # Load draft details
    draft = {}
    if prescription.draft_json:
        try:
            draft = json.loads(prescription.draft_json)
        except Exception:
            pass

    schedules_data = draft.get("proposed_schedules", [])

    created_schedules_count = 0
    for s_item in schedules_data:
        med_name = s_item.get("medication_name")
        if not med_name:
            continue

        med = db.query(Medication).filter(Medication.name.ilike(med_name.strip())).first()
        if not med:
            continue

        sched_time = s_item.get("scheduled_time_str", "08:00")
        tod_label = s_item.get("time_of_day_label", "morning")
        meal_timing = s_item.get("meal_timing", "none")
        dose_qty = s_item.get("dose_quantity", 1)

        # Avoid duplicating schedule
        existing = db.query(Schedule).filter(
            Schedule.medication_id == med.id,
            Schedule.scheduled_time_str == sched_time,
            Schedule.is_active == True
        ).first()

        if not existing:
            sched = Schedule(
                medication_id=med.id,
                time_of_day_label=tod_label,
                scheduled_time_str=sched_time,
                meal_timing=meal_timing,
                dose_quantity=dose_qty,
                is_active=True,
                created_at=system_clock.now()
            )
            db.add(sched)
            created_schedules_count += 1

    prescription.review_status = "confirmed"
    prescription.reviewed_by = data.activated_by
    prescription.reviewed_at = system_clock.now()
    prescription.caregiver_notes = data.notes

    db.commit()

    # Generate daily dose timeline for today without immediately dispensing
    DoseOrchestrator.generate_daily_doses_if_needed(db)

    return {
        "status": "success",
        "review_status": "confirmed",
        "message": f"Prescription activated successfully. Created {created_schedules_count} schedules. Dispenser offline cache synchronized.",
        "activated_at": prescription.reviewed_at.isoformat()
    }

@router.post("/review")
def review_prescription_legacy(review_data: PrescriptionReviewSubmission, db: Session = Depends(get_db)):
    """
    Backward-compatible review endpoint for legacy tests and scripts.
    """
    success, message = OCRService.review_and_confirm_prescription(
        db=db,
        prescription_id=review_data.prescription_id,
        reviewed_by=review_data.reviewed_by,
        review_items=[item.dict() for item in review_data.items]
    )
    if not success:
        raise HTTPException(status_code=400, detail=message)
    return {"status": "success", "message": message}
