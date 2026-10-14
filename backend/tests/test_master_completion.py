import pytest
from datetime import datetime
from app.models.models import (
    Medication, Schedule, Cartridge, DoseOccurrence, InventoryTransaction, User
)
from app.services.dose_orchestrator import DoseOrchestrator
from app.services.notification_service import TwilioNotificationProvider
from app.services.clock_service import system_clock

def test_exact_schedule_clock_times_and_prescribed_dose_qty(client, db_session):
    """
    Test creating and retrieving medication with exact clock times (08:30, 20:30),
    accessible time-of-day labels, recurrence, and prescribed_dose_qty (1-5).
    """
    payload = {
        "name": "Metformin Extended Release",
        "strength": "500mg",
        "dosage_form": "tablet",
        "instructions": "Take with breakfast and dinner",
        "meal_context": "with_breakfast",
        "prescribed_dose_qty": 2,
        "low_stock_threshold": 6,
        "is_active": True,
        "schedules": [
            {
                "time_of_day": "08:30",
                "time_of_day_label": "morning",
                "dose_quantity": 2,
                "meal_context": "with_breakfast",
                "recurrence": "daily",
                "start_date": "2026-01-01"
            },
            {
                "time_of_day": "20:30",
                "time_of_day_label": "evening",
                "dose_quantity": 2,
                "meal_context": "with_dinner",
                "recurrence": "daily"
            }
        ]
    }

    res = client.post("/api/medications", json=payload)
    assert res.status_code == 200
    data = res.json()
    assert data["name"] == "Metformin Extended Release"
    assert data["prescribed_dose_qty"] == 2
    assert len(data["schedules"]) == 2

    sched_times = {s["scheduled_time_str"] for s in data["schedules"]}
    assert "08:30" in sched_times
    assert "20:30" in sched_times

    # Verify via GET
    get_res = client.get(f"/api/medications/{data['id']}")
    assert get_res.status_code == 200
    get_data = get_res.json()
    assert get_data["prescribed_dose_qty"] == 2
    assert len(get_data["schedules"]) == 2

def test_human_name_validation_and_medicine_name(client, db_session):
    """
    Test that human names (caregiver/patient) reject digits,
    while medication names allow digits (e.g., Vitamin B12, CoQ10).
    """
    # 1. Caregiver update with digits in name must fail
    bad_caregiver = {
        "name": "Marcus Vance 123",
        "phone": "+91 98765 43210"
    }
    res_bad = client.put("/api/caregiver/settings", json=bad_caregiver)
    assert res_bad.status_code == 422

    # 2. Caregiver update with valid alphabetic name must succeed
    good_caregiver = {
        "name": "Marcus Vance-O'Connor",
        "phone": "+91 98765 43210"
    }
    res_good = client.put("/api/caregiver/settings", json=good_caregiver)
    assert res_good.status_code == 200
    assert res_good.json()["name"] == "Marcus Vance-O'Connor"

    # 3. Medication with numbers in the name (e.g. CoQ10 100mg) must succeed
    med_payload = {
        "name": "CoQ10 Complex 100mg",
        "strength": "100mg",
        "dosage_form": "capsule",
        "instructions": "Take once daily with food",
        "meal_context": "with_food",
        "prescribed_dose_qty": 1
    }
    res_med = client.post("/api/medications", json=med_payload)
    assert res_med.status_code == 200
    assert res_med.json()["name"] == "CoQ10 Complex 100mg"

def test_phone_number_validation_and_e164_normalization(client, db_session):
    """
    Test phone validation:
    - Rejects alphabetic characters.
    - Accepts valid Indian +91 numbers and standard international formats.
    - Twilio provider correctly normalizes numbers to E.164.
    """
    # 1. Alphabetic phone number rejected
    bad_phone = {
        "phone": "+91 98765 ABCDE"
    }
    res_bad = client.put("/api/caregiver/settings", json=bad_phone)
    assert res_bad.status_code == 422

    # 2. Valid +91 phone accepted
    good_phone = {
        "phone": "+91 98765 43210",
        "whatsapp_phone": "+91 98765 43210"
    }
    res_good = client.put("/api/caregiver/settings", json=good_phone)
    assert res_good.status_code == 200

    # 3. Twilio normalization test
    provider = TwilioNotificationProvider()
    clean_india = provider._normalize_e164("+91 98765 43210")
    assert clean_india == "+919876543210"

    clean_us = provider._normalize_e164("+1 (555) 321-4567")
    assert clean_us == "+15553214567"

    clean_plain = provider._normalize_e164("9876543210")
    assert clean_plain == "+919876543210"

def test_safe_medication_archival_and_dependencies(client, db_session):
    """
    Test medication dependency checking, safe deactivation/archival, and reactivation:
    - Draft with no history -> can be hard deleted.
    - Medication with active stock -> blocked from deletion unless force=True.
    - Medication with past doses/transactions -> safely archived (is_active=False).
    - Archived medication can be reactivated.
    """
    # 1. Create a draft medication with no history
    draft_res = client.post("/api/medications", json={
        "name": "Temporary Test Drug",
        "strength": "10mg",
        "instructions": "Draft testing only",
        "meal_context": "none",
        "prescribed_dose_qty": 1
    })
    assert draft_res.status_code == 200
    draft_id = draft_res.json()["id"]

    # Check dependencies
    dep_res = client.get(f"/api/medications/{draft_id}/dependencies")
    assert dep_res.status_code == 200
    dep_data = dep_res.json()
    assert dep_data["can_hard_delete"] is True
    assert dep_data["recommendation"] == "delete"

    # Delete draft
    del_res = client.delete(f"/api/medications/{draft_id}")
    assert del_res.status_code == 200
    assert del_res.json()["status"] == "deleted"

    # Verify it is removed
    assert client.get(f"/api/medications/{draft_id}").status_code == 404

    # 2. Create medication assigned to cartridge with stock
    med_res = client.post("/api/medications", json={
        "name": "Active Stock Drug",
        "strength": "20mg",
        "instructions": "Take daily",
        "meal_context": "with_breakfast",
        "prescribed_dose_qty": 1
    })
    med_id = med_res.json()["id"]

    # Assign to cartridge 1, set stock, and add audit history transaction
    cart = db_session.query(Cartridge).filter(Cartridge.cartridge_number == 1).first()
    if cart:
        cart.medication_id = med_id
        cart.current_stock = 15
        cart.is_configured = True

        tx = InventoryTransaction(
            cartridge_id=cart.id,
            medication_id=med_id,
            delta=15,
            previous_stock=0,
            new_stock=15,
            reason="refill",
            timestamp=datetime.utcnow()
        )
        db_session.add(tx)
        db_session.commit()

    # Check dependencies: should warn of active stock and transactions
    dep_res2 = client.get(f"/api/medications/{med_id}/dependencies")
    assert dep_res2.status_code == 200
    dep_data2 = dep_res2.json()
    assert dep_data2["has_active_cartridge"] is True
    assert dep_data2["current_stock"] == 15
    assert dep_data2["can_hard_delete"] is False

    # Delete without force -> blocked because cartridge still has stock
    del_blocked = client.delete(f"/api/medications/{med_id}")
    assert del_blocked.status_code == 400

    # Delete with force -> safely archived and cartridge freed
    del_forced = client.delete(f"/api/medications/{med_id}?force=true")
    assert del_forced.status_code == 200
    assert del_forced.json()["status"] == "archived"
    assert del_forced.json()["is_active"] is False

    # Verify cartridge is unassigned
    db_session.refresh(cart)
    assert cart.medication_id is None

    # 3. Reactivate medication
    reactivate_res = client.post(f"/api/medications/{med_id}/reactivate")
    assert reactivate_res.status_code == 200
    assert reactivate_res.json()["is_active"] is True

def test_inactive_medication_excluded_from_daily_dose_generation(client, db_session):
    """
    Ensure that inactive medications (is_active=False) do not generate scheduled doses.
    """
    # Create inactive medication and schedule
    med = Medication(
        name="Retired Drug",
        strength="5mg",
        is_active=False,
        prescribed_dose_qty=1
    )
    db_session.add(med)
    db_session.flush()

    sched = Schedule(
        medication_id=med.id,
        scheduled_time_str="12:00",
        time_of_day_label="noon",
        dose_quantity=1,
        is_active=True,
        recurrence="daily"
    )
    db_session.add(sched)
    db_session.commit()

    # Run dose generation for today
    today = system_clock.now().date()
    DoseOrchestrator.generate_daily_doses_if_needed(db_session, target_date=today)

    # Verify no dose was generated for Retired Drug
    retired_doses = db_session.query(DoseOccurrence).filter(
        DoseOccurrence.medication_id == med.id
    ).all()
    assert len(retired_doses) == 0
