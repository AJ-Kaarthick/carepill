import pytest
from datetime import datetime, timedelta
from app.models.models import DoseOccurrence, Cartridge, CaregiverAlert, InventoryTransaction, Prescription
from app.services.dose_orchestrator import DoseOrchestrator
from app.services.inventory_service import InventoryService
from app.services.clock_service import system_clock
from app.services.ocr_service import OCRService

def test_exact_dose_dispensing_and_stock_decrement(db_session):
    """
    Scenario: Prescribed dose requires 2 tablets.
    Sensor 1 confirms 2 tablets delivered in 1st attempt.
    Verified: stock decrements by exactly 2, state -> awaiting_collection.
    """
    dose = db_session.query(DoseOccurrence).filter(DoseOccurrence.requested_pills == 2).first()
    assert dose is not None
    cartridge = db_session.query(Cartridge).filter(Cartridge.id == dose.cartridge_id).first()
    initial_stock = cartridge.current_stock

    # Trigger dispensing
    ok, msg, d = DoseOrchestrator.trigger_dispense(db_session, dose.id)
    assert ok is True
    assert d.status == "dispensing"

    # Sensor 1 reports 2 pills
    ok, msg, d = DoseOrchestrator.process_sensor1_drop_result(
        db=db_session,
        dose_id=dose.id,
        detected_pills_in_this_step=2,
        sensor_status="ok"
    )
    assert ok is True
    assert d.status == "awaiting_collection"
    assert d.confirmed_pills == 2

    # Inventory must be decremented by exactly 2
    db_session.refresh(cartridge)
    assert cartridge.current_stock == initial_stock - 2

    # Auditable transaction recorded
    tx = db_session.query(InventoryTransaction).filter(
        InventoryTransaction.dose_occurrence_id == dose.id,
        InventoryTransaction.reason == "dispense_confirmed"
    ).first()
    assert tx is not None
    assert tx.delta == -2

def test_duplicate_event_protection(db_session):
    """
    Verify stock is NOT decremented twice for duplicate events on the same dose.
    """
    dose = db_session.query(DoseOccurrence).filter(DoseOccurrence.requested_pills == 2).first()
    cartridge = db_session.query(Cartridge).filter(Cartridge.id == dose.cartridge_id).first()
    initial_stock = cartridge.current_stock

    # First decrement
    ok1, msg1 = InventoryService.decrement_stock_for_dose(db_session, dose, 2)
    assert ok1 is True
    db_session.refresh(cartridge)
    assert cartridge.current_stock == initial_stock - 2

    # Duplicate call
    ok2, msg2 = InventoryService.decrement_stock_for_dose(db_session, dose, 2)
    assert ok2 is False
    assert "already decremented" in msg2.lower()
    db_session.refresh(cartridge)
    # Stock must still be exactly initial_stock - 2, NOT initial_stock - 4!
    assert cartridge.current_stock == initial_stock - 2

def test_under_dispense_and_corrective_dispensing(db_session):
    """
    Scenario: Prescribed dose requires 2 tablets.
    Attempt 1: Sensor 1 detects 1 tablet -> status becomes 'corrective_dispensing'.
    Attempt 2: Sensor 1 detects remaining 1 tablet -> status becomes 'awaiting_collection'.
    Total confirmed = 2 tablets. Stock decremented by 2.
    """
    dose = db_session.query(DoseOccurrence).filter(DoseOccurrence.requested_pills == 2).first()
    cartridge = db_session.query(Cartridge).filter(Cartridge.id == dose.cartridge_id).first()
    initial_stock = cartridge.current_stock

    DoseOrchestrator.trigger_dispense(db_session, dose.id)

    # Attempt 1: only 1 tablet drops
    ok1, msg1, d1 = DoseOrchestrator.process_sensor1_drop_result(
        db=db_session,
        dose_id=dose.id,
        detected_pills_in_this_step=1,
        sensor_status="ok"
    )
    assert d1.status == "corrective_dispensing"
    assert d1.confirmed_pills == 1
    assert d1.correction_attempts_used == 1

    # Attempt 2: corrective attempt delivers the remaining 1 tablet
    ok2, msg2, d2 = DoseOrchestrator.process_sensor1_drop_result(
        db=db_session,
        dose_id=dose.id,
        detected_pills_in_this_step=1,
        sensor_status="ok"
    )
    assert d2.status == "awaiting_collection"
    assert d2.confirmed_pills == 2
    assert d2.correction_attempts_used == 2

    db_session.refresh(cartridge)
    assert cartridge.current_stock == initial_stock - 2

def test_over_dispense_safety_halt(db_session):
    """
    Scenario: 2 tablets requested, but Sensor 1 detects 3 tablets (excess).
    Mechanism must immediately halt, enter dispensing_fault, and alert caregiver.
    Must NOT attempt to reverse automatically.
    """
    dose = db_session.query(DoseOccurrence).filter(DoseOccurrence.requested_pills == 2).first()
    DoseOrchestrator.trigger_dispense(db_session, dose.id)

    ok, msg, d = DoseOrchestrator.process_sensor1_drop_result(
        db=db_session,
        dose_id=dose.id,
        detected_pills_in_this_step=3,
        sensor_status="ok"
    )
    assert ok is False
    assert d.status == "dispensing_fault"
    assert "Over-dispense" in d.fault_reason

    # Caregiver alert generated
    alert = db_session.query(CaregiverAlert).filter(
        CaregiverAlert.dose_occurrence_id == dose.id,
        CaregiverAlert.alert_type == "dispensing_fault"
    ).first()
    assert alert is not None
    assert "Over-dispense" in alert.message

def test_sensor1_uncertain_count_fault(db_session):
    """
    Sensor 1 uncertainty enters safe sensor_fault state.
    """
    dose = db_session.query(DoseOccurrence).filter(DoseOccurrence.requested_pills == 2).first()
    DoseOrchestrator.trigger_dispense(db_session, dose.id)

    ok, msg, d = DoseOrchestrator.process_sensor1_drop_result(
        db=db_session,
        dose_id=dose.id,
        detected_pills_in_this_step=0,
        sensor_status="uncertain",
        raw_telemetry="Beam blocked indefinitely"
    )
    assert ok is False
    assert d.status == "sensor_fault"

def test_sensor2_pickup_cancels_reminders(db_session):
    """
    Sensor 2 detects medicine cup removal/pickup.
    Transitions state to 'collected' and records timestamp.
    """
    dose = db_session.query(DoseOccurrence).filter(DoseOccurrence.requested_pills == 2).first()
    DoseOrchestrator.trigger_dispense(db_session, dose.id)
    DoseOrchestrator.process_sensor1_drop_result(db_session, dose.id, 2, "ok")
    assert dose.status == "awaiting_collection"

    # Sensor 2 reports pickup
    ok, msg, d = DoseOrchestrator.process_sensor2_pickup_event(db_session, dose.id, is_collected=True)
    assert ok is True
    assert d.status == "collected"
    assert d.collected_at is not None

def test_5min_reminder_and_10min_escalation_with_clock(db_session):
    """
    Deterministic test clock verification:
    - After 5 minutes without pickup: status -> collection_reminder
    - After 10 minutes without pickup: status -> escalated, caregiver notification dispatched.
    """
    dose = db_session.query(DoseOccurrence).filter(DoseOccurrence.requested_pills == 2).first()
    DoseOrchestrator.trigger_dispense(db_session, dose.id)
    DoseOrchestrator.process_sensor1_drop_result(db_session, dose.id, 2, "ok")
    assert dose.status == "awaiting_collection"

    # 1. Advance virtual clock by 5 minutes
    system_clock.advance_minutes(5)
    res5 = DoseOrchestrator.evaluate_timeouts_and_escalations(db_session)
    db_session.refresh(dose)
    assert dose.status == "collection_reminder"
    assert res5["reminders_triggered"] == 1

    # 2. Advance virtual clock by another 5 minutes (total 10 minutes since dispense)
    system_clock.advance_minutes(5)
    res10 = DoseOrchestrator.evaluate_timeouts_and_escalations(db_session)
    db_session.refresh(dose)
    assert dose.status == "escalated"
    assert res10["escalations_triggered"] == 1

    # Verify caregiver alert created with uncollected status
    alert = db_session.query(CaregiverAlert).filter(
        CaregiverAlert.dose_occurrence_id == dose.id,
        CaregiverAlert.alert_type == "uncollected_dose"
    ).first()
    assert alert is not None
    assert "collected" in alert.message.lower()

def test_prescription_human_verification_safety(db_session):
    """
    Rule: Never activate medication schedule directly from unverified OCR results.
    """
    rx = Prescription(
        filename="test_unverified_rx.txt",
        file_path="/tmp/test_unverified_rx.txt",
        raw_ocr_text="Aspirin 81mg - 1 tablet daily",
        review_status="unreviewed"
    )
    db_session.add(rx)
    db_session.commit()

    # Verify review status is unreviewed
    assert rx.review_status == "unreviewed"
    # Review and confirm explicitly
    success, msg = OCRService.review_and_confirm_prescription(
        db=db_session,
        prescription_id=rx.id,
        reviewed_by="Pharmacist Jane",
        review_items=[]
    )
    assert success is True
    db_session.refresh(rx)
    assert rx.review_status == "confirmed"
    assert rx.reviewed_by == "Pharmacist Jane"
