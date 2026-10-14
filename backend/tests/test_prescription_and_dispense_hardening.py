import pytest
from datetime import datetime, timedelta
from fastapi.testclient import TestClient
from app.main import app
from app.models.models import DoseOccurrence, Cartridge, Prescription, DeviceState, Schedule
from app.services.clock_service import system_clock
from app.services.prescription_intelligence import PrescriptionIntelligenceService
from app.services.device_service import DeviceService
from app.services.dose_orchestrator import DoseOrchestrator

@pytest.fixture
def client():
    return TestClient(app)

def test_prescription_intelligence_extraction_and_hardware_sizing():
    """
    Test intelligent extraction:
    - Solid oral medications are marked dispenser supported
    - Syrups, creams, inhalers, PRN are flagged unsupported
    - Sizing: <=4 -> 4 cartridges, 5-6 -> 6, 7-8 -> 8, >8 -> warning
    """
    raw_rx = (
        "Rx: Dr. Sarah Bennett, MD\n"
        "Patient: Eleanor Vance | Age: 76\n\n"
        "1. Metformin 500mg - Take 1 tablet twice daily with meals\n"
        "2. Lisinopril 10mg - Take 1 tablet once daily in morning\n"
        "3. Cough Syrup 10ml - Take 10ml twice daily as needed\n"
        "4. Hydrocortisone Cream 1% - Apply thin layer to affected skin at bedtime\n"
        "5. Albuterol Inhaler 90mcg - 2 puffs as needed (PRN) for shortness of breath\n"
        "6. Atorvastatin 20mg - Take 1 tablet at bedtime\n"
    )

    extracted = PrescriptionIntelligenceService.extract_medications_from_text(raw_rx)
    assert len(extracted) >= 5

    # Check Metformin
    met = next(m for m in extracted if "Metformin" in m["medicine_name"])
    assert met["is_dispenser_supported"] is True
    assert met["dosage_form"] == "tablet"
    assert met["strength"] == "500mg"

    # Check Syrup
    syr = next(m for m in extracted if "Syrup" in m["medicine_name"])
    assert syr["is_dispenser_supported"] is False
    assert "liquid" in syr["unsupported_reason"].lower() or "syrup" in syr["unsupported_reason"].lower()

    # Check Cream
    crm = next(m for m in extracted if "Cream" in m["medicine_name"])
    assert crm["is_dispenser_supported"] is False
    assert "topical" in crm["unsupported_reason"].lower() or "cream" in crm["unsupported_reason"].lower()

    # Hardware sizing check
    proposal_3meds = PrescriptionIntelligenceService.propose_cartridge_allocation(extracted)
    # Metformin, Lisinopril, Atorvastatin = 3 supported meds -> 4 cartridges
    assert proposal_3meds["recommended_cartridge_count"] == 4
    assert len(proposal_3meds["cartridge_assignments"]) == 3
    assert proposal_3meds["capacity_warning"] is None

    # Test 6-med and 8-med and >8 capacity warning
    meds_6 = [
        {"medicine_name": f"Pill{i}", "strength": "10mg", "dosage_form": "tablet", "is_dispenser_supported": True}
        for i in range(1, 7)
    ]
    proposal_6 = PrescriptionIntelligenceService.propose_cartridge_allocation(meds_6)
    assert proposal_6["recommended_cartridge_count"] == 6

    meds_9 = [
        {"medicine_name": f"Pill{i}", "strength": "10mg", "dosage_form": "tablet", "is_dispenser_supported": True}
        for i in range(1, 10)
    ]
    proposal_9 = PrescriptionIntelligenceService.propose_cartridge_allocation(meds_9)
    assert proposal_9["recommended_cartridge_count"] == 8
    assert proposal_9["capacity_warning"] is not None
    assert "exceeds" in proposal_9["capacity_warning"].lower()

def test_paste_prescription_and_draft_export(client):
    """
    Test POST /api/prescriptions/paste and GET /api/prescriptions/{id}/export-json
    """
    rx_text = (
        "Rx: Dr. Marcus Evans\n"
        "Patient: Eleanor Vance\n"
        "1. Amlodipine 5mg - Take 1 tablet once daily morning\n"
        "2. Metformin 500mg - Take 1 tablet twice daily with meals\n"
    )
    res = client.post("/api/prescriptions/paste", json={
        "raw_text": rx_text,
        "filename": "Clinical_Intake_Test.txt"
    })
    assert res.status_code == 200
    rx_data = res.json()
    assert rx_data["review_status"] == "unreviewed"
    assert rx_data["draft_json"] is not None
    rx_id = rx_data["id"]

    # Test draft retrieval
    res_draft = client.get(f"/api/prescriptions/{rx_id}/draft")
    assert res_draft.status_code == 200
    draft = res_draft.json()
    assert len(draft["extracted_medications"]) >= 2
    assert draft["hardware_proposal"]["recommended_cartridge_count"] == 4

    # Test JSON download export
    res_exp = client.get(f"/api/prescriptions/{rx_id}/export-json")
    assert res_exp.status_code == 200
    assert "attachment" in res_exp.headers.get("content-disposition", "")
    assert res_exp.headers["content-type"] == "application/json"

def test_guided_setup_physical_loading_and_activation(client, db_session):
    """
    Verify complete 4-step wizard:
    Step 1: Paste/Upload
    Step 2: Review draft & cartridge allocation
    Step 3: Physical loading validation (rejects empty/guess stock or unconfirmed)
    Step 4: Final activation (syncs schedules, does NOT immediate dispense)
    """
    rx_text = (
        "Rx: Dr. Bennett\n"
        "Patient: Eleanor Vance\n"
        "1. Losartan 50mg - Take 1 tablet daily in morning\n"
    )
    res_step1 = client.post("/api/prescriptions/paste", json={"raw_text": rx_text})
    rx_id = res_step1.json()["id"]

    # Step 2: Review draft
    res_step2 = client.post(f"/api/prescriptions/{rx_id}/review-draft", json={
        "prescription_id": rx_id,
        "reviewed_by": "Marcus Vance (Caregiver)",
        "target_cartridge_count": 4,
        "medications": [{"medicine_name": "Losartan", "strength": "50mg", "dosage_form": "tablet"}],
        "schedules": [{"medication_name": "Losartan", "scheduled_time_str": "08:00", "time_of_day_label": "morning", "dose_quantity": 1}],
        "cartridge_assignments": [{"cartridge_number": 1, "medicine_name": "Losartan"}]
    })
    assert res_step2.status_code == 200
    assert res_step2.json()["review_status"] == "schedule_reviewed"

    # Step 3 Failure Case A: Physical checkbox NOT checked
    res_fail1 = client.post(f"/api/prescriptions/{rx_id}/confirm-loading", json={
        "prescription_id": rx_id,
        "loaded_by": "Marcus Vance",
        "cartridge_loads": [{
            "cartridge_number": 1,
            "medication_name": "Losartan",
            "pill_count": 30,
            "confirm_physical_loaded": False  # Must be True
        }]
    })
    assert res_fail1.status_code == 400
    assert "checkbox must be checked" in res_fail1.text.lower()

    # Step 3 Failure Case B: Pill count is 0 or invalid (guessing/defaulting prevented)
    res_fail2 = client.post(f"/api/prescriptions/{rx_id}/confirm-loading", json={
        "prescription_id": rx_id,
        "loaded_by": "Marcus Vance",
        "cartridge_loads": [{
            "cartridge_number": 1,
            "medication_name": "Losartan",
            "pill_count": 0,
            "confirm_physical_loaded": True
        }]
    })
    assert res_fail2.status_code == 422 or res_fail2.status_code == 400

    # Step 3 Success Case: Explicit actual pill count + checked
    res_step3 = client.post(f"/api/prescriptions/{rx_id}/confirm-loading", json={
        "prescription_id": rx_id,
        "loaded_by": "Marcus Vance",
        "cartridge_loads": [{
            "cartridge_number": 1,
            "medication_name": "Losartan",
            "pill_count": 28,
            "confirm_physical_loaded": True
        }]
    })
    assert res_step3.status_code == 200
    assert res_step3.json()["review_status"] == "loaded"

    # Step 4: Final Activation
    res_step4 = client.post(f"/api/prescriptions/{rx_id}/activate", json={
        "prescription_id": rx_id,
        "activated_by": "Marcus Vance",
        "notes": "Verified in person"
    })
    assert res_step4.status_code == 200
    assert res_step4.json()["review_status"] == "confirmed"

    # Verify schedule created
    res_sched = client.get("/api/schedules/")
    losartan_sched = [s for s in res_sched.json() if "Losartan" in s.get("medication_name", "")]
    assert len(losartan_sched) >= 1

def test_simulated_dispensing_vs_physical_dispensing(client, db_session):
    """
    Test difference between simulated dispense and physical dispense:
    1. /simulate-dispense: auto-simulates drop pulses, decrements stock, moves to awaiting_collection.
    2. /dispense: initiates physical dispense (state: dispensing, command_id assigned).
    3. /cancel-dispense: recovers back to scheduled.
    """
    # Find an active scheduled dose
    today = client.get("/api/doses/today").json()
    assert len(today) > 0
    scheduled_doses = [d for d in today if d["status"] in ["scheduled", "pre_dose_reminder"]]
    if not scheduled_doses:
        # Reset one dose for test
        dose_id = today[0]["id"]
        d = db_session.query(DoseOccurrence).filter(DoseOccurrence.id == dose_id).first()
        d.status = "scheduled"
        d.confirmed_pills = 0
        db_session.commit()
    else:
        dose_id = scheduled_doses[0]["id"]

    # 1. Test Simulated Dispense
    res_sim = client.post(f"/api/doses/{dose_id}/simulate-dispense")
    assert res_sim.status_code == 200
    sim_dose = res_sim.json()["dose"]
    assert sim_dose["status"] == "awaiting_collection"
    assert sim_dose["confirmed_pills"] == sim_dose["requested_pills"]

    # 2. Reset/Cancel back to scheduled
    # Since pills were confirmed, cancel preserves them in awaiting_collection
    res_manual = client.post(f"/api/doses/{dose_id}/manual-confirm", json={"confirmed_by": "Patient Eleanor"})
    assert res_manual.status_code == 200
    assert res_manual.json()["dose"]["status"] == "confirmed_taken"

    # Test physical dispense on another dose
    fresh_today = client.get("/api/doses/today").json()
    other_doses = [d for d in fresh_today if d["id"] != dose_id and d["status"] in ["scheduled", "pre_dose_reminder"]]
    if not other_doses:
        p_id = fresh_today[1]["id"]
        d2 = db_session.query(DoseOccurrence).filter(DoseOccurrence.id == p_id).first()
        d2.status = "scheduled"
        d2.confirmed_pills = 0
        db_session.commit()
    else:
        p_id = other_doses[0]["id"]

    res_phys = client.post(f"/api/doses/{p_id}/dispense")
    assert res_phys.status_code == 200
    d_phys = res_phys.json()["dose"]
    assert d_phys["status"] == "dispensing"
    assert d_phys["command_id"] is not None

    # Cancel physical dispense before any drops occur -> safely returns to scheduled!
    res_cancel = client.post(f"/api/doses/{p_id}/cancel-dispense")
    assert res_cancel.status_code == 200
    assert res_cancel.json()["dose"]["status"] == "scheduled"


def test_truthful_connectivity_and_mode_switching(client):
    """
    Verify truthful connectivity model:
    - In Simulated mode: status is demo_simulated, badge is Demo Mode (Simulated)
    - In Physical mode: reports physical_online or physical_stale/offline
    """
    # Switch to simulated mode
    res_sim = client.post("/api/device/mode", json={"mode": "simulated"})
    assert res_sim.status_code == 200
    data_sim = res_sim.json()
    assert data_sim["status"] == "demo_simulated"
    assert "Demo Mode" in data_sim["badge_label"]
    assert data_sim["is_simulated"] is True

    # Check GET /connectivity
    res_conn = client.get("/api/device/connectivity")
    assert res_conn.status_code == 200
    assert res_conn.json()["status"] == "demo_simulated"

    # Switch to physical mode
    res_phys = client.post("/api/device/mode", json={"mode": "physical"})
    assert res_phys.status_code == 200
    data_phys = res_phys.json()
    assert data_phys["is_simulated"] is False
    assert data_phys["status"] in ["physical_online", "physical_stale", "physical_offline"]

    # Switch back to simulated mode
    client.post("/api/device/mode", json={"mode": "simulated"})
