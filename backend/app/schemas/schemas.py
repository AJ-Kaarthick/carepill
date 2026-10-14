from pydantic import BaseModel, Field, ConfigDict, field_validator, model_validator
from typing import Optional, List, Dict, Any
from datetime import datetime
import re

# Validation Helpers
VALID_MEAL_CONTEXTS = {
    "before_breakfast", "with_breakfast", "after_breakfast",
    "before_lunch", "with_lunch", "after_lunch",
    "before_dinner", "with_dinner", "after_dinner",
    "with_food", "none"
}

def validate_human_name(v: str) -> str:
    if not v or not v.strip():
        raise ValueError("Name cannot be empty")
    v_clean = v.strip()
    if any(char.isdigit() for char in v_clean):
        raise ValueError("Human name must not contain numbers")
    if not re.match(r"^[\w\s\.\-'\u00C0-\u024F]+$", v_clean, re.UNICODE):
        raise ValueError("Name contains invalid characters")
    return v_clean

def validate_phone_number(v: Optional[str]) -> Optional[str]:
    if not v:
        return None
    val = v.strip()
    if not val:
        return None
    if any(c.isalpha() for c in val):
        raise ValueError("Phone number must not contain letters")
    cleaned = re.sub(r"[\s\-\(\)\.]", "", val)
    if not re.match(r"^\+?[0-9]{7,15}$", cleaned):
        raise ValueError("Phone number must contain between 7 and 15 digits")
    return val

def normalize_meal_context(v: Optional[str]) -> str:
    if not v:
        return "none"
    val = v.strip().lower()
    if val in VALID_MEAL_CONTEXTS:
        return val
    # Map common aliases
    if "before" in val and "breakfast" in val: return "before_breakfast"
    if "after" in val and "breakfast" in val: return "after_breakfast"
    if "with" in val and "breakfast" in val: return "with_breakfast"
    if "before" in val and "lunch" in val: return "before_lunch"
    if "after" in val and "lunch" in val: return "after_lunch"
    if "with" in val and "lunch" in val: return "with_lunch"
    if "before" in val and "dinner" in val: return "before_dinner"
    if "after" in val and "dinner" in val: return "after_dinner"
    if "with" in val and "dinner" in val: return "with_dinner"
    if "food" in val or "meal" in val: return "with_food"
    return "none"

# User
class UserBase(BaseModel):
    name: str
    role: str = "patient"
    phone: Optional[str] = None
    email: Optional[str] = None
    whatsapp_phone: Optional[str] = None
    notification_channel: str = "simulated"
    sms_consent: bool = False
    whatsapp_consent: bool = False
    timezone: str = "UTC"

    @field_validator("name")
    @classmethod
    def check_name(cls, v: str) -> str:
        return validate_human_name(v)

    @field_validator("phone", "whatsapp_phone")
    @classmethod
    def check_phone(cls, v: Optional[str]) -> Optional[str]:
        return validate_phone_number(v)

class UserCreate(UserBase):
    pass

class UserResponse(UserBase):
    id: str
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)

class CaregiverSettingsRequest(BaseModel):
    name: Optional[str] = None
    phone: Optional[str] = None
    whatsapp_phone: Optional[str] = None
    notification_channel: str = "simulated"
    sms_consent: bool = False
    whatsapp_consent: bool = False

    @field_validator("name")
    @classmethod
    def check_name(cls, v: Optional[str]) -> Optional[str]:
        return validate_human_name(v) if v else None

    @field_validator("phone", "whatsapp_phone")
    @classmethod
    def check_phone(cls, v: Optional[str]) -> Optional[str]:
        return validate_phone_number(v)

class CaregiverSettingsResponse(CaregiverSettingsRequest):
    id: str
    name: str
    role: str
    model_config = ConfigDict(from_attributes=True)

class TestNotificationRequest(BaseModel):
    channel: str = "simulated"  # "simulated", "sms", "whatsapp", "webhook"
    recipient_override: Optional[str] = None
    custom_message: Optional[str] = None

# Medication Schedule Item for Nested Creation/Update
class ScheduleCreateItem(BaseModel):
    scheduled_time_str: str = "08:00"   # "HH:MM"
    time_of_day: Optional[str] = None
    time_of_day_label: str = "morning"  # "early_morning", "morning", "afternoon", "evening", "bedtime"
    meal_timing: str = "none"
    custom_meal_note: Optional[str] = None
    dose_quantity: int = 1
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    recurrence: str = "daily"
    days_of_week: str = "all"

    @model_validator(mode="before")
    @classmethod
    def sync_time_fields(cls, data: Any) -> Any:
        if isinstance(data, dict):
            if "time_of_day" in data and data["time_of_day"]:
                data["scheduled_time_str"] = data["time_of_day"]
            elif "scheduled_time_str" in data and data["scheduled_time_str"]:
                data["time_of_day"] = data["scheduled_time_str"]
        return data

    @field_validator("meal_timing")
    @classmethod
    def check_meal(cls, v: Optional[str]) -> str:
        return normalize_meal_context(v)

# Medication
class MedicationBase(BaseModel):
    name: str
    strength: Optional[str] = None
    dosage_form: str = "tablet"
    instructions: Optional[str] = None
    meal_context: str = "none"
    low_stock_threshold: int = 5
    prescribed_dose_qty: int = 1
    is_active: bool = True

    @field_validator("name")
    @classmethod
    def check_med_name(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("Medication name cannot be empty")
        return v.strip()

    @field_validator("meal_context")
    @classmethod
    def check_meal(cls, v: Optional[str]) -> str:
        return normalize_meal_context(v)

class MedicationCreate(MedicationBase):
    schedules: Optional[List[ScheduleCreateItem]] = None

class MedicationUpdate(BaseModel):
    name: Optional[str] = None
    strength: Optional[str] = None
    dosage_form: Optional[str] = None
    instructions: Optional[str] = None
    meal_context: Optional[str] = None
    low_stock_threshold: Optional[int] = None
    prescribed_dose_qty: Optional[int] = None
    is_active: Optional[bool] = None
    schedules: Optional[List[ScheduleCreateItem]] = None

    @field_validator("name")
    @classmethod
    def check_med_name(cls, v: Optional[str]) -> Optional[str]:
        return v.strip() if v else None

    @field_validator("meal_context")
    @classmethod
    def check_meal(cls, v: Optional[str]) -> Optional[str]:
        return normalize_meal_context(v) if v else None

class MedicationResponse(MedicationBase):
    id: str
    created_at: datetime
    assigned_cartridge_number: Optional[int] = None
    current_stock: Optional[int] = None
    schedules: List[Any] = []
    model_config = ConfigDict(from_attributes=True)

class MedicationDependencyResponse(BaseModel):
    medication_id: str
    medication_name: str
    can_hard_delete: bool
    has_active_cartridge: bool
    cartridge_number: Optional[int] = None
    current_stock: int = 0
    schedules_count: int = 0
    historical_doses_count: int = 0
    pending_doses_count: int = 0
    inventory_transactions_count: int = 0
    recommendation: str  # "archive" or "delete"
    warning_message: str

class MedicationDeactivateResponse(BaseModel):
    status: str  # "archived" or "deleted"
    message: str
    medication_id: str
    is_active: bool

# Prescription & Candidates
class PrescriptionCandidateSchema(BaseModel):
    id: str
    prescription_id: str
    medicine_name: str
    strength: Optional[str] = None
    prescribed_dose_qty: int = 1
    frequency: Optional[str] = None
    timing_hint: Optional[str] = None
    meal_instructions: Optional[str] = None
    confidence: float
    status: str
    notes: Optional[str] = None
    model_config = ConfigDict(from_attributes=True)

class PrescriptionResponse(BaseModel):
    id: str
    filename: str
    review_status: str
    raw_ocr_text: Optional[str] = None
    reviewed_by: Optional[str] = None
    reviewed_at: Optional[datetime] = None
    uploaded_at: datetime
    draft_json: Optional[str] = None
    extraction_engine: Optional[str] = "local_rule_engine"
    caregiver_notes: Optional[str] = None
    candidates: List[PrescriptionCandidateSchema] = []
    model_config = ConfigDict(from_attributes=True)

class PrescriptionPasteRequest(BaseModel):
    raw_text: str
    filename: Optional[str] = "Pasted Prescription"

class DraftReviewSubmission(BaseModel):
    prescription_id: str
    reviewed_by: str = "Marcus Vance (Caregiver)"
    target_cartridge_count: int = 4
    medications: List[Dict[str, Any]]
    schedules: List[Dict[str, Any]]
    cartridge_assignments: List[Dict[str, Any]]

class PhysicalCartridgeLoadItem(BaseModel):
    cartridge_number: int
    medication_name: str
    pill_count: int = Field(..., ge=1, le=30, description="Actual physical pill count loaded into the cartridge (1-30)")
    confirm_physical_loaded: bool = Field(..., description="Caregiver must explicitly check that pills are physically placed in slot")

class PhysicalLoadingSubmission(BaseModel):
    prescription_id: str
    loaded_by: str = "Marcus Vance (Caregiver)"
    cartridge_loads: List[PhysicalCartridgeLoadItem]

class PrescriptionActivateSubmission(BaseModel):
    prescription_id: str
    activated_by: str = "Marcus Vance (Caregiver)"
    notes: Optional[str] = None

class CandidateReviewItem(BaseModel):
    candidate_id: str
    action: str  # "accept", "reject", "modify"
    medicine_name: Optional[str] = None
    strength: Optional[str] = None
    prescribed_dose_qty: Optional[int] = None
    frequency: Optional[str] = None
    meal_instructions: Optional[str] = None
    assign_cartridge_number: Optional[int] = None
    initial_stock: Optional[int] = 0

class PrescriptionReviewSubmission(BaseModel):
    prescription_id: str
    reviewed_by: str = "Dr. Caregiver / Verified User"
    items: List[CandidateReviewItem]

# Cartridge
class CartridgeBase(BaseModel):
    cartridge_number: int
    device_id: str = "ESP32_PILLBOX_01"
    medication_id: Optional[str] = None
    current_stock: int = 0
    capacity: int = 30
    low_stock_threshold: int = 5
    is_configured: bool = False
    needs_reconciliation: bool = False
    quarantine_reason: Optional[str] = None
    calibration_offset_deg: float = 0.0

class CartridgeResponse(CartridgeBase):
    id: str
    last_refilled_at: Optional[datetime] = None
    medication_name: Optional[str] = None
    medication_strength: Optional[str] = None
    is_low_stock: bool = False
    model_config = ConfigDict(from_attributes=True)

class CartridgeSetupRequest(BaseModel):
    cartridge_number: int
    device_id: str = "ESP32_PILLBOX_01"
    medication_id: Optional[str] = None
    initial_stock: int = 0
    low_stock_threshold: int = 5
    confirm_physical_loaded: bool = False
    clear_reconciliation: bool = False

class CartridgeReconcileRequest(BaseModel):
    device_id: str = "ESP32_PILLBOX_01"
    reconciled_by: str = "Marcus Vance (Caregiver)"
    notes: Optional[str] = "Physically unloaded and verified slot is empty"
    confirm_physically_empty: bool = True

class CartridgeRefillRequest(BaseModel):
    cartridge_number: int
    device_id: str = "ESP32_PILLBOX_01"
    added_pills: int
    notes: Optional[str] = None

class DeviceHardwareConfigRequest(BaseModel):
    device_id: str = "ESP32_PILLBOX_01"
    cartridge_count: int = Field(..., description="Configured circular cartridge count: 4, 6, or 8")
    force: bool = Field(False, description="Force reconfiguration even if affected cartridges have stock/assignments")

# Schedule
class ScheduleBase(BaseModel):
    medication_id: str
    time_of_day_label: str = "morning"  # "early_morning", "morning", "afternoon", "evening", "bedtime"
    scheduled_time_str: str = "08:00"   # "HH:MM"
    meal_timing: str = "none"
    custom_meal_note: Optional[str] = None
    dose_quantity: int = 1
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    recurrence: str = "daily"
    days_of_week: str = "all"
    is_active: bool = True

    @field_validator("meal_timing")
    @classmethod
    def check_meal(cls, v: Optional[str]) -> str:
        return normalize_meal_context(v)

class ScheduleCreate(ScheduleBase):
    pass

class ScheduleUpdate(BaseModel):
    time_of_day_label: Optional[str] = None
    scheduled_time_str: Optional[str] = None
    meal_timing: Optional[str] = None
    custom_meal_note: Optional[str] = None
    dose_quantity: Optional[int] = None
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    recurrence: Optional[str] = None
    days_of_week: Optional[str] = None
    is_active: Optional[bool] = None

    @field_validator("meal_timing")
    @classmethod
    def check_meal(cls, v: Optional[str]) -> Optional[str]:
        return normalize_meal_context(v) if v else None

class ScheduleResponse(ScheduleBase):
    id: str
    created_at: datetime
    medication_name: Optional[str] = None
    cartridge_number: Optional[int] = None
    model_config = ConfigDict(from_attributes=True)

# Dose Occurrence
class DispensingOperationSchema(BaseModel):
    id: str
    attempt_number: int
    target_pills_this_attempt: int
    sensor1_detected_count: int
    status: str
    raw_telemetry: Optional[str] = None
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)

class DoseOccurrenceResponse(BaseModel):
    id: str
    schedule_id: Optional[str] = None
    medication_id: str
    cartridge_id: Optional[str] = None
    medication_name: Optional[str] = None
    medication_strength: Optional[str] = None
    cartridge_number: Optional[int] = None
    scheduled_for: datetime
    scheduled_time_local: str
    meal_context_snapshot: Optional[str] = None
    requested_pills: int
    confirmed_pills: int
    status: str
    is_due: bool = False
    can_dispense: bool = False
    seconds_until_due: Optional[int] = None
    command_id: Optional[str] = None
    dispense_initiated_at: Optional[datetime] = None
    manual_confirmed_at: Optional[datetime] = None
    pre_dose_10m_sent_at: Optional[datetime] = None
    pre_dose_5m_sent_at: Optional[datetime] = None
    dispensed_at: Optional[datetime] = None
    collected_at: Optional[datetime] = None
    pickup_reminder_sent_at: Optional[datetime] = None
    escalated_at: Optional[datetime] = None
    manual_confirmation_by: Optional[str] = None
    manual_confirmation_notes: Optional[str] = None
    fault_reason: Optional[str] = None
    correction_attempts_used: int = 0
    created_at: datetime
    operations: List[DispensingOperationSchema] = []
    model_config = ConfigDict(from_attributes=True)

class ManualConfirmRequest(BaseModel):
    confirmed_by: str = "Patient / Caregiver"
    notes: Optional[str] = None

# Hardware / Device API Contracts
class DeviceHeartbeatRequest(BaseModel):
    device_id: str
    firmware_version: str
    battery_pct: Optional[int] = None
    wifi_rssi: Optional[int] = None
    status: str = "idle"

class DeviceHeartbeatResponse(BaseModel):
    acknowledged: bool
    server_time: str
    cartridge_count: int = 4
    current_led_pattern: str
    current_buzzer_pattern: str
    pending_command: Optional[Dict[str, Any]] = None

class DispenseCommand(BaseModel):
    command_id: str
    dose_id: str
    cartridge_number: int
    requested_pills: int
    max_correction_attempts: int = 3

class DeviceDispenseResultReport(BaseModel):
    command_id: str
    dose_id: str
    cartridge_number: int
    requested_pills: int
    confirmed_pills: int
    correction_attempts: int
    status: str  # "success", "under_dispense", "over_dispense", "jam_fault", "sensor_uncertain"
    raw_telemetry: Optional[str] = None

class DevicePickupEventReport(BaseModel):
    device_id: str
    dose_id: Optional[str] = None
    is_collected: bool
    sensor2_raw_val: Optional[float] = None
    timestamp: Optional[datetime] = None

# Caregiver Alert
class CaregiverAlertResponse(BaseModel):
    id: str
    dose_occurrence_id: Optional[str] = None
    alert_type: str
    message: str
    recipient_contact: Optional[str] = None
    channel: str
    delivery_status: str
    provider_message_id: Optional[str] = None
    provider_response: Optional[str] = None
    acknowledged: bool
    acknowledged_by: Optional[str] = None
    acknowledged_at: Optional[datetime] = None
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)

class AlertAcknowledgeRequest(BaseModel):
    acknowledged_by: str = "Caregiver"

# Inventory Transaction
class InventoryTransactionResponse(BaseModel):
    id: str
    cartridge_id: str
    cartridge_number: Optional[int] = None
    medication_name: Optional[str] = None
    delta: int
    previous_stock: int
    new_stock: int
    reason: str
    confirmed_sensor_id: Optional[str] = None
    timestamp: datetime
    model_config = ConfigDict(from_attributes=True)

# Device State
class DeviceStateResponse(BaseModel):
    device_id: str
    cartridge_count: int = 4
    is_online: bool
    last_heartbeat: datetime
    firmware_version: str
    current_led_pattern: str
    current_buzzer_pattern: str
    active_dose_id: Optional[str] = None
    is_simulated: bool
    updated_at: datetime
    model_config = ConfigDict(from_attributes=True)

# Simulation Controls
class SimulationStepRequest(BaseModel):
    scenario: str
    # "dispense_perfect_2", "dispense_under_1_then_1", "dispense_over_fault",
    # "sensor_jam_fault", "pickup_detected", "fast_forward_5m", "fast_forward_10m",
    # "fast_forward_pre_dose_10m", "fast_forward_pre_dose_5m",
    # "simulate_offline", "simulate_online", "reset"
    dose_id: Optional[str] = None
    cartridge_number: Optional[int] = None
    simulated_pill_drop_count: Optional[int] = None

class DeviceModeRequest(BaseModel):
    mode: str = Field(..., description="Operating mode: 'simulated' or 'physical'")
    device_id: str = "ESP32_PILLBOX_01"

class DeviceConnectivityResponse(BaseModel):
    status: str
    badge_label: str
    badge_color: str
    is_simulated: bool
    is_online: bool
    telemetry_age_seconds: float
    device_id: str
    firmware_version: str
    cartridge_count: int
    current_led_pattern: str
    current_buzzer_pattern: str
    explanation: str
