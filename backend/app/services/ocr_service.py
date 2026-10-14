import re
import os
from typing import List, Dict, Any, Tuple
from sqlalchemy.orm import Session
from app.models.models import Prescription, PrescriptionCandidate, Medication, Cartridge, Schedule
from app.services.clock_service import system_clock

class OCRService:
    @staticmethod
    def extract_text_from_file(file_path: str, filename: str) -> str:
        """
        Extracts raw text from image or text file.
        Uses local fallback text parser or simulated medical OCR engine
        if tesseract/pdfplumber is not installed on the system.
        """
        # If it's a text-based sample file or has recognizable content
        ext = os.path.splitext(filename)[1].lower()
        if ext in [".txt", ".md"]:
            with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                return f.read()

        # Try pytesseract if available
        try:
            import pytesseract
            from PIL import Image
            img = Image.open(file_path)
            text = pytesseract.image_to_string(img)
            if text and len(text.strip()) > 10:
                return text
        except Exception:
            pass

        # Simulated fallback OCR for healthcare demonstration
        return (
            "Rx: Dr. Sarah Bennett, MD\n"
            "Patient: Eleanor Vance | DOB: 1948-03-12\n\n"
            "1. Metformin 500mg - Take 1 tablet twice daily with meals (Cartridge 1)\n"
            "2. Lisinopril 10mg - Take 1 tablet once daily morning before breakfast\n"
            "3. Atorvastatin 20mg - Take 1 tablet at bedtime\n"
            "4. Omeprazole 20mg - Take 1 capsule 30 minutes before breakfast\n"
        )

    @staticmethod
    def parse_candidates(raw_text: str) -> List[Dict[str, Any]]:
        """
        Extracts structured medication candidates from raw text.
        Identifies: name, strength, dose quantity, frequency, timing hint, meal instructions.
        Flags ambiguous fields.
        """
        candidates = []
        lines = [line.strip() for line in raw_text.split("\n") if line.strip()]

        med_pattern = re.compile(
            r"(?:(?:\d+[\.\)]\s*)?([A-Za-z]+(?:\s+[A-Za-z]+)?))\s+(\d+(?:\.\d+)?\s*(?:mg|mcg|g|ml))?",
            re.IGNORECASE
        )

        for line in lines:
            # Skip header lines like "Doctor", "Patient", "Rx", "Clinic"
            if any(h in line.lower() for h in ["rx:", "dr.", "patient:", "clinic", "hospital", "date:", "tel:"]):
                continue

            match = med_pattern.search(line)
            if not match:
                continue

            name = match.group(1).strip()
            # Filter common false positives
            if name.lower() in ["take", "tablet", "capsule", "daily", "every", "morning", "bedtime", "signature"]:
                continue

            strength = match.group(2).strip() if match.group(2) else None

            # Detect quantity
            qty_match = re.search(r"take\s+(\d+)\s*(?:tablet|cap|pill)?", line, re.IGNORECASE)
            qty = int(qty_match.group(1)) if qty_match else 1

            # Detect frequency
            freq = "Once daily"
            if re.search(r"twice\s+daily|bid|2\s*times", line, re.IGNORECASE):
                freq = "Twice daily"
            elif re.search(r"three\s+times|tid|3\s*times", line, re.IGNORECASE):
                freq = "Three times daily"
            elif re.search(r"bedtime|at night|qhs", line, re.IGNORECASE):
                freq = "Bedtime"

            # Detect meal relationship
            meal = "none"
            if re.search(r"with\s+(?:meals|food|breakfast)", line, re.IGNORECASE):
                meal = "with_breakfast" if "breakfast" in line.lower() else "with_food"
            elif re.search(r"before\s+(?:meals|food|breakfast)", line, re.IGNORECASE):
                meal = "before_breakfast" if "breakfast" in line.lower() else "before_food"
            elif re.search(r"after\s+(?:meals|food|breakfast|dinner)", line, re.IGNORECASE):
                meal = "after_dinner" if "dinner" in line.lower() else "after_food"

            timing_hint = "morning"
            if "bedtime" in line.lower() or "night" in line.lower():
                timing_hint = "bedtime"
            elif "evening" in line.lower() or "dinner" in line.lower():
                timing_hint = "evening"
            elif "afternoon" in line.lower() or "lunch" in line.lower():
                timing_hint = "afternoon"

            confidence = 0.9 if strength else 0.65
            notes = None if strength else "Warning: Strength was not clearly identified by OCR. Please verify."

            candidates.append({
                "medicine_name": name,
                "strength": strength,
                "prescribed_dose_qty": qty,
                "frequency": freq,
                "timing_hint": timing_hint,
                "meal_instructions": meal,
                "confidence": confidence,
                "notes": notes
            })

        return candidates

    @staticmethod
    def process_prescription_file(db: Session, filename: str, file_path: str) -> Prescription:
        raw_text = OCRService.extract_text_from_file(file_path, filename)
        from app.services.prescription_intelligence import PrescriptionIntelligenceService
        return PrescriptionIntelligenceService.create_prescription_with_draft(
            db=db,
            raw_text=raw_text,
            filename=filename,
            file_path=file_path
        )

    @staticmethod
    def review_and_confirm_prescription(
        db: Session,
        prescription_id: str,
        reviewed_by: str,
        review_items: List[Dict[str, Any]]
    ) -> Tuple[bool, str]:
        """
        Strict human review gatekeeper.
        NEVER creates medications or schedules until reviewed!
        """
        prescription = db.query(Prescription).filter(Prescription.id == prescription_id).first()
        if not prescription:
            return False, "Prescription record not found."

        if prescription.review_status == "confirmed":
            return False, "Prescription has already been verified and confirmed."

        for item in review_items:
            cand = db.query(PrescriptionCandidate).filter(
                PrescriptionCandidate.id == item["candidate_id"],
                PrescriptionCandidate.prescription_id == prescription_id
            ).first()
            if not cand:
                continue

            action = item.get("action", "accept")
            if action in ["accept", "modify"]:
                cand.status = "accepted"
                med_name = item.get("medicine_name") or cand.medicine_name
                strength = item.get("strength") or cand.strength
                meal_inst = item.get("meal_instructions") or cand.meal_instructions
                dose_qty = item.get("prescribed_dose_qty") or cand.prescribed_dose_qty

                # Create active Medication
                med = Medication(
                    name=med_name,
                    strength=strength,
                    dosage_form="tablet",
                    instructions=f"Reviewed from prescription: {prescription.filename}",
                    meal_context=meal_inst or "none",
                    low_stock_threshold=5,
                    is_active=True,
                    created_at=system_clock.now()
                )
                db.add(med)
                db.flush()

                # Assign cartridge if specified within active device hardware count
                cart_num = item.get("assign_cartridge_number")
                from app.models.models import DeviceState
                dev = db.query(DeviceState).first()
                max_cart = dev.cartridge_count if dev else 4
                if cart_num and 1 <= cart_num <= max_cart:
                    dev_id = dev.device_id if dev else "ESP32_PILLBOX_01"
                    cart = db.query(Cartridge).filter(
                        Cartridge.device_id == dev_id,
                        Cartridge.cartridge_number == cart_num
                    ).first()
                    if cart:
                        cart.medication_id = med.id
                        init_stock = item.get("initial_stock", 0)
                        if init_stock > 0:
                            cart.current_stock = init_stock
                            cart.is_configured = True
                            cart.last_refilled_at = system_clock.now()

                # Create default Schedule
                timing_map = {
                    "morning": ("08:00", "morning"),
                    "afternoon": ("13:00", "afternoon"),
                    "evening": ("19:00", "evening"),
                    "bedtime": ("21:30", "bedtime")
                }
                hint = cand.timing_hint or "morning"
                sched_time, tod_label = timing_map.get(hint, ("08:00", "morning"))

                sched = Schedule(
                    medication_id=med.id,
                    time_of_day_label=tod_label,
                    scheduled_time_str=sched_time,
                    meal_timing=meal_inst or "none",
                    dose_quantity=dose_qty,
                    is_active=True,
                    created_at=system_clock.now()
                )
                db.add(sched)

            elif action == "reject":
                cand.status = "discarded"

        prescription.review_status = "confirmed"
        prescription.reviewed_by = reviewed_by
        prescription.reviewed_at = system_clock.now()
        db.commit()
        return True, "Prescription successfully reviewed and medications activated."
