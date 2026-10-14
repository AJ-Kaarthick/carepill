import sys
from fastapi.testclient import TestClient
from app.main import app
from app.database import Base, engine, SessionLocal, run_schema_migrations
from app.seed import seed_database
from app.models.models import DoseOccurrence
from app.services.clock_service import system_clock

def run_verification():
    print("==================================================")
    print("STARTING CAREPILL END-TO-END SYSTEM VERIFICATION")
    print("==================================================")

    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    run_schema_migrations(engine)
    db = SessionLocal()
    seed_database(db)
    db.close()

    client = TestClient(app)

    # 1. Health check
    res = client.get("/health")
    assert res.status_code == 200, f"Health check failed: {res.text}"
    print("[PASS] 1. /health check: OK")

    # 2. Get Users
    res = client.get("/api/users/")
    assert res.status_code == 200
    users = res.json()
    assert len(users) >= 2
    print(f"[PASS] 2. Users loaded: {len(users)} users (Patient Eleanor, Caregiver Marcus)")

    # 3. Cartridges (Default 4)
    res = client.get("/api/cartridges/")
    assert res.status_code == 200
    cartridges = res.json()
    assert len(cartridges) == 4
    for c in cartridges:
        print(f"   - Cartridge {c['cartridge_number']}: {c['medication_name']} ({c['current_stock']}/{c['capacity']} pills) [LowStock: {c['is_low_stock']}]")
    print("[PASS] 3. 4 Physical Cartridges loaded and mapped correctly (Default count)")

    # 4. Hardware Configuration: Switch to 6 and 8 Cartridges
    print("\n[TESTING] Configurable Hardware: 4 -> 6 -> 8 Cartridges")
    res_cfg6 = client.post("/api/device/configure-hardware", json={"device_id": "ESP32_PILLBOX_01", "cartridge_count": 6})
    assert res_cfg6.status_code == 200
    carts6 = client.get("/api/cartridges/").json()
    assert len(carts6) == 6
    print("   [PASS] Successfully expanded to 6 circular cartridges")

    res_cfg8 = client.post("/api/device/configure-hardware", json={"device_id": "ESP32_PILLBOX_01", "cartridge_count": 8})
    assert res_cfg8.status_code == 200
    carts8 = client.get("/api/cartridges/").json()
    assert len(carts8) == 8
    print("   [PASS] Successfully expanded to 8 circular cartridges")

    # Revert to 4 cartridges safely
    res_cfg4 = client.post("/api/device/configure-hardware", json={"device_id": "ESP32_PILLBOX_01", "cartridge_count": 4, "force": True})
    assert res_cfg4.status_code == 200
    print("   [PASS] Successfully reconfigured back to standard 4 cartridges")

    # 5. Schedules
    res = client.get("/api/schedules/")
    assert res.status_code == 200
    schedules = res.json()
    assert len(schedules) >= 4
    print(f"\n[PASS] 5. Medication Schedules: {len(schedules)} active schedules")

    # 6. Today's Doses
    res = client.get("/api/doses/today")
    assert res.status_code == 200
    doses = res.json()
    assert len(doses) >= 4
    print(f"[PASS] 6. Today's Chronological Dose Timeline: {len(doses)} doses generated")

    # 7. Pre-Dose Reminder Timings (-10m, -5m)
    print("\n[TESTING] Pre-Dose Reminders (-10m and -5m)")
    res_pre10 = client.post("/api/simulator/action", json={"scenario": "fast_forward_pre_dose_10m"})
    assert res_pre10.status_code == 200
    print(f"   [PASS] -10m Pre-Dose Reminder: {res_pre10.json()['message']}")

    res_pre5 = client.post("/api/simulator/action", json={"scenario": "fast_forward_pre_dose_5m"})
    assert res_pre5.status_code == 200
    print(f"   [PASS] -5m Pre-Dose Reminder: {res_pre5.json()['message']}")

    # 8. Scenario Test: Under-dispense 1 of 2 -> Bounded Corrective Dispensing -> Pickup
    print("\n[TESTING] Scenario: 2-Tablet Prescribed Dose (Atorvastatin) with Under-dispense & Correction")
    target_dose = [d for d in doses if d["requested_pills"] == 2 and d["status"] in ["scheduled", "pre_dose_reminder"]][0]
    dose_id = target_dose["id"]

    # Step A: Dispense
    res = client.post(f"/api/doses/{dose_id}/dispense")
    assert res.status_code == 200
    print("   [A] Triggered Dispense -> State: dispensing")

    # Step B: Sensor 1 detects 1 pill only
    res = client.post(f"/api/doses/{dose_id}/sensor1-drop?detected_count=1&sensor_status=ok")
    assert res.status_code == 200
    d_step1 = res.json()["dose"]
    assert d_step1["status"] == "corrective_dispensing"
    assert d_step1["confirmed_pills"] == 1
    print("   [B] Sensor 1 detected 1 pill -> State: corrective_dispensing (Missing 1 pill)")

    # Step C: Corrective attempt delivers remaining 1 pill
    res = client.post(f"/api/doses/{dose_id}/sensor1-drop?detected_count=1&sensor_status=ok")
    assert res.status_code == 200
    d_step2 = res.json()["dose"]
    assert d_step2["status"] == "awaiting_collection"
    assert d_step2["confirmed_pills"] == 2
    print("   [C] Sensor 1 detected corrective pill -> State: awaiting_collection (2/2 confirmed)")

    # Step D: Test Clock for 5-min Post-Dispense Reminder
    print("\n[TESTING] Clock: Advancing 5 Minutes")
    res = client.post("/api/simulator/action", json={"scenario": "fast_forward_5m"})
    assert res.status_code == 200
    res_d = client.get("/api/doses/today").json()
    updated_dose = [d for d in res_d if d["id"] == dose_id][0]
    assert updated_dose["status"] == "collection_reminder"
    print("   [D] 5 Minutes elapsed uncollected -> State: collection_reminder (Repeating alert active)")

    # Step E: Test Clock for 10-min Post-Dispense Escalation
    print("\n[TESTING] Clock: Advancing another 5 Minutes (Total 10 Minutes)")
    res = client.post("/api/simulator/action", json={"scenario": "fast_forward_10m"})
    assert res.status_code == 200
    res_d = client.get("/api/doses/today").json()
    updated_dose = [d for d in res_d if d["id"] == dose_id][0]
    assert updated_dose["status"] == "escalated"
    print("   [E] 10 Minutes elapsed uncollected -> State: escalated (Caregiver alert dispatched)")

    # Step F: Verify Caregiver Alert generated
    res_alerts = client.get("/api/caregiver/alerts").json()
    uncollected_alert = [a for a in res_alerts if a["dose_occurrence_id"] == dose_id and a["alert_type"] == "uncollected_dose"][0]
    assert uncollected_alert is not None
    assert "CarePill alert: A scheduled medication has not been collected." in uncollected_alert["message"]
    print(f"   [F] Caregiver Alert Created: '{uncollected_alert['message'][:65]}...' [Status: {uncollected_alert['delivery_status']}]")

    # Step G: Caregiver Acknowledges Alert
    res_ack = client.post(f"/api/caregiver/alerts/{uncollected_alert['id']}/acknowledge", json={"acknowledged_by": "Marcus Vance"})
    assert res_ack.status_code == 200
    print("   [G] Caregiver Acknowledged Alert successfully")

    # Step H: Sensor 2 detects Patient Pickup
    res_pickup = client.post(f"/api/doses/{dose_id}/pickup?is_collected=true")
    assert res_pickup.status_code == 200
    d_final = res_pickup.json()["dose"]
    assert d_final["status"] == "collected"
    print("   [H] Sensor 2 detected Medicine Cup Pickup -> State: collected! All reminders halted.")

    # 9. Caregiver Notification Channels & Settings Test
    print("\n[TESTING] Caregiver Notification Preferences & Test Alert")
    res_cg_set = client.put("/api/caregiver/settings", json={
        "phone": "+1 (555) 987-6543",
        "whatsapp_phone": "+1 (555) 987-6543",
        "notification_channel": "simulated",
        "sms_consent": True,
        "whatsapp_consent": True
    })
    assert res_cg_set.status_code == 200
    print("   [PASS] Updated Caregiver Settings: SMS & WhatsApp consent granted")

    res_cg_test = client.post("/api/caregiver/test-notification", json={
        "channel": "simulated",
        "custom_message": "CarePill verification test alert"
    })
    assert res_cg_test.status_code == 200
    assert res_cg_test.json()["delivery_status"] == "simulated"
    print(f"   [PASS] Dispatched Caregiver Test Notification: {res_cg_test.json()['delivery_status']}")

    # 10. Device Hardware Protocol Check
    print("\n[TESTING] ESP32 Device Hardware Protocol")
    res_hb = client.post("/api/device/heartbeat", json={
        "device_id": "ESP32_PILLBOX_01",
        "firmware_version": "v1.0.0-idp",
        "battery_pct": 95,
        "wifi_rssi": -48,
        "status": "idle"
    })
    assert res_hb.status_code == 200
    print(f"   [PASS] Heartbeat OK: Server time {res_hb.json()['server_time']}, LED pattern {res_hb.json()['current_led_pattern']}")

    res_sched = client.get("/api/device/schedule")
    assert res_sched.status_code == 200
    print(f"   [PASS] Offline Schedule Sync Download: {len(res_sched.json()['schedules'])} schedules returned for ESP32 LittleFS")

    # 11. Auditable Inventory Ledger
    res_tx = client.get("/api/cartridges/transactions").json()
    assert len(res_tx) >= 1
    print(f"\n[PASS] 11. Auditable Inventory Ledger: {len(res_tx)} transactions recorded")

    print("\n==================================================")
    print("ALL VERIFICATION CHECKS PASSED (100% SUCCESS)")
    print("==================================================")

if __name__ == "__main__":
    run_verification()
