import pytest
import os
import re
from datetime import datetime
from app.models.models import (
    Medication, Schedule, Cartridge, DoseOccurrence, InventoryTransaction
)
from app.services.dose_orchestrator import DoseOrchestrator
from app.services.clock_service import system_clock
from app.services.device_service import DeviceService

def test_service_worker_isolation_and_port_configuration():
    """
    Verify architectural isolation of CarePill from LearnFlow:
    1. Vite config uses port 5174 and strictPort: true.
    2. index.html does not unconditionally register /sw.js.
    3. main.tsx explicitly unregisters SW in development and registers only in production.
    """
    vite_config_path = "frontend/vite.config.ts"
    assert os.path.exists(vite_config_path), "frontend/vite.config.ts must exist"
    with open(vite_config_path, "r", encoding="utf-8") as f:
        vite_content = f.read()
    assert "port: 5174" in vite_content, "Dev server port must be 5174"
    assert "strictPort: true" in vite_content, "strictPort must be true to prevent fallback to 5173"

    index_html_path = "frontend/index.html"
    assert os.path.exists(index_html_path), "frontend/index.html must exist"
    with open(index_html_path, "r", encoding="utf-8") as f:
        html_content = f.read()
    assert "navigator.serviceWorker.register('/sw.js')" not in html_content, (
        "index.html must NOT contain unconditional sw.js registration script"
    )

    main_tsx_path = "frontend/src/main.tsx"
    assert os.path.exists(main_tsx_path), "frontend/src/main.tsx must exist"
    with open(main_tsx_path, "r", encoding="utf-8") as f:
        main_content = f.read()
    assert "import.meta.env.DEV" in main_content, "main.tsx must check DEV mode"
    assert "unregister" in main_content, "main.tsx must unregister any stale SW in dev mode"
    assert "import.meta.env.PROD" in main_content, "main.tsx must restrict SW registration to PROD mode"

def test_prn_excluded_from_daily_dose_generation_and_device_sync(client, db_session):
    """
    Verify that PRN / As-needed medications:
    1. Are never automatically scheduled by DoseOrchestrator into daily dose occurrences.
    2. Are excluded from /api/device/schedule and /api/device/schedule-sync.
    """
    # 1. Create a PRN medication with an as_needed schedule
    prn_med = Medication(
        name="Robitussin PRN",
        strength="10ml",
        dosage_form="syrup",
        instructions="Take as needed for cough",
        meal_context="none",
        is_active=True,
        created_at=system_clock.now()
    )
    db_session.add(prn_med)
    db_session.commit()
    db_session.refresh(prn_med)

    prn_sched = Schedule(
        medication_id=prn_med.id,
        time_of_day_label="as_needed",
        scheduled_time_str="12:00",
        meal_timing="none",
        dose_quantity=1,
        recurrence="prn",
        is_active=True,
        created_at=system_clock.now()
    )
    db_session.add(prn_sched)
    db_session.commit()

    # 2. Run DoseOrchestrator daily dose generation
    created_doses = DoseOrchestrator.generate_daily_doses_if_needed(db_session)
    prn_doses = [d for d in created_doses if d.medication_id == prn_med.id]
    assert len(prn_doses) == 0, "PRN medication should never have automated daily doses generated"

    all_prn_doses = db_session.query(DoseOccurrence).filter(
        DoseOccurrence.medication_id == prn_med.id
    ).all()
    assert len(all_prn_doses) == 0, "No dose occurrences should exist for PRN schedule"

    # 3. Test /api/device/schedule and /api/device/schedule-sync
    for endpoint in ["/api/device/schedule", "/api/device/schedule-sync"]:
        res = client.get(endpoint)
        assert res.status_code == 200
        payload = res.json()
        assert "schedules" in payload
        for s in payload["schedules"]:
            assert s["schedule_id"] != prn_sched.id, f"PRN schedule found in {endpoint}"
            assert s["tod_label"] != "as_needed"

def test_stocked_cartridge_archival_guard_and_quarantine_reconciliation(client, db_session):
    """
    Verify physical stock safeguards:
    1. Archiving medication with stock fails without force=True.
    2. Force-archiving records an InventoryTransaction audit log and puts cartridge in quarantine.
    3. Reassigning or refilling a quarantined cartridge is rejected until reconciled.
    4. Dispensing from a quarantined cartridge is blocked.
    5. Reconciling with verification clears the quarantine state and records an audit record.
    """
    # 1. Setup active medication with Cartridge 1 holding 20 pills
    med = Medication(
        name="CardioPill Test",
        strength="50mg",
        dosage_form="tablet",
        is_active=True,
        created_at=system_clock.now()
    )
    db_session.add(med)
    db_session.commit()
    db_session.refresh(med)

    cart = db_session.query(Cartridge).filter(
        Cartridge.device_id == "ESP32_PILLBOX_01",
        Cartridge.cartridge_number == 1
    ).first()
    cart.medication_id = med.id
    cart.current_stock = 20
    cart.is_configured = True
    cart.needs_reconciliation = False
    cart.quarantine_reason = None
    db_session.commit()

    # Create dummy schedule and dose record for audit history
    sched = Schedule(
        medication_id=med.id,
        time_of_day_label="morning",
        scheduled_time_str="08:00",
        dose_quantity=1,
        is_active=True,
        created_at=system_clock.now()
    )
    db_session.add(sched)
    db_session.commit()

    dose = DoseOccurrence(
        schedule_id=sched.id,
        medication_id=med.id,
        cartridge_id=cart.id,
        scheduled_for=system_clock.now(),
        scheduled_time_local="08:00",
        requested_pills=1,
        confirmed_pills=1,
        status="collected",
        created_at=system_clock.now()
    )
    db_session.add(dose)
    db_session.commit()

    # 2. Attempt deletion without force -> Must be rejected (400)
    del_res = client.delete(f"/api/medications/{med.id}")
    assert del_res.status_code == 400
    assert "contains 20 pills" in del_res.json()["detail"]

    # 3. Force deletion with caregiver identity and reason
    force_res = client.delete(
        f"/api/medications/{med.id}?force=true&caregiver_name=Nurse%20Joy&reason=Discontinued%20by%20Cardiologist"
    )
    assert force_res.status_code == 200
    assert force_res.json()["status"] == "archived"

    # Refresh cartridge from DB
    db_session.refresh(cart)
    assert cart.needs_reconciliation is True, "Cartridge must be flagged needs_reconciliation"
    assert "Discontinued by Cardiologist" in cart.quarantine_reason
    assert "Nurse Joy" in cart.quarantine_reason
    assert cart.medication_id is None
    assert cart.current_stock == 0

    # Verify inventory audit transaction was written
    tx = db_session.query(InventoryTransaction).filter(
        InventoryTransaction.cartridge_id == cart.id,
        InventoryTransaction.reason == "archival_quarantine"
    ).first()
    assert tx is not None, "Inventory transaction for archival_quarantine must be created"
    assert tx.previous_stock == 20
    assert tx.delta == -20

    # 4. Attempt to refill quarantined cartridge -> Must be rejected (400)
    refill_res = client.post("/api/cartridges/refill", json={
        "cartridge_number": 1,
        "device_id": "ESP32_PILLBOX_01",
        "added_pills": 10
    })
    assert refill_res.status_code == 400
    assert "stock reconciliation state" in refill_res.json()["detail"]

    # 5. Attempt to setup new medication into quarantined cartridge without clear_reconciliation -> Must be rejected (400)
    setup_res = client.post("/api/cartridges/setup", json={
        "cartridge_number": 1,
        "device_id": "ESP32_PILLBOX_01",
        "medication_id": None,
        "initial_stock": 10,
        "low_stock_threshold": 5,
        "confirm_physical_loaded": True,
        "clear_reconciliation": False
    })
    assert setup_res.status_code == 400
    assert "requires physical stock reconciliation" in setup_res.json()["detail"]

    # 6. Attempt to trigger dispense from quarantined cartridge -> Must fail with fault
    dummy_dose = DoseOccurrence(
        medication_id=med.id,
        cartridge_id=cart.id,
        scheduled_for=system_clock.now(),
        scheduled_time_local="08:00",
        requested_pills=1,
        status="scheduled",
        created_at=system_clock.now()
    )
    db_session.add(dummy_dose)
    db_session.commit()

    ok, msg, updated_dose = DoseOrchestrator.trigger_dispense(db_session, dummy_dose.id)
    assert ok is False
    assert "physical stock reconciliation" in msg
    assert updated_dose.status == "dispensing_fault"

    # 7. Explicit physical reconciliation clearance via dedicated endpoint
    # First test without confirmation -> Rejected (400)
    bad_rec = client.post("/api/cartridges/1/reconcile", json={
        "device_id": "ESP32_PILLBOX_01",
        "reconciled_by": "Nurse Joy",
        "confirm_physically_empty": False
    })
    assert bad_rec.status_code == 400

    # Now with confirmation -> Success (200)
    good_rec = client.post("/api/cartridges/1/reconcile", json={
        "device_id": "ESP32_PILLBOX_01",
        "reconciled_by": "Nurse Joy",
        "notes": "Verified cartridge is physically empty and cleaned",
        "confirm_physically_empty": True
    })
    assert good_rec.status_code == 200

    db_session.refresh(cart)
    assert cart.needs_reconciliation is False
    assert cart.quarantine_reason is None

    # Verify reconciliation audit transaction
    rec_tx = db_session.query(InventoryTransaction).filter(
        InventoryTransaction.cartridge_id == cart.id,
        InventoryTransaction.reason == "physical_reconciliation_cleared"
    ).first()
    assert rec_tx is not None, "Reconciliation clearance audit record must be recorded"
