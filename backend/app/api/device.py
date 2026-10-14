from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import Dict, Any, List
from app.database import get_db
from app.models.models import DeviceState, DoseOccurrence
from app.schemas.schemas import (
    DeviceHeartbeatRequest, DeviceHeartbeatResponse,
    DeviceDispenseResultReport, DevicePickupEventReport,
    DeviceHardwareConfigRequest, DeviceStateResponse,
    DeviceModeRequest, DeviceConnectivityResponse
)
from app.services.device_service import DeviceService
from app.services.dose_orchestrator import DoseOrchestrator
from app.services.clock_service import system_clock

router = APIRouter(prefix="/device", tags=["ESP32 Hardware Protocol"])

@router.post("/heartbeat", response_model=DeviceHeartbeatResponse)
def device_heartbeat(data: DeviceHeartbeatRequest, db: Session = Depends(get_db)):
    dev = DeviceService.record_heartbeat(
        db=db,
        device_id=data.device_id,
        firmware=data.firmware_version,
        status=data.status
    )

    pending_cmd = None
    # Check if there is an active dispensing dose waiting to be carried out
    active_dispense = db.query(DoseOccurrence).filter(
        DoseOccurrence.status.in_(["dispensing", "corrective_dispensing"])
    ).first()

    if active_dispense and active_dispense.cartridge:
        missing_pills = active_dispense.requested_pills - active_dispense.confirmed_pills
        pending_cmd = {
            "command": "DISPENSE",
            "dose_id": active_dispense.id,
            "cartridge_number": active_dispense.cartridge.cartridge_number,
            "target_pills": missing_pills,
            "max_attempts": 3
        }

    return DeviceHeartbeatResponse(
        acknowledged=True,
        server_time=system_clock.now().isoformat(),
        current_led_pattern=dev.current_led_pattern,
        current_buzzer_pattern=dev.current_buzzer_pattern,
        pending_command=pending_cmd
    )

@router.get("/schedule")
@router.get("/schedule-sync")
def get_device_schedule(db: Session = Depends(get_db)):
    """
    Offline autonomous schedule cache for ESP32 LittleFS flash sync.
    Accessible via both /api/device/schedule and /api/device/schedule-sync.
    """
    return DeviceService.get_offline_schedule_payload(db)

@router.post("/dispense-result")
def report_dispense_result(data: DeviceDispenseResultReport, db: Session = Depends(get_db)):
    """
    ESP32 reports physical Sensor 1 counts.
    """
    success, msg, dose = DoseOrchestrator.process_sensor1_drop_result(
        db=db,
        dose_id=data.dose_id,
        detected_pills_in_this_step=data.confirmed_pills,
        sensor_status=data.status,
        raw_telemetry=data.raw_telemetry
    )
    return {"status": "received", "success": success, "message": msg, "dose_status": dose.status}

@router.post("/pickup-event")
def report_pickup_event(data: DevicePickupEventReport, db: Session = Depends(get_db)):
    """
    ESP32 reports physical Sensor 2 cup pickup detection.
    """
    success, msg, dose = DoseOrchestrator.process_sensor2_pickup_event(
        db=db,
        dose_id=data.dose_id,
        is_collected=data.is_collected,
        raw_val=data.sensor2_raw_val
    )
    return {"status": "received", "success": success, "message": msg}

@router.post("/reconcile")
def reconcile_offline_events(events: List[Dict[str, Any]], db: Session = Depends(get_db)):
    """
    Reconciles batch offline events recorded by ESP32 during network outage.
    Guarantees idempotency: does not re-dispense already completed doses.
    """
    reconciled_count = 0
    for evt in events:
        evt_type = evt.get("type")
        dose_id = evt.get("dose_id")
        if not dose_id:
            continue
        dose = db.query(DoseOccurrence).filter(DoseOccurrence.id == dose_id).first()
        if not dose:
            continue

        if evt_type == "dispense_result" and dose.status in ["scheduled", "dispensing"]:
            DoseOrchestrator.process_sensor1_drop_result(
                db=db,
                dose_id=dose_id,
                detected_pills_in_this_step=evt.get("confirmed_pills", 1),
                sensor_status=evt.get("status", "ok"),
                raw_telemetry=evt.get("telemetry", "offline_reconciled")
            )
            reconciled_count += 1
        elif evt_type == "pickup_event" and dose.status in ["awaiting_collection", "collection_reminder", "escalated"]:
            DoseOrchestrator.process_sensor2_pickup_event(
                db=db,
                dose_id=dose_id,
                is_collected=evt.get("is_collected", True),
                raw_val=evt.get("raw_val")
            )
            reconciled_count += 1

    return {"status": "success", "reconciled_events": reconciled_count}

@router.get("/state", response_model=DeviceStateResponse)
def get_device_state(device_id: str = "ESP32_PILLBOX_01", db: Session = Depends(get_db)):
    """
    Returns current device state including configured cartridge count, online status, LED/buzzer pattern.
    """
    dev = DeviceService.get_or_create_device(db, device_id)
    return dev

@router.post("/configure-hardware")
def configure_device_hardware(data: DeviceHardwareConfigRequest, db: Session = Depends(get_db)):
    """
    Configures device circular cartridge count (4, 6, or 8).
    Safely validates against loss of active medications or stock when downsizing unless force=True.
    """
    success, msg, details = DeviceService.configure_device_cartridges(
        db=db,
        device_id=data.device_id,
        target_count=data.cartridge_count,
        force=data.force
    )
    if not success:
        raise HTTPException(
            status_code=400,
            detail={
                "message": msg,
                "affected_cartridges": details,
                "requires_confirmation": True
            }
        )
    return {
        "status": "success",
        "message": msg,
        "device_id": data.device_id,
        "cartridge_count": data.cartridge_count
    }

@router.get("/connectivity", response_model=DeviceConnectivityResponse)
def get_device_connectivity(device_id: str = "ESP32_PILLBOX_01", db: Session = Depends(get_db)):
    """
    Returns authoritative hardware connectivity and simulation status.
    Truthfully reports Demo vs Physical ESP32 connection state.
    """
    return DeviceService.get_authoritative_status(db, device_id)

@router.post("/mode", response_model=DeviceConnectivityResponse)
def set_device_mode(data: DeviceModeRequest, db: Session = Depends(get_db)):
    """
    Switches system between Simulated/Demo mode and Physical ESP32 hardware mode.
    """
    is_simulated = (data.mode.lower() == "simulated")
    DeviceService.set_operating_mode(db, data.device_id, is_simulated)
    return DeviceService.get_authoritative_status(db, data.device_id)
