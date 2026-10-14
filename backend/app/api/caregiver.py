from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List, Dict, Any
from app.database import get_db
from app.models.models import CaregiverAlert, DoseOccurrence, Cartridge, DeviceState, User
from app.schemas.schemas import (
    CaregiverAlertResponse, AlertAcknowledgeRequest,
    CaregiverSettingsRequest, CaregiverSettingsResponse, TestNotificationRequest
)
from app.services.notification_service import NotificationService
from app.services.dose_orchestrator import DoseOrchestrator
from app.services.clock_service import system_clock

router = APIRouter(prefix="/caregiver", tags=["Caregiver Portal"])

@router.get("/dashboard")
def get_caregiver_dashboard(db: Session = Depends(get_db)):
    DoseOrchestrator.evaluate_timeouts_and_escalations(db)

    device = db.query(DeviceState).first()
    alerts = db.query(CaregiverAlert).order_by(CaregiverAlert.created_at.desc()).limit(10).all()
    unacked_alerts = [a for a in alerts if not a.acknowledged]

    # Active issues
    uncollected_doses = db.query(DoseOccurrence).filter(
        DoseOccurrence.status.in_(["collection_reminder", "escalated"])
    ).all()

    faulty_doses = db.query(DoseOccurrence).filter(
        DoseOccurrence.status.in_(["dispensing_fault", "sensor_fault"])
    ).all()

    # Low stock cartridges
    cartridges = db.query(Cartridge).all()
    low_stock = [c for c in cartridges if c.is_configured and c.current_stock <= c.low_stock_threshold]

    return {
        "device_online": device.is_online if device else False,
        "last_heartbeat": device.last_heartbeat if device else None,
        "unacknowledged_alerts_count": len(unacked_alerts),
        "uncollected_doses_count": len(uncollected_doses),
        "faulty_doses_count": len(faulty_doses),
        "low_stock_count": len(low_stock),
        "current_led_pattern": device.current_led_pattern if device else "OFF",
        "current_buzzer_pattern": device.current_buzzer_pattern if device else "SILENT",
        "system_time": system_clock.now().isoformat()
    }

@router.get("/alerts", response_model=List[CaregiverAlertResponse])
def get_caregiver_alerts(db: Session = Depends(get_db)):
    DoseOrchestrator.evaluate_timeouts_and_escalations(db)
    return db.query(CaregiverAlert).order_by(CaregiverAlert.created_at.desc()).all()

@router.post("/alerts/{alert_id}/acknowledge")
def acknowledge_caregiver_alert(
    alert_id: str,
    req: AlertAcknowledgeRequest,
    db: Session = Depends(get_db)
):
    alert = NotificationService.acknowledge_alert(db, alert_id, acknowledged_by=req.acknowledged_by)
    if not alert:
        raise HTTPException(status_code=404, detail="Alert not found")
    return {"status": "success", "message": "Alert acknowledged."}

@router.get("/settings", response_model=CaregiverSettingsResponse)
def get_caregiver_settings(db: Session = Depends(get_db)):
    """
    Returns the caregiver profile and notification preferences.
    """
    caregiver = db.query(User).filter(User.role == "caregiver").first()
    if not caregiver:
        caregiver = User(
            name="Marcus Vance",
            role="caregiver",
            phone="+91 98765 43210",
            whatsapp_phone="+91 98765 43210",
            notification_channel="simulated",
            sms_consent=False,
            whatsapp_consent=False
        )
        db.add(caregiver)
        db.commit()
        db.refresh(caregiver)
    return caregiver

@router.put("/settings", response_model=CaregiverSettingsResponse)
def update_caregiver_settings(req: CaregiverSettingsRequest, db: Session = Depends(get_db)):
    """
    Updates caregiver contact phone, whatsapp phone, channel, and explicit SMS/WhatsApp consent.
    """
    caregiver = db.query(User).filter(User.role == "caregiver").first()
    if not caregiver:
        caregiver = User(name="Marcus Vance", role="caregiver")
        db.add(caregiver)

    if req.name is not None:
        caregiver.name = req.name
    if req.phone is not None:
        caregiver.phone = req.phone
    if req.whatsapp_phone is not None:
        caregiver.whatsapp_phone = req.whatsapp_phone
    if req.notification_channel is not None:
        caregiver.notification_channel = req.notification_channel
    caregiver.sms_consent = req.sms_consent
    caregiver.whatsapp_consent = req.whatsapp_consent

    db.commit()
    db.refresh(caregiver)
    return caregiver

@router.post("/test-notification")
def send_test_notification(req: TestNotificationRequest, db: Session = Depends(get_db)):
    """
    Sends a test notification to verify caregiver channel configuration.
    Delivers honestly with actual provider status.
    """
    alert = NotificationService.dispatch_caregiver_alert(
        db=db,
        alert_type="test_notification",
        message=req.custom_message,
        recipient_override=req.recipient_override,
        channel_override=req.channel
    )
    return {
        "status": "success",
        "alert_id": alert.id,
        "channel": alert.channel,
        "recipient": alert.recipient_contact,
        "delivery_status": alert.delivery_status,
        "provider_message_id": alert.provider_message_id,
        "provider_response": alert.provider_response,
        "message": alert.message
    }
