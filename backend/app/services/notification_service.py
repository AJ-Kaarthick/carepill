from typing import Tuple, Optional, Dict, Any
import httpx
import re
from sqlalchemy.orm import Session
from app.config import settings
from app.models.models import CaregiverAlert, DoseOccurrence, User
from app.services.clock_service import system_clock

class NotificationProviderInterface:
    def send(
        self,
        recipient: str,
        alert_type: str,
        message: str,
        channel: str = "sms"
    ) -> Tuple[str, Optional[str], str]:
        """
        Dispatches notification over channel ('sms', 'whatsapp', 'webhook').
        Returns: (delivery_status, provider_message_id, provider_response)
        delivery_status must be one of: "simulated", "queued", "sent", "delivered", "failed"
        """
        raise NotImplementedError

class SimulatedNotificationProvider(NotificationProviderInterface):
    def send(
        self,
        recipient: str,
        alert_type: str,
        message: str,
        channel: str = "sms"
    ) -> Tuple[str, Optional[str], str]:
        import uuid
        msg_id = f"sim_{channel}_{str(uuid.uuid4())[:8]}"
        response_text = f"[SIMULATED_{channel.upper()}] To: {recipient} | Type: {alert_type} | Content: {message}"
        return "simulated", msg_id, response_text

class WebhookNotificationProvider(NotificationProviderInterface):
    def send(
        self,
        recipient: str,
        alert_type: str,
        message: str,
        channel: str = "webhook"
    ) -> Tuple[str, Optional[str], str]:
        if not settings.WEBHOOK_URL:
            return "failed", None, "WEBHOOK_URL not configured in environment"
        try:
            payload = {
                "recipient": recipient,
                "channel": channel,
                "alert_type": alert_type,
                "message": message,
                "timestamp": system_clock.now().isoformat()
            }
            response = httpx.post(settings.WEBHOOK_URL, json=payload, timeout=5.0)
            if response.status_code in (200, 201, 202, 204):
                return "delivered", None, f"Webhook accepted with status {response.status_code}"
            return "failed", None, f"Webhook responded with HTTP {response.status_code}: {response.text[:100]}"
        except Exception as e:
            return "failed", None, f"Webhook dispatch error: {str(e)}"

class TwilioNotificationProvider(NotificationProviderInterface):
    @staticmethod
    def _normalize_e164(phone: str) -> str:
        if not phone:
            return ""
        clean = re.sub(r"[\s\-\(\)\.]", "", phone)
        if not clean.startswith("+"):
            clean = "+91" + clean
        return clean

    def send(
        self,
        recipient: str,
        alert_type: str,
        message: str,
        channel: str = "sms"
    ) -> Tuple[str, Optional[str], str]:
        if not (settings.TWILIO_ACCOUNT_SID and settings.TWILIO_AUTH_TOKEN):
            return "failed", None, "Twilio credentials (ACCOUNT_SID, AUTH_TOKEN) not configured in environment"

        url = f"https://api.twilio.com/2010-04-01/Accounts/{settings.TWILIO_ACCOUNT_SID}/Messages.json"

        if channel == "whatsapp":
            from_addr = settings.TWILIO_WHATSAPP_FROM
            if not from_addr:
                return "failed", None, "TWILIO_WHATSAPP_FROM not configured (must be formatted as whatsapp:+14155238886)"
            if not from_addr.startswith("whatsapp:"):
                from_addr = f"whatsapp:{from_addr}"

            clean_rcpt = self._normalize_e164(recipient)
            to_addr = clean_rcpt if clean_rcpt.startswith("whatsapp:") else f"whatsapp:{clean_rcpt}"

            data = {
                "From": from_addr,
                "To": to_addr,
            }
            # Use Content Template if configured, otherwise fallback to Body
            if settings.TWILIO_WHATSAPP_TEMPLATE_SID:
                data["ContentSid"] = settings.TWILIO_WHATSAPP_TEMPLATE_SID
                # Twilio Content Variables JSON format
                data["ContentVariables"] = f'{{"1":"{message}"}}'
            else:
                data["Body"] = message

        else:
            # Standard SMS
            from_addr = settings.TWILIO_FROM_NUMBER
            if not from_addr:
                return "failed", None, "TWILIO_FROM_NUMBER not configured in environment"
            to_addr = self._normalize_e164(recipient)
            data = {
                "From": from_addr,
                "To": to_addr,
                "Body": message
            }

        try:
            response = httpx.post(
                url,
                data=data,
                auth=(settings.TWILIO_ACCOUNT_SID, settings.TWILIO_AUTH_TOKEN),
                timeout=6.0
            )
            resp_json = response.json() if response.headers.get("content-type", "").startswith("application/json") else {}
            if response.status_code in (200, 201):
                sid = resp_json.get("sid", "TWILIO_OK")
                return "sent", sid, f"Twilio accepted message: SID {sid}"
            err_msg = resp_json.get("message", response.text[:120])
            return "failed", None, f"Twilio HTTP {response.status_code}: {err_msg}"
        except Exception as e:
            return "failed", None, f"Twilio network error: {str(e)}"

def get_notification_provider() -> NotificationProviderInterface:
    if settings.NOTIFICATION_PROVIDER == "webhook":
        return WebhookNotificationProvider()
    elif settings.NOTIFICATION_PROVIDER == "twilio":
        return TwilioNotificationProvider()
    return SimulatedNotificationProvider()

class NotificationService:
    @staticmethod
    def dispatch_caregiver_alert(
        db: Session,
        alert_type: str,
        message: Optional[str] = None,
        dose: Optional[DoseOccurrence] = None,
        recipient_override: Optional[str] = None,
        channel_override: Optional[str] = None
    ) -> CaregiverAlert:
        """
        Creates and dispatches an alert to designated caregiver.
        Prevents duplicate uncollected-dose alert for the same dose.
        Checks consent for real SMS/WhatsApp delivery.
        """
        now = system_clock.now()

        # Idempotency check: prevent duplicate uncollected-dose alert for the same dose
        if dose and alert_type == "uncollected_dose":
            existing = db.query(CaregiverAlert).filter(
                CaregiverAlert.dose_occurrence_id == dose.id,
                CaregiverAlert.alert_type == "uncollected_dose"
            ).first()
            if existing:
                return existing

        # Locate caregiver profile
        caregiver = db.query(User).filter(User.role == "caregiver").first()

        # Channel selection: override or caregiver preference, default to simulated
        channel = channel_override or (caregiver.notification_channel if caregiver else "simulated")
        if channel not in ["simulated", "sms", "whatsapp", "webhook"]:
            channel = "simulated"

        # Determine target recipient address based on channel
        if channel == "whatsapp":
            recipient = recipient_override or (
                (caregiver.whatsapp_phone or caregiver.phone) if caregiver else "whatsapp:+919876543210"
            )
        elif channel in ["sms", "simulated"]:
            recipient = recipient_override or (caregiver.phone if caregiver else "+919876543210")
        else:
            recipient = recipient_override or (caregiver.email if caregiver else "webhook@carepill.local")

        # Standard minimal message text as requested by spec:
        # "CarePill alert: A scheduled medication has not been collected. Please check on the patient. Time: [time]."
        if not message:
            time_str = now.strftime("%H:%M")
            if alert_type == "uncollected_dose":
                message = f"CarePill alert: A scheduled medication has not been collected. Please check on the patient. Time: {time_str}."
            elif alert_type == "dispensing_fault":
                message = f"CarePill alert: A hardware dispensing fault occurred. Please check on the patient and pill dispenser. Time: {time_str}."
            elif alert_type == "low_stock":
                message = f"CarePill alert: One or more pill cartridges are low on stock. Please plan a refill. Time: {time_str}."
            else:
                message = f"CarePill alert: Notification event '{alert_type}'. Time: {time_str}."

        # Verify Consent if not in simulated mode
        if settings.NOTIFICATION_PROVIDER == "twilio":
            if channel == "sms" and caregiver and not caregiver.sms_consent:
                # Consent not granted!
                alert = CaregiverAlert(
                    dose_occurrence_id=dose.id if dose else None,
                    alert_type=alert_type,
                    message=message,
                    recipient_contact=recipient,
                    channel=channel,
                    delivery_status="failed",
                    provider_message_id=None,
                    provider_response="Delivery failed: Explicit SMS opt-in consent has not been granted by caregiver.",
                    acknowledged=False,
                    created_at=now
                )
                db.add(alert)
                db.commit()
                db.refresh(alert)
                return alert

            elif channel == "whatsapp" and caregiver and not caregiver.whatsapp_consent:
                # Consent not granted!
                alert = CaregiverAlert(
                    dose_occurrence_id=dose.id if dose else None,
                    alert_type=alert_type,
                    message=message,
                    recipient_contact=recipient,
                    channel=channel,
                    delivery_status="failed",
                    provider_message_id=None,
                    provider_response="Delivery failed: Explicit WhatsApp opt-in consent has not been granted by caregiver.",
                    acknowledged=False,
                    created_at=now
                )
                db.add(alert)
                db.commit()
                db.refresh(alert)
                return alert

        provider = get_notification_provider()
        status, msg_id, provider_resp = provider.send(
            recipient=recipient,
            alert_type=alert_type,
            message=message,
            channel=channel
        )

        alert = CaregiverAlert(
            dose_occurrence_id=dose.id if dose else None,
            alert_type=alert_type,
            message=message,
            recipient_contact=recipient,
            channel=channel,
            delivery_status=status,
            provider_message_id=msg_id,
            provider_response=provider_resp,
            acknowledged=False,
            created_at=now
        )
        db.add(alert)
        db.commit()
        db.refresh(alert)
        return alert

    @staticmethod
    def acknowledge_alert(db: Session, alert_id: str, acknowledged_by: str = "Caregiver") -> Optional[CaregiverAlert]:
        alert = db.query(CaregiverAlert).filter(CaregiverAlert.id == alert_id).first()
        if alert:
            alert.acknowledged = True
            alert.acknowledged_by = acknowledged_by
            alert.acknowledged_at = system_clock.now()
            db.commit()
            db.refresh(alert)
        return alert
