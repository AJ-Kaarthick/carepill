import pytest
from datetime import timedelta
from unittest.mock import patch, MagicMock
from app.models.models import (
    Cartridge, Medication, DoseOccurrence, DeviceState,
    CaregiverAlert, User, InventoryTransaction
)
from app.services.device_service import DeviceService
from app.services.dose_orchestrator import DoseOrchestrator
from app.services.inventory_service import InventoryService
from app.services.notification_service import NotificationService, TwilioNotificationProvider
from app.services.clock_service import system_clock
from app.config import settings

def test_default_4_cartridges_and_expansion_to_6_and_8(client, db_session):
    """
    CarePill hardware specification:
    - Default cartridge count: 4.
    - Additional supported: 6 and 8.
    """
    dev = DeviceService.get_or_create_device(db_session, "ESP32_PILLBOX_01")
    assert dev.cartridge_count == 4

    cartridges = db_session.query(Cartridge).filter(Cartridge.device_id == "ESP32_PILLBOX_01").all()
    assert len(cartridges) == 4

    # 1. Expand to 6 cartridges via API
    res6 = client.post("/api/device/configure-hardware", json={
        "device_id": "ESP32_PILLBOX_01",
        "cartridge_count": 6
    })
    assert res6.status_code == 200
    assert res6.json()["cartridge_count"] == 6

    carts6 = db_session.query(Cartridge).filter(Cartridge.device_id == "ESP32_PILLBOX_01").all()
    assert len(carts6) == 6
    cart6_numbers = {c.cartridge_number for c in carts6}
    assert cart6_numbers == {1, 2, 3, 4, 5, 6}

    # 2. Expand to 8 cartridges via API
    res8 = client.post("/api/device/configure-hardware", json={
        "device_id": "ESP32_PILLBOX_01",
        "cartridge_count": 8
    })
    assert res8.status_code == 200
    assert res8.json()["cartridge_count"] == 8

    carts8 = db_session.query(Cartridge).filter(Cartridge.device_id == "ESP32_PILLBOX_01").all()
    assert len(carts8) == 8

def test_device_isolation_between_multiple_patients(client, db_session):
    """
    Verify that 4-, 6-, and 8-cartridge patient dispensers exist independently
    without sharing assignments or inventory.
    """
    # Create 3 distinct devices
    DeviceService.get_or_create_device(db_session, "DEVICE_PATIENT_4", default_cartridge_count=4)
    DeviceService.get_or_create_device(db_session, "DEVICE_PATIENT_6", default_cartridge_count=6)
    DeviceService.get_or_create_device(db_session, "DEVICE_PATIENT_8", default_cartridge_count=8)

    med = db_session.query(Medication).first()
    assert med is not None

    # Configure Slot 1 on DEVICE_PATIENT_4 with medication and 20 pills
    client.post("/api/cartridges/setup", json={
        "cartridge_number": 1,
        "device_id": "DEVICE_PATIENT_4",
        "medication_id": med.id,
        "initial_stock": 20,
        "low_stock_threshold": 5,
        "confirm_physical_loaded": True
    })

    # Configure Slot 1 on DEVICE_PATIENT_8 with 5 pills
    client.post("/api/cartridges/setup", json={
        "cartridge_number": 1,
        "device_id": "DEVICE_PATIENT_8",
        "medication_id": med.id,
        "initial_stock": 5,
        "low_stock_threshold": 5,
        "confirm_physical_loaded": True
    })

    # Query cartridges for each device
    res4 = client.get("/api/cartridges/?device_id=DEVICE_PATIENT_4").json()
    res6 = client.get("/api/cartridges/?device_id=DEVICE_PATIENT_6").json()
    res8 = client.get("/api/cartridges/?device_id=DEVICE_PATIENT_8").json()

    assert len(res4) == 4
    assert len(res6) == 6
    assert len(res8) == 8

    # Stock check for Slot 1 across devices
    assert res4[0]["current_stock"] == 20
    assert res6[0]["current_stock"] == 0  # Unconfigured
    assert res8[0]["current_stock"] == 5

    # Refill DEVICE_PATIENT_6 Slot 1 with 12 pills
    client.post("/api/cartridges/refill", json={
        "cartridge_number": 1,
        "device_id": "DEVICE_PATIENT_6",
        "added_pills": 12,
        "notes": "Patient 6 refill"
    })

    c4 = db_session.query(Cartridge).filter(Cartridge.device_id == "DEVICE_PATIENT_4", Cartridge.cartridge_number == 1).first()
    c6 = db_session.query(Cartridge).filter(Cartridge.device_id == "DEVICE_PATIENT_6", Cartridge.cartridge_number == 1).first()
    c8 = db_session.query(Cartridge).filter(Cartridge.device_id == "DEVICE_PATIENT_8", Cartridge.cartridge_number == 1).first()

    assert c4.current_stock == 20  # Completely untouched
    assert c6.current_stock == 12  # Updated
    assert c8.current_stock == 5   # Untouched

def test_safe_downsizing_prevented_when_stocked_or_assigned(client, db_session):
    """
    Safe hardware reconfiguration:
    Attempting to downsize from 8 to 4 when slots 5-8 have medication or stock
    must fail unless force=True.
    """
    dev_id = "ESP32_DOWNSIZE_TEST"
    DeviceService.get_or_create_device(db_session, dev_id, default_cartridge_count=8)

    med = db_session.query(Medication).first()

    # Load stock into cartridge 6
    cart6 = db_session.query(Cartridge).filter(Cartridge.device_id == dev_id, Cartridge.cartridge_number == 6).first()
    cart6.medication_id = med.id
    cart6.current_stock = 15
    cart6.is_configured = True
    db_session.commit()

    # Attempt to downsize to 4 without force
    res_fail = client.post("/api/device/configure-hardware", json={
        "device_id": dev_id,
        "cartridge_count": 4,
        "force": False
    })
    assert res_fail.status_code == 400
    detail = res_fail.json()["detail"]
    assert detail["requires_confirmation"] is True
    assert any(c["cartridge_number"] == 6 for c in detail["affected_cartridges"])

    # Device remains at 8 cartridges
    dev = db_session.query(DeviceState).filter(DeviceState.device_id == dev_id).first()
    assert dev.cartridge_count == 8

    # Now confirm downsize with force=True
    res_ok = client.post("/api/device/configure-hardware", json={
        "device_id": dev_id,
        "cartridge_count": 4,
        "force": True
    })
    assert res_ok.status_code == 200
    db_session.refresh(dev)
    assert dev.cartridge_count == 4

def test_all_four_reminder_timings_deterministic_clock(client, db_session):
    """
    Verify all 4 reminder timings based on virtual clock:
    1. Pre-dose -10m (-10m)
    2. Pre-dose -5m (-5m)
    3. Post-dispense +5m collection reminder
    4. Post-dispense +10m caregiver escalation
    """
    med = db_session.query(Medication).first()
    cart = db_session.query(Cartridge).filter(Cartridge.device_id == "ESP32_PILLBOX_01", Cartridge.cartridge_number == 1).first()
    cart.medication_id = med.id
    cart.current_stock = 20
    cart.is_configured = True
    db_session.commit()

    now = system_clock.now()

    # Create dose scheduled exactly 11 minutes in the future
    dose = DoseOccurrence(
        medication_id=med.id,
        cartridge_id=cart.id,
        scheduled_for=now + timedelta(minutes=11),
        scheduled_time_local="12:00",
        requested_pills=1,
        confirmed_pills=0,
        status="scheduled",
        created_at=now
    )
    db_session.add(dose)
    db_session.commit()
    db_session.refresh(dose)

    # Time 0: 11m before -> no reminders yet
    res0 = DoseOrchestrator.evaluate_timeouts_and_escalations(db_session)
    db_session.refresh(dose)
    assert dose.status == "scheduled"
    assert res0["pre_dose_reminders_triggered"] == 0

    # 1. Advance virtual clock by 2 minutes (now 9m before scheduled -> in -10m window)
    system_clock.advance_minutes(2)
    res_10m = DoseOrchestrator.evaluate_timeouts_and_escalations(db_session)
    db_session.refresh(dose)
    assert dose.status == "pre_dose_reminder"
    assert dose.pre_dose_10m_sent_at is not None
    assert res_10m["pre_dose_reminders_triggered"] == 1

    # 2. Advance clock by 5 minutes (now 4m before scheduled -> in -5m window)
    system_clock.advance_minutes(5)
    res_5m = DoseOrchestrator.evaluate_timeouts_and_escalations(db_session)
    db_session.refresh(dose)
    assert dose.status == "pre_dose_reminder"
    assert dose.pre_dose_5m_sent_at is not None
    assert res_5m["pre_dose_reminders_triggered"] == 1

    # 3. Advance to scheduled time and trigger dispense
    system_clock.advance_minutes(4)
    DoseOrchestrator.trigger_dispense(db_session, dose.id)
    DoseOrchestrator.process_sensor1_drop_result(db_session, dose.id, 1, "ok")
    db_session.refresh(dose)
    assert dose.status == "awaiting_collection"

    # 4. Advance clock by 5 minutes uncollected -> +5m Collection Reminder
    system_clock.advance_minutes(5)
    res_rem = DoseOrchestrator.evaluate_timeouts_and_escalations(db_session)
    db_session.refresh(dose)
    assert dose.status == "collection_reminder"
    assert res_rem["reminders_triggered"] == 1

    # 5. Advance clock by another 5 minutes (total 10m uncollected) -> +10m Escalation
    system_clock.advance_minutes(5)
    res_esc = DoseOrchestrator.evaluate_timeouts_and_escalations(db_session)
    db_session.refresh(dose)
    assert dose.status == "escalated"
    assert res_esc["escalations_triggered"] == 1

    # Verify escalation alert text adheres to minimal specification:
    alert = db_session.query(CaregiverAlert).filter(
        CaregiverAlert.dose_occurrence_id == dose.id,
        CaregiverAlert.alert_type == "uncollected_dose"
    ).first()
    assert alert is not None
    assert "CarePill alert: A scheduled medication has not been collected." in alert.message
    assert "Please check on the patient." in alert.message

def test_sensor2_pickup_cancels_reminders_and_escalations(db_session):
    """
    Sensor 2 cup pickup confirms patient took the medication and cancels pending alerts.
    """
    med = db_session.query(Medication).first()
    cart = db_session.query(Cartridge).filter(Cartridge.cartridge_number == 1).first()

    dose = DoseOccurrence(
        medication_id=med.id,
        cartridge_id=cart.id,
        scheduled_for=system_clock.now(),
        scheduled_time_local="10:00",
        requested_pills=2,
        confirmed_pills=2,
        status="awaiting_collection",
        dispensed_at=system_clock.now(),
        created_at=system_clock.now()
    )
    db_session.add(dose)
    db_session.commit()

    # Sensor 2 reports patient cup pickup
    success, msg, d = DoseOrchestrator.process_sensor2_pickup_event(db_session, dose.id, is_collected=True)
    assert success is True
    assert d.status == "collected"
    assert d.collected_at is not None

    # Advance clock by 30 minutes
    system_clock.advance_minutes(30)
    res = DoseOrchestrator.evaluate_timeouts_and_escalations(db_session)
    assert res["reminders_triggered"] == 0
    assert res["escalations_triggered"] == 0

    # No alerts generated
    alert = db_session.query(CaregiverAlert).filter(CaregiverAlert.dose_occurrence_id == dose.id).first()
    assert alert is None

def test_caregiver_settings_and_test_notification_api(client, db_session):
    """
    Verify GET /api/caregiver/settings, PUT /api/caregiver/settings,
    and POST /api/caregiver/test-notification.
    """
    # 1. GET settings
    get_res = client.get("/api/caregiver/settings")
    assert get_res.status_code == 200
    data = get_res.json()
    assert data["role"] == "caregiver"

    # 2. PUT settings (enable SMS and WhatsApp consent, set phone numbers)
    put_res = client.put("/api/caregiver/settings", json={
        "phone": "+1 (555) 321-4567",
        "whatsapp_phone": "+1 (555) 321-4567",
        "notification_channel": "whatsapp",
        "sms_consent": True,
        "whatsapp_consent": True
    })
    assert put_res.status_code == 200
    updated = put_res.json()
    assert updated["notification_channel"] == "whatsapp"
    assert updated["sms_consent"] is True
    assert updated["whatsapp_consent"] is True
    assert updated["whatsapp_phone"] == "+1 (555) 321-4567"

    # 3. POST test-notification (simulated channel)
    test_res = client.post("/api/caregiver/test-notification", json={
        "channel": "simulated",
        "custom_message": "Test verification alert"
    })
    assert test_res.status_code == 200
    t_data = test_res.json()
    assert t_data["delivery_status"] == "simulated"
    assert t_data["channel"] == "simulated"
    assert "Test verification alert" in t_data["message"]

def test_consent_gating_for_sms_and_whatsapp_with_twilio(db_session):
    """
    Explicit caregiver consent requirement:
    Under Twilio provider, if sms_consent or whatsapp_consent is False,
    the alert is blocked and recorded as delivery_status='failed'.
    """
    caregiver = db_session.query(User).filter(User.role == "caregiver").first()
    caregiver.sms_consent = False
    caregiver.whatsapp_consent = False
    db_session.commit()

    with patch.object(settings, "NOTIFICATION_PROVIDER", "twilio"):
        # Attempt SMS without consent
        alert_sms = NotificationService.dispatch_caregiver_alert(
            db=db_session,
            alert_type="consent_check_sms",
            channel_override="sms"
        )
        assert alert_sms.delivery_status == "failed"
        assert "SMS opt-in consent" in alert_sms.provider_response

        # Attempt WhatsApp without consent
        alert_wa = NotificationService.dispatch_caregiver_alert(
            db=db_session,
            alert_type="consent_check_wa",
            channel_override="whatsapp"
        )
        assert alert_wa.delivery_status == "failed"
        assert "WhatsApp opt-in consent" in alert_wa.provider_response

def test_twilio_whatsapp_formatting_and_prefix(db_session):
    """
    Verifies Twilio WhatsApp formatting uses 'whatsapp:' prefix for both From and To.
    """
    provider = TwilioNotificationProvider()

    with patch.object(settings, "TWILIO_ACCOUNT_SID", "ACtest123456789"), \
         patch.object(settings, "TWILIO_AUTH_TOKEN", "authtesttoken123"), \
         patch.object(settings, "TWILIO_WHATSAPP_FROM", "whatsapp:+14155238886"), \
         patch("httpx.post") as mock_post:

        mock_post.return_value = MagicMock(
            status_code=201,
            json=lambda: {"sid": "SMtestmessage123"}
        )

        status, sid, resp = provider.send(
            recipient="+15559876543",
            alert_type="uncollected_dose",
            message="CarePill alert: A scheduled medication has not been collected.",
            channel="whatsapp"
        )

        assert status == "sent"
        assert sid == "SMtestmessage123"

        # Verify posted payload has whatsapp: prefix for To and From
        call_kwargs = mock_post.call_args[1]
        data = call_kwargs["data"]
        assert data["From"] == "whatsapp:+14155238886"
        assert data["To"] == "whatsapp:+15559876543"

def test_uncollected_alert_idempotency_protection(db_session):
    """
    Prevents duplicate uncollected-dose caregiver alerts for the same dose occurrence.
    """
    med = db_session.query(Medication).first()
    cart = db_session.query(Cartridge).first()

    dose = DoseOccurrence(
        medication_id=med.id,
        cartridge_id=cart.id,
        scheduled_for=system_clock.now(),
        scheduled_time_local="08:00",
        requested_pills=1,
        confirmed_pills=0,
        status="escalated",
        created_at=system_clock.now()
    )
    db_session.add(dose)
    db_session.commit()

    # First dispatch
    alert1 = NotificationService.dispatch_caregiver_alert(
        db=db_session,
        alert_type="uncollected_dose",
        dose=dose,
        channel_override="simulated"
    )

    # Second dispatch attempt for the exact same dose
    alert2 = NotificationService.dispatch_caregiver_alert(
        db=db_session,
        alert_type="uncollected_dose",
        dose=dose,
        channel_override="simulated"
    )

    # Must return the same alert without duplicating rows
    assert alert1.id == alert2.id
    count = db_session.query(CaregiverAlert).filter(
        CaregiverAlert.dose_occurrence_id == dose.id,
        CaregiverAlert.alert_type == "uncollected_dose"
    ).count()
    assert count == 1
