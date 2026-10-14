import re
import json
from typing import List, Dict, Any, Optional, Tuple
from sqlalchemy.orm import Session
from app.config import settings
from app.models.models import Prescription, PrescriptionCandidate, Cartridge, Medication, Schedule, DeviceState
from app.services.clock_service import system_clock

class PrescriptionIntelligenceService:
    @staticmethod
    def extract_medications_from_text(raw_text: str) -> List[Dict[str, Any]]:
        """
        Extracts structured medication candidate records from raw prescription text.
        Identifies:
        - Medicine Name
        - Strength (e.g., 500mg, 10mg, 20mcg)
        - Dosage Form (tablet, capsule, syrup, cream, inhaler, drops, injection)
        - Frequency (once daily, twice daily, bedtime, PRN)
        - Meal Context (none, before_breakfast, with_food, after_dinner, etc.)
        - Dispenser Eligibility (solid oral vs non-solid / PRN)
        - Missing field warnings and confidence scores
        """
        extracted: List[Dict[str, Any]] = []
        lines = [line.strip() for line in raw_text.split("\n") if line.strip()]

        # Medication Regex with optional number prefix and strength
        med_regex = re.compile(
            r"(?:(?:\d+[\.\)]\s*)?([A-Za-z]+(?:\s+[A-Za-z]+)?))\s+(\d+(?:\.\d+)?\s*(?:mg|mcg|g|ml|iu))?",
            re.IGNORECASE
        )

        for line in lines:
            line_lower = line.lower()
            # Ignore headers, clinics, doctors, dates
            if any(h in line_lower for h in ["rx:", "dr.", "doctor", "clinic", "hospital", "patient:", "date:", "tel:", "phone:", "signature"]):
                continue

            # Check if this line describes a medication
            match = med_regex.search(line)
            if not match:
                continue

            name = match.group(1).strip()
            # Exclude clinical stop words
            if name.lower() in [
                "take", "tablet", "tablets", "capsule", "capsules", "daily", "every",
                "morning", "evening", "bedtime", "after", "before", "with", "meals", "water"
            ]:
                continue

            raw_strength = match.group(2).strip() if match.group(2) else None

            # Detect dosage form
            form = "tablet"
            if re.search(r"\bcapsule[s]?\b|\bcap[s]?\b", line_lower):
                form = "capsule"
            elif re.search(r"\bsyrup\b|\bliquid\b|\bsolution\b|\bsuspension\b", line_lower):
                form = "syrup"
            elif re.search(r"\bcream\b|\bointment\b|\bgel\b|\blotion\b", line_lower):
                form = "cream"
            elif re.search(r"\binhaler\b|\bpuff[s]?\b|\baerosol\b", line_lower):
                form = "inhaler"
            elif re.search(r"\binjection\b|\bpen\b|\binsulin\b", line_lower):
                form = "injection"
            elif re.search(r"\bdrops\b|\beye\s*drops\b|\bear\s*drops\b", line_lower):
                form = "drops"

            # Detect PRN / As Needed
            is_prn = bool(re.search(r"\bprn\b|\bas\s+needed\b|\bif\s+needed\b|\bwhen\s+required\b", line_lower))

            # Detect dose quantity
            qty_match = re.search(r"take\s+(\d+)\s*(?:tablet|tablets|cap|capsule|pill|pills)?", line_lower)
            dose_qty = int(qty_match.group(1)) if qty_match else 1

            # Detect Frequency
            frequency = "Once daily"
            timing_hint = "morning"
            if is_prn:
                frequency = "PRN (As Needed)"
                timing_hint = "prn"
            elif re.search(r"\btwice\s+daily\b|\bbid\b|\b2\s*times\s*a?\s*day\b", line_lower):
                frequency = "Twice daily"
                timing_hint = "morning_and_evening"
            elif re.search(r"\bthree\s+times\s+daily\b|\btid\b|\b3\s*times\s*a?\s*day\b", line_lower):
                frequency = "Three times daily"
                timing_hint = "morning_afternoon_evening"
            elif re.search(r"\bfour\s+times\s+daily\b|\bqid\b|\b4\s*times\s*a?\s*day\b", line_lower):
                frequency = "Four times daily"
                timing_hint = "morning_afternoon_evening_bedtime"
            elif re.search(r"\bbedtime\b|\bat\s+night\b|\bqhs\b|\bbefore\s+sleep\b", line_lower):
                frequency = "At bedtime"
                timing_hint = "bedtime"
            elif re.search(r"\bevening\b|\bdinner\b", line_lower):
                frequency = "Once daily (Evening)"
                timing_hint = "evening"
            elif re.search(r"\bafternoon\b|\blunch\b", line_lower):
                frequency = "Once daily (Afternoon)"
                timing_hint = "afternoon"

            # Detect Meal Relationship
            meal_context = "none"
            if "breakfast" in line_lower:
                if "before" in line_lower: meal_context = "before_breakfast"
                elif "after" in line_lower: meal_context = "after_breakfast"
                else: meal_context = "with_breakfast"
            elif "lunch" in line_lower:
                if "before" in line_lower: meal_context = "before_lunch"
                elif "after" in line_lower: meal_context = "after_lunch"
                else: meal_context = "with_lunch"
            elif "dinner" in line_lower:
                if "before" in line_lower: meal_context = "before_dinner"
                elif "after" in line_lower: meal_context = "after_dinner"
                else: meal_context = "with_dinner"
            elif re.search(r"\bwith\s+(?:meals|food)\b", line_lower):
                meal_context = "with_food"
            elif re.search(r"\bbefore\s+(?:meals|food)\b", line_lower):
                meal_context = "before_breakfast" if "morning" in timing_hint else "before_dinner"
            elif re.search(r"\bafter\s+(?:meals|food)\b", line_lower):
                meal_context = "after_dinner" if "evening" in timing_hint else "after_breakfast"

            # Detect Duration / Refills
            duration_match = re.search(r"for\s+(\d+)\s*(days|weeks|months)", line_lower)
            duration = f"{duration_match.group(1)} {duration_match.group(2)}" if duration_match else "30 days"

            refills_match = re.search(r"refill[s]?\s*:\s*(\d+)", line_lower)
            refills = int(refills_match.group(1)) if refills_match else 0

            # Determine dispenser support
            is_solid = form in ["tablet", "capsule"]
            is_supported = is_solid and not is_prn
            unsupported_reason = None
            if not is_solid:
                unsupported_reason = f"Non-solid formulation ({form}) cannot be dispensed by circular carousel. Manual administration required."
            elif is_prn:
                unsupported_reason = "PRN (as-needed) medications should not be scheduled for autonomous dispensing."

            # Calculate confidence & warnings
            warnings = []
            confidence = 0.95
            if not raw_strength:
                warnings.append("Strength was not identified. Please enter strength (e.g., 500mg).")
                confidence -= 0.25
            if meal_context == "none":
                warnings.append("No specific meal instruction detected.")
            if is_prn:
                warnings.append("Marked as PRN (As Needed). Excluded from automatic carousel schedule.")

            extracted.append({
                "medicine_name": name.title(),
                "strength": raw_strength,
                "dosage_form": form,
                "prescribed_dose_qty": dose_qty,
                "frequency": frequency,
                "timing_hint": timing_hint,
                "meal_context": meal_context,
                "duration": duration,
                "refills": refills,
                "is_dispenser_supported": is_supported,
                "unsupported_reason": unsupported_reason,
                "warnings": warnings,
                "confidence": round(max(0.4, confidence), 2),
                "raw_line": line
            })

        return extracted

    @staticmethod
    def propose_cartridge_allocation(extracted_meds: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Calculates minimum required circular cartridge slots (4, 6, or 8).
        Assigns exactly 1 medicine per cartridge slot.
        Reuses the same slot for recurring morning/evening doses.
        Flags capacity warning if count > 8.
        """
        supported_meds = [m for m in extracted_meds if m.get("is_dispenser_supported", True)]
        unsupported_meds = [m for m in extracted_meds if not m.get("is_dispenser_supported", True)]

        # Unique medicines by name + strength
        distinct_names = []
        for m in supported_meds:
            key = f"{m['medicine_name']} {m.get('strength') or ''}".strip()
            if key not in distinct_names:
                distinct_names.append(key)

        num_meds = len(distinct_names)

        # Sizing rules:
        if num_meds <= 4:
            recommended_count = 4
        elif num_meds <= 6:
            recommended_count = 6
        elif num_meds <= 8:
            recommended_count = 8
        else:
            recommended_count = 8

        capacity_warning = None
        if num_meds > 8:
            capacity_warning = (
                f"Prescription contains {num_meds} distinct dispenser-supported medications, "
                f"which exceeds the maximum hardware limit of 8 cartridges. "
                f"The first 8 medications have been assigned to cartridges 1-8. "
                f"The remaining {num_meds - 8} medications must be administered manually."
            )

        # Map distinct medicines to slot 1..recommended_count
        assignments: List[Dict[str, Any]] = []
        unassigned: List[str] = []

        for idx, key in enumerate(distinct_names):
            cart_num = idx + 1
            matching_med = next(
                (m for m in supported_meds if f"{m['medicine_name']} {m.get('strength') or ''}".strip() == key),
                None
            )
            if cart_num <= recommended_count:
                assignments.append({
                    "cartridge_number": cart_num,
                    "medicine_name": matching_med["medicine_name"] if matching_med else key,
                    "strength": matching_med.get("strength") if matching_med else None,
                    "dosage_form": matching_med.get("dosage_form", "tablet") if matching_med else "tablet",
                    "requires_manual_loading": True,
                    "suggested_initial_stock": 30  # Caregiver will verify actual physical count
                })
            else:
                unassigned.append(key)

        return {
            "recommended_cartridge_count": recommended_count,
            "total_supported_medicines": num_meds,
            "cartridge_assignments": assignments,
            "unassigned_medicines": unassigned,
            "unsupported_medicines": [
                {
                    "medicine_name": m["medicine_name"],
                    "strength": m.get("strength"),
                    "dosage_form": m.get("dosage_form"),
                    "reason": m.get("unsupported_reason")
                }
                for m in unsupported_meds
            ],
            "capacity_warning": capacity_warning
        }

    @staticmethod
    def propose_schedules(extracted_meds: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Proposes daily schedule occurrences for supported medications.
        Maps frequency to specific times of day and meal relationship.
        """
        schedules: List[Dict[str, Any]] = []

        for med in extracted_meds:
            if not med.get("is_dispenser_supported", True):
                continue

            name = med["medicine_name"]
            timing_hint = med.get("timing_hint", "morning")
            dose_qty = med.get("prescribed_dose_qty", 1)
            meal_timing = med.get("meal_context", "none")

            if timing_hint == "morning":
                schedules.append({
                    "medication_name": name,
                    "time_of_day_label": "morning",
                    "scheduled_time_str": "08:00",
                    "meal_timing": meal_timing if meal_timing != "none" else "with_breakfast",
                    "dose_quantity": dose_qty
                })
            elif timing_hint == "afternoon":
                schedules.append({
                    "medication_name": name,
                    "time_of_day_label": "afternoon",
                    "scheduled_time_str": "13:00",
                    "meal_timing": meal_timing if meal_timing != "none" else "after_lunch",
                    "dose_quantity": dose_qty
                })
            elif timing_hint == "evening":
                schedules.append({
                    "medication_name": name,
                    "time_of_day_label": "evening",
                    "scheduled_time_str": "19:00",
                    "meal_timing": meal_timing if meal_timing != "none" else "with_dinner",
                    "dose_quantity": dose_qty
                })
            elif timing_hint == "bedtime":
                schedules.append({
                    "medication_name": name,
                    "time_of_day_label": "bedtime",
                    "scheduled_time_str": "21:30",
                    "meal_timing": "none",
                    "dose_quantity": dose_qty
                })
            elif timing_hint == "morning_and_evening":
                schedules.append({
                    "medication_name": name,
                    "time_of_day_label": "morning",
                    "scheduled_time_str": "08:00",
                    "meal_timing": "with_breakfast",
                    "dose_quantity": dose_qty
                })
                schedules.append({
                    "medication_name": name,
                    "time_of_day_label": "evening",
                    "scheduled_time_str": "20:00",
                    "meal_timing": "after_dinner",
                    "dose_quantity": dose_qty
                })
            elif timing_hint == "morning_afternoon_evening":
                schedules.append({
                    "medication_name": name,
                    "time_of_day_label": "morning",
                    "scheduled_time_str": "08:00",
                    "meal_timing": "with_breakfast",
                    "dose_quantity": dose_qty
                })
                schedules.append({
                    "medication_name": name,
                    "time_of_day_label": "afternoon",
                    "scheduled_time_str": "13:00",
                    "meal_timing": "with_lunch",
                    "dose_quantity": dose_qty
                })
                schedules.append({
                    "medication_name": name,
                    "time_of_day_label": "evening",
                    "scheduled_time_str": "20:00",
                    "meal_timing": "with_dinner",
                    "dose_quantity": dose_qty
                })

        return schedules

    @staticmethod
    def generate_care_plan_draft(raw_text: str, filename: str = "Pasted Prescription") -> Dict[str, Any]:
        """
        Generates full structured Care Plan Draft JSON from prescription text.
        """
        extracted_meds = PrescriptionIntelligenceService.extract_medications_from_text(raw_text)
        hardware_proposal = PrescriptionIntelligenceService.propose_cartridge_allocation(extracted_meds)
        schedule_proposals = PrescriptionIntelligenceService.propose_schedules(extracted_meds)

        # Extract Doctor or Patient if mentioned
        doctor_match = re.search(r"(?:Dr\.|Doctor)\s+([A-Za-z]+(?:\s+[A-Za-z]+)?)", raw_text)
        patient_match = re.search(r"Patient\s*:\s*([A-Za-z]+(?:\s+[A-Za-z]+)?)", raw_text, re.IGNORECASE)

        return {
            "source_filename": filename,
            "extracted_at": system_clock.now().isoformat(),
            "doctor_name": doctor_match.group(0) if doctor_match else "Prescribing Physician",
            "patient_name": patient_match.group(1).strip() if patient_match else "Eleanor Vance",
            "raw_text": raw_text,
            "extracted_medications": extracted_meds,
            "hardware_proposal": hardware_proposal,
            "proposed_schedules": schedule_proposals,
            "status": "draft"
        }

    @staticmethod
    def create_prescription_with_draft(
        db: Session,
        raw_text: str,
        filename: str,
        file_path: str = ""
    ) -> Prescription:
        """
        Creates a Prescription entity with the structured Care Plan Draft JSON.
        """
        draft = PrescriptionIntelligenceService.generate_care_plan_draft(raw_text, filename)
        draft_str = json.dumps(draft)

        prescription = Prescription(
            filename=filename,
            file_path=file_path or f"virtual://{filename}",
            raw_ocr_text=raw_text,
            review_status="unreviewed",
            draft_json=draft_str,
            extraction_engine=settings.AI_EXTRACTION_PROVIDER,
            uploaded_at=system_clock.now()
        )
        db.add(prescription)
        db.flush()

        # Populate candidate records for backward-compatible queries
        for med in draft["extracted_medications"]:
            candidate = PrescriptionCandidate(
                prescription_id=prescription.id,
                medicine_name=med["medicine_name"],
                strength=med.get("strength"),
                prescribed_dose_qty=med.get("prescribed_dose_qty", 1),
                frequency=med.get("frequency"),
                timing_hint=med.get("timing_hint"),
                meal_instructions=med.get("meal_context"),
                confidence=med.get("confidence", 0.9),
                status="pending",
                notes="; ".join(med.get("warnings", [])) or (med.get("unsupported_reason"))
            )
            db.add(candidate)

        db.commit()
        db.refresh(prescription)
        return prescription
