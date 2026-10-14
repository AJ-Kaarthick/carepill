from sqlalchemy import Column, Integer, String, Float, Boolean, DateTime, ForeignKey, Text, UniqueConstraint
from sqlalchemy.orm import relationship
from datetime import datetime, timezone
import uuid
from app.database import Base

def generate_uuid():
    return str(uuid.uuid4())

def utc_now():
    return datetime.now(timezone.utc).replace(tzinfo=None)

class User(Base):
    __tablename__ = "users"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    name = Column(String(100), nullable=False)
    role = Column(String(20), nullable=False, default="patient")  # "patient", "caregiver", "admin"
    phone = Column(String(30), nullable=True)
    email = Column(String(100), nullable=True)
    whatsapp_phone = Column(String(30), nullable=True)
    notification_channel = Column(String(20), default="simulated")  # "simulated", "sms", "whatsapp", "webhook"
    sms_consent = Column(Boolean, default=False)
    whatsapp_consent = Column(Boolean, default=False)
    timezone = Column(String(50), default="UTC")
    created_at = Column(DateTime, default=utc_now)

class Medication(Base):
    __tablename__ = "medications"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    name = Column(String(100), nullable=False)
    strength = Column(String(50), nullable=True)  # e.g., "500mg", "10mg"
    dosage_form = Column(String(50), default="tablet")  # "tablet", "capsule"
    instructions = Column(Text, nullable=True)
    meal_context = Column(String(50), default="none")  # e.g. "after_breakfast", "with_food"
    low_stock_threshold = Column(Integer, default=5)
    prescribed_dose_qty = Column(Integer, default=1)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=utc_now)

    cartridges = relationship("Cartridge", back_populates="medication")
    schedules = relationship("Schedule", back_populates="medication")

class Prescription(Base):
    __tablename__ = "prescriptions"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    filename = Column(String(255), nullable=False)
    file_path = Column(String(500), nullable=False)
    raw_ocr_text = Column(Text, nullable=True)
    review_status = Column(String(30), default="unreviewed")  # "unreviewed", "draft_reviewed", "schedule_reviewed", "loaded", "confirmed", "rejected"
    reviewed_by = Column(String(100), nullable=True)
    reviewed_at = Column(DateTime, nullable=True)
    uploaded_at = Column(DateTime, default=utc_now)
    draft_json = Column(Text, nullable=True)
    extraction_engine = Column(String(50), default="local_rule_engine")
    caregiver_notes = Column(Text, nullable=True)

    candidates = relationship("PrescriptionCandidate", back_populates="prescription", cascade="all, delete-orphan")

class PrescriptionCandidate(Base):
    __tablename__ = "prescription_candidates"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    prescription_id = Column(String(36), ForeignKey("prescriptions.id"), nullable=False)
    medicine_name = Column(String(100), nullable=False)
    strength = Column(String(50), nullable=True)
    prescribed_dose_qty = Column(Integer, default=1)
    frequency = Column(String(100), nullable=True)  # e.g. "Twice daily"
    timing_hint = Column(String(50), nullable=True)  # "morning", "bedtime"
    meal_instructions = Column(String(100), nullable=True)  # "after meals"
    confidence = Column(Float, default=0.85)
    status = Column(String(30), default="pending")  # "pending", "accepted", "discarded"
    notes = Column(Text, nullable=True)

    prescription = relationship("Prescription", back_populates="candidates")

class Cartridge(Base):
    __tablename__ = "cartridges"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    device_id = Column(String(50), default="ESP32_PILLBOX_01", nullable=False)
    cartridge_number = Column(Integer, nullable=False)  # 1..4, 1..6, or 1..8
    medication_id = Column(String(36), ForeignKey("medications.id"), nullable=True)
    current_stock = Column(Integer, default=0)
    capacity = Column(Integer, default=30)
    low_stock_threshold = Column(Integer, default=5)
    is_configured = Column(Boolean, default=False)
    needs_reconciliation = Column(Boolean, default=False)
    quarantine_reason = Column(Text, nullable=True)
    last_refilled_at = Column(DateTime, nullable=True)
    calibration_offset_deg = Column(Float, default=0.0)

    medication = relationship("Medication", back_populates="cartridges")
    doses = relationship("DoseOccurrence", back_populates="cartridge")
    transactions = relationship("InventoryTransaction", back_populates="cartridge")

    __table_args__ = (
        UniqueConstraint("device_id", "cartridge_number", name="uq_device_cartridge_number"),
    )

class Schedule(Base):
    __tablename__ = "schedules"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    medication_id = Column(String(36), ForeignKey("medications.id"), nullable=False)
    time_of_day_label = Column(String(30), default="morning")  # "early_morning", "morning", "afternoon", "evening", "bedtime"
    scheduled_time_str = Column(String(10), nullable=False)  # "08:00", "13:00", "20:00"
    meal_timing = Column(String(50), default="none")
    custom_meal_note = Column(String(200), nullable=True)
    dose_quantity = Column(Integer, default=1)
    start_date = Column(String(20), nullable=True)  # "YYYY-MM-DD"
    end_date = Column(String(20), nullable=True)    # "YYYY-MM-DD"
    recurrence = Column(String(30), default="daily")  # "daily", "weekdays", "specific_days"
    days_of_week = Column(String(50), default="all")  # "all" or "0,1,2,3,4,5,6"
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=utc_now)

    medication = relationship("Medication", back_populates="schedules")
    doses = relationship("DoseOccurrence", back_populates="schedule")

class DoseOccurrence(Base):
    __tablename__ = "dose_occurrences"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    schedule_id = Column(String(36), ForeignKey("schedules.id"), nullable=True)
    medication_id = Column(String(36), ForeignKey("medications.id"), nullable=False)
    cartridge_id = Column(String(36), ForeignKey("cartridges.id"), nullable=True)

    scheduled_for = Column(DateTime, nullable=False)  # UTC timestamp
    scheduled_time_local = Column(String(10), nullable=False)  # "08:00"
    meal_context_snapshot = Column(String(100), nullable=True)
    requested_pills = Column(Integer, nullable=False, default=1)
    confirmed_pills = Column(Integer, default=0)  # Measured by Sensor 1

    # States:
    # scheduled, pre_dose_reminder, dispensing, dispensing_verification,
    # corrective_dispensing, dispensed, awaiting_collection, collection_reminder,
    # collected, escalated, dispensing_fault, sensor_fault, missed
    status = Column(String(40), default="scheduled")

    pre_dose_10m_sent_at = Column(DateTime, nullable=True)
    pre_dose_5m_sent_at = Column(DateTime, nullable=True)
    command_id = Column(String(36), nullable=True)
    dispense_initiated_at = Column(DateTime, nullable=True)
    dispensed_at = Column(DateTime, nullable=True)
    collected_at = Column(DateTime, nullable=True)
    pickup_reminder_sent_at = Column(DateTime, nullable=True)
    escalated_at = Column(DateTime, nullable=True)

    manual_confirmation_by = Column(String(100), nullable=True)
    manual_confirmed_at = Column(DateTime, nullable=True)
    manual_confirmation_notes = Column(Text, nullable=True)
    fault_reason = Column(Text, nullable=True)
    correction_attempts_used = Column(Integer, default=0)

    created_at = Column(DateTime, default=utc_now)

    schedule = relationship("Schedule", back_populates="doses")
    cartridge = relationship("Cartridge", back_populates="doses")
    operations = relationship("DispensingOperation", back_populates="dose", cascade="all, delete-orphan")
    alerts = relationship("CaregiverAlert", back_populates="dose")

class DispensingOperation(Base):
    __tablename__ = "dispensing_operations"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    dose_occurrence_id = Column(String(36), ForeignKey("dose_occurrences.id"), nullable=False)
    attempt_number = Column(Integer, nullable=False, default=1)
    target_pills_this_attempt = Column(Integer, nullable=False)
    sensor1_detected_count = Column(Integer, default=0)
    status = Column(String(30), default="success")  # "success", "under_dispense", "over_dispense", "jam_fault", "uncertain"
    raw_telemetry = Column(Text, nullable=True)
    created_at = Column(DateTime, default=utc_now)

    dose = relationship("DoseOccurrence", back_populates="operations")

class SensorReading(Base):
    __tablename__ = "sensor_readings"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    sensor_type = Column(String(30), nullable=False)  # "sensor1_drop_counter", "sensor2_pickup"
    dose_occurrence_id = Column(String(36), ForeignKey("dose_occurrences.id"), nullable=True)
    value = Column(Float, nullable=False)
    details = Column(String(255), nullable=True)
    timestamp = Column(DateTime, default=utc_now)

class CaregiverAlert(Base):
    __tablename__ = "caregiver_alerts"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    dose_occurrence_id = Column(String(36), ForeignKey("dose_occurrences.id"), nullable=True)
    alert_type = Column(String(50), nullable=False)  # "uncollected_dose", "dispensing_fault", "sensor_fault", "low_stock", "test_alert"
    message = Column(Text, nullable=False)
    recipient_contact = Column(String(100), nullable=True)
    channel = Column(String(30), default="simulated")  # "simulated", "sms", "whatsapp", "webhook"
    delivery_status = Column(String(30), default="simulated")  # "simulated", "queued", "sent", "delivered", "failed"
    provider_message_id = Column(String(100), nullable=True)
    provider_response = Column(Text, nullable=True)
    acknowledged = Column(Boolean, default=False)
    acknowledged_by = Column(String(100), nullable=True)
    acknowledged_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=utc_now)

    dose = relationship("DoseOccurrence", back_populates="alerts")

class InventoryTransaction(Base):
    __tablename__ = "inventory_transactions"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    cartridge_id = Column(String(36), ForeignKey("cartridges.id"), nullable=False)
    medication_id = Column(String(36), ForeignKey("medications.id"), nullable=True)
    delta = Column(Integer, nullable=False)  # e.g. -2 or +30
    previous_stock = Column(Integer, nullable=False)
    new_stock = Column(Integer, nullable=False)
    reason = Column(String(50), nullable=False)  # "dispense_confirmed", "refill", "manual_adjustment", "waste"
    confirmed_sensor_id = Column(String(50), nullable=True)  # e.g. "sensor1_breakbeam"
    dose_occurrence_id = Column(String(36), ForeignKey("dose_occurrences.id"), nullable=True)
    timestamp = Column(DateTime, default=utc_now)

    cartridge = relationship("Cartridge", back_populates="transactions")

class DeviceState(Base):
    __tablename__ = "device_states"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    device_id = Column(String(50), unique=True, default="ESP32_PILLBOX_01")
    cartridge_count = Column(Integer, default=4)  # 4, 6, or 8 supported
    is_online = Column(Boolean, default=True)
    last_heartbeat = Column(DateTime, default=utc_now)
    firmware_version = Column(String(30), default="v1.0.0-idp")
    current_led_pattern = Column(String(50), default="IDLE_OFF")
    current_buzzer_pattern = Column(String(50), default="SILENT")
    active_dose_id = Column(String(36), nullable=True)
    is_simulated = Column(Boolean, default=True)
    config_json = Column(Text, nullable=True)
    updated_at = Column(DateTime, default=utc_now)
