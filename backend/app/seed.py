from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from app.models.models import (
    User, Medication, Cartridge, Schedule, DoseOccurrence,
    DispensingOperation, InventoryTransaction, DeviceState,
    Prescription, PrescriptionCandidate
)
from app.services.clock_service import system_clock

def seed_database(db: Session):
    # Only seed if empty
    if db.query(User).count() > 0:
        return

    now = system_clock.now()

    # 1. Users
    patient = User(
        name="Eleanor Vance",
        role="patient",
        phone="+91 98765 23456",
        email="eleanor.vance@carenet.org",
        notification_channel="simulated",
        timezone="Asia/Kolkata",
        created_at=now - timedelta(days=30)
    )
    caregiver = User(
        name="Marcus Vance",
        role="caregiver",
        phone="+91 98765 43210",
        whatsapp_phone="+91 98765 43210",
        email="marcus.vance@familycare.org",
        notification_channel="simulated",
        timezone="Asia/Kolkata",
        created_at=now - timedelta(days=30)
    )
    db.add_all([patient, caregiver])
    db.flush()

    # 2. Medications
    med1 = Medication(
        name="Metformin",
        strength="500mg",
        dosage_form="tablet",
        instructions="Take with meals to minimize gastrointestinal discomfort.",
        meal_context="with_breakfast",
        low_stock_threshold=5,
        is_active=True,
        created_at=now - timedelta(days=20)
    )
    med2 = Medication(
        name="Lisinopril",
        strength="10mg",
        dosage_form="tablet",
        instructions="Take once daily in the morning before food.",
        meal_context="before_breakfast",
        low_stock_threshold=5,
        is_active=True,
        created_at=now - timedelta(days=20)
    )
    med3 = Medication(
        name="Atorvastatin",
        strength="20mg",
        dosage_form="tablet",
        instructions="Take in the evening or bedtime.",
        meal_context="none",
        low_stock_threshold=5,
        is_active=True,
        created_at=now - timedelta(days=20)
    )
    med4 = Medication(
        name="Vitamin D3",
        strength="1000 IU",
        dosage_form="capsule",
        instructions="Daily bone and immune support supplement.",
        meal_context="with_lunch",
        low_stock_threshold=5,
        is_active=True,
        created_at=now - timedelta(days=20)
    )
    db.add_all([med1, med2, med3, med4])
    db.flush()

    # 3. Four Cartridges
    cart1 = Cartridge(
        cartridge_number=1,
        medication_id=med1.id,
        current_stock=24,
        capacity=30,
        low_stock_threshold=5,
        is_configured=True,
        last_refilled_at=now - timedelta(days=5),
        calibration_offset_deg=0.0
    )
    cart2 = Cartridge(
        cartridge_number=2,
        medication_id=med2.id,
        current_stock=18,
        capacity=30,
        low_stock_threshold=5,
        is_configured=True,
        last_refilled_at=now - timedelta(days=5),
        calibration_offset_deg=90.0
    )
    cart3 = Cartridge(
        cartridge_number=3,
        medication_id=med3.id,
        current_stock=4,  # Intentionally low stock to demonstrate alert!
        capacity=30,
        low_stock_threshold=5,
        is_configured=True,
        last_refilled_at=now - timedelta(days=15),
        calibration_offset_deg=180.0
    )
    cart4 = Cartridge(
        cartridge_number=4,
        medication_id=med4.id,
        current_stock=20,
        capacity=30,
        low_stock_threshold=5,
        is_configured=True,
        last_refilled_at=now - timedelta(days=7),
        calibration_offset_deg=270.0
    )
    db.add_all([cart1, cart2, cart3, cart4])
    db.flush()

    # Record initial inventory load transactions
    for c in [cart1, cart2, cart3, cart4]:
        tx = InventoryTransaction(
            cartridge_id=c.id,
            medication_id=c.medication_id,
            delta=c.current_stock,
            previous_stock=0,
            new_stock=c.current_stock,
            reason="refill",
            timestamp=now - timedelta(days=5)
        )
        db.add(tx)

    # 4. Schedules
    s1 = Schedule(
        medication_id=med1.id,
        time_of_day_label="morning",
        scheduled_time_str="08:00",
        meal_timing="with_breakfast",
        dose_quantity=1,
        is_active=True,
        created_at=now - timedelta(days=10)
    )
    s2 = Schedule(
        medication_id=med2.id,
        time_of_day_label="morning",
        scheduled_time_str="08:00",
        meal_timing="before_breakfast",
        dose_quantity=1,
        is_active=True,
        created_at=now - timedelta(days=10)
    )
    s3 = Schedule(
        medication_id=med4.id,
        time_of_day_label="afternoon",
        scheduled_time_str="13:00",
        meal_timing="with_lunch",
        dose_quantity=1,
        is_active=True,
        created_at=now - timedelta(days=10)
    )
    s4 = Schedule(
        medication_id=med3.id,
        time_of_day_label="bedtime",
        scheduled_time_str="21:30",
        meal_timing="none",
        dose_quantity=2,  # Prescribed 2 tablets (for 2-tablet demo!)
        is_active=True,
        created_at=now - timedelta(days=10)
    )
    db.add_all([s1, s2, s3, s4])
    db.flush()

    # 5. Device State
    dev = DeviceState(
        device_id="ESP32_PILLBOX_01",
        is_online=True,
        last_heartbeat=now,
        firmware_version="v1.0.0-idp",
        current_led_pattern="OFF",
        current_buzzer_pattern="SILENT",
        is_simulated=True,
        updated_at=now
    )
    db.add(dev)

    # 6. Sample Prescription
    rx = Prescription(
        filename="Eleanor_Vance_Rx_Oct2026.txt",
        file_path="/uploads/sample_rx.txt",
        raw_ocr_text=(
            "Metropolitan Geriatric Center\n"
            "Physician: Dr. Sarah Bennett, MD | DEA: AB1234567\n"
            "Patient: Eleanor Vance | DOB: 03/12/1948\n\n"
            "1. Metformin 500mg - 1 tab PO BID with meals\n"
            "2. Lisinopril 10mg - 1 tab PO daily in AM before breakfast\n"
            "3. Atorvastatin 20mg - 2 tabs PO QHS at bedtime\n"
            "4. Vitamin D3 1000 IU - 1 cap PO daily with lunch\n"
        ),
        review_status="confirmed",
        reviewed_by="Marcus Vance (Verified Caregiver)",
        reviewed_at=now - timedelta(days=10),
        uploaded_at=now - timedelta(days=10)
    )
    db.add(rx)
    db.flush()

    cand1 = PrescriptionCandidate(
        prescription_id=rx.id,
        medicine_name="Metformin",
        strength="500mg",
        prescribed_dose_qty=1,
        frequency="Twice daily",
        timing_hint="morning",
        meal_instructions="with_breakfast",
        confidence=0.95,
        status="accepted"
    )
    cand2 = PrescriptionCandidate(
        prescription_id=rx.id,
        medicine_name="Lisinopril",
        strength="10mg",
        prescribed_dose_qty=1,
        frequency="Once daily",
        timing_hint="morning",
        meal_instructions="before_breakfast",
        confidence=0.92,
        status="accepted"
    )
    cand3 = PrescriptionCandidate(
        prescription_id=rx.id,
        medicine_name="Atorvastatin",
        strength="20mg",
        prescribed_dose_qty=2,
        frequency="Once daily at bedtime",
        timing_hint="bedtime",
        meal_instructions="none",
        confidence=0.88,
        status="accepted"
    )
    cand4 = PrescriptionCandidate(
        prescription_id=rx.id,
        medicine_name="Vitamin D3",
        strength="1000 IU",
        prescribed_dose_qty=1,
        frequency="Once daily",
        timing_hint="afternoon",
        meal_instructions="with_lunch",
        confidence=0.90,
        status="accepted"
    )
    db.add_all([cand1, cand2, cand3, cand4])

    # 7. Today's Doses
    today_y, today_m, today_d = now.year, now.month, now.day

    # Dose 1: Metformin (08:00 AM) - Confirmed and Collected earlier today
    d1 = DoseOccurrence(
        schedule_id=s1.id,
        medication_id=med1.id,
        cartridge_id=cart1.id,
        scheduled_for=datetime(today_y, today_m, today_d, 8, 0),
        scheduled_time_local="08:00",
        meal_context_snapshot="with_breakfast",
        requested_pills=1,
        confirmed_pills=1,
        status="collected",
        dispensed_at=datetime(today_y, today_m, today_d, 8, 1),
        collected_at=datetime(today_y, today_m, today_d, 8, 3),
        created_at=datetime(today_y, today_m, today_d, 6, 0)
    )

    # Dose 2: Lisinopril (08:00 AM) - Confirmed and Collected earlier today
    d2 = DoseOccurrence(
        schedule_id=s2.id,
        medication_id=med2.id,
        cartridge_id=cart2.id,
        scheduled_for=datetime(today_y, today_m, today_d, 8, 0),
        scheduled_time_local="08:00",
        meal_context_snapshot="before_breakfast",
        requested_pills=1,
        confirmed_pills=1,
        status="collected",
        dispensed_at=datetime(today_y, today_m, today_d, 8, 1),
        collected_at=datetime(today_y, today_m, today_d, 8, 3),
        created_at=datetime(today_y, today_m, today_d, 6, 0)
    )

    # Dose 3: Vitamin D3 (13:00 PM) - Confirmed and Collected
    d3 = DoseOccurrence(
        schedule_id=s3.id,
        medication_id=med4.id,
        cartridge_id=cart4.id,
        scheduled_for=datetime(today_y, today_m, today_d, 13, 0),
        scheduled_time_local="13:00",
        meal_context_snapshot="with_lunch",
        requested_pills=1,
        confirmed_pills=1,
        status="collected",
        dispensed_at=datetime(today_y, today_m, today_d, 13, 1),
        collected_at=datetime(today_y, today_m, today_d, 13, 4),
        created_at=datetime(today_y, today_m, today_d, 6, 0)
    )

    # Dose 4: Atorvastatin (21:30 PM) - Scheduled, ready to be tested!
    d4 = DoseOccurrence(
        schedule_id=s4.id,
        medication_id=med3.id,
        cartridge_id=cart3.id,
        scheduled_for=datetime(today_y, today_m, today_d, 21, 30),
        scheduled_time_local="21:30",
        meal_context_snapshot="none",
        requested_pills=2,  # 2 tablets requested!
        confirmed_pills=0,
        status="scheduled",
        created_at=datetime(today_y, today_m, today_d, 6, 0)
    )

    db.add_all([d1, d2, d3, d4])
    db.commit()
