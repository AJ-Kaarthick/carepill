from app.models.models import Cartridge, DoseOccurrence
from app.services.clock_service import system_clock

def test_cartridge_refill_api(client):
    response = client.post("/api/cartridges/refill", json={
        "cartridge_number": 1,
        "added_pills": 5,
        "notes": "Weekly refill"
    })
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "success"

def test_device_heartbeat_and_schedule_sync(client):
    # Device heartbeat
    hb_resp = client.post("/api/device/heartbeat", json={
        "device_id": "ESP32_PILLBOX_01",
        "firmware_version": "v1.0.0-idp",
        "battery_pct": 92,
        "wifi_rssi": -55,
        "status": "idle"
    })
    assert hb_resp.status_code == 200
    hb_data = hb_resp.json()
    assert hb_data["acknowledged"] is True
    assert "current_led_pattern" in hb_data
    assert "current_buzzer_pattern" in hb_data

    # Offline schedule sync download
    sched_resp = client.get("/api/device/schedule")
    assert sched_resp.status_code == 200
    sched_data = sched_resp.json()
    assert "schedules" in sched_data
    assert len(sched_data["schedules"]) >= 1

def test_simulator_scenarios(client):
    # Test perfect 2-tablet dispense
    sim_resp = client.post("/api/simulator/action", json={
        "scenario": "dispense_perfect_2"
    })
    assert sim_resp.status_code == 200
    sim_data = sim_resp.json()
    assert sim_data["status"] == "success"

    # Test pickup detection
    pickup_resp = client.post("/api/simulator/action", json={
        "scenario": "pickup_detected"
    })
    assert pickup_resp.status_code == 200
    assert pickup_resp.json()["status"] == "success"
