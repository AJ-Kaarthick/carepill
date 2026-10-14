export type DoseStatus =
  | 'scheduled'
  | 'pre_dose_reminder'
  | 'dispensing'
  | 'dispensing_verification'
  | 'corrective_dispensing'
  | 'dispensed'
  | 'awaiting_collection'
  | 'collection_reminder'
  | 'collected'
  | 'confirmed_taken'
  | 'escalated'
  | 'dispensing_fault'
  | 'sensor_fault'
  | 'missed';

export interface DispensingOperation {
  id: string;
  attempt_number: number;
  target_pills_this_attempt: number;
  sensor1_detected_count: number;
  status: string;
  raw_telemetry?: string;
  created_at: string;
}

export interface DoseOccurrence {
  id: string;
  schedule_id?: string;
  medication_id: string;
  cartridge_id?: string;
  medication_name: string;
  medication_strength?: string;
  cartridge_number?: number;
  scheduled_for: string;
  scheduled_time_local: string;
  meal_context_snapshot?: string;
  requested_pills: number;
  confirmed_pills: number;
  status: DoseStatus;
  is_due?: boolean;
  can_dispense?: boolean;
  seconds_until_due?: number;
  command_id?: string;
  dispense_initiated_at?: string;
  manual_confirmed_at?: string;
  dispensed_at?: string;
  collected_at?: string;
  pickup_reminder_sent_at?: string;
  escalated_at?: string;
  manual_confirmation_by?: string;
  manual_confirmation_notes?: string;
  fault_reason?: string;
  correction_attempts_used: number;
  created_at: string;
  operations?: DispensingOperation[];
}

export interface Medication {
  id: string;
  name: string;
  strength?: string;
  dosage_form: string;
  instructions?: string;
  meal_context: string;
  low_stock_threshold: number;
  prescribed_dose_qty?: number;
  is_active: boolean;
  assigned_cartridge_number?: number;
  current_stock?: number;
  schedules?: Schedule[];
  created_at: string;
}

export interface Cartridge {
  id: string;
  device_id?: string;
  cartridge_number: number;
  medication_id?: string;
  medication_name?: string;
  medication_strength?: string;
  current_stock: number;
  capacity: number;
  low_stock_threshold: number;
  is_configured: boolean;
  needs_reconciliation?: boolean;
  quarantine_reason?: string;
  is_low_stock: boolean;
  calibration_offset_deg: number;
  last_refilled_at?: string;
}

export interface Schedule {
  id: string;
  medication_id: string;
  medication_name?: string;
  cartridge_number?: number;
  time_of_day_label: 'early_morning' | 'morning' | 'afternoon' | 'evening' | 'bedtime' | string;
  scheduled_time_str?: string;
  time_of_day?: string;
  meal_timing?: string;
  meal_context?: string;
  custom_meal_note?: string;
  dose_quantity: number;
  start_date?: string;
  end_date?: string;
  recurrence?: string;
  days_of_week?: string;
  is_active: boolean;
}

export interface MedicationDependencyResponse {
  medication_id: string;
  medication_name: string;
  can_hard_delete: boolean;
  has_active_cartridge: boolean;
  cartridge_number?: number;
  current_stock: number;
  schedules_count: number;
  historical_doses_count: number;
  pending_doses_count: number;
  inventory_transactions_count: number;
  recommendation: 'archive' | 'delete' | string;
  warning_message: string;
}

export interface MedicationDeactivateResponse {
  status: 'archived' | 'deleted';
  message: string;
  medication_id: string;
  is_active: boolean;
}

export interface PrescriptionCandidate {
  id: string;
  prescription_id: string;
  medicine_name: string;
  strength?: string;
  prescribed_dose_qty: number;
  frequency?: string;
  timing_hint?: string;
  meal_instructions?: string;
  confidence: number;
  status: string;
  notes?: string;
}

export interface Prescription {
  id: string;
  filename: string;
  review_status: 'unreviewed' | 'draft_reviewed' | 'schedule_reviewed' | 'loaded' | 'confirmed' | 'rejected';
  raw_ocr_text?: string;
  reviewed_by?: string;
  reviewed_at?: string;
  uploaded_at: string;
  draft_json?: string;
  extraction_engine?: string;
  caregiver_notes?: string;
  candidates: PrescriptionCandidate[];
}

export interface ExtractedMedication {
  medicine_name: string;
  strength: string | null;
  dosage_form: string;
  prescribed_dose_qty: number;
  frequency: string;
  timing_hint: string;
  meal_context: string;
  duration?: string;
  refills?: number;
  is_dispenser_supported: boolean;
  unsupported_reason?: string | null;
  warnings: string[];
  confidence: number;
  raw_line?: string;
}

export interface CartridgeAssignmentProposal {
  cartridge_number: number;
  medicine_name: string;
  strength?: string | null;
  dosage_form?: string;
  requires_manual_loading?: boolean;
  suggested_initial_stock?: number;
}

export interface HardwareProposal {
  recommended_cartridge_count: number;
  total_supported_medicines: number;
  cartridge_assignments: CartridgeAssignmentProposal[];
  unassigned_medicines: string[];
  unsupported_medicines: Array<{
    medicine_name: string;
    strength?: string | null;
    dosage_form?: string;
    reason?: string | null;
  }>;
  capacity_warning?: string | null;
}

export interface ProposedSchedule {
  medication_name: string;
  time_of_day_label: string;
  scheduled_time_str: string;
  meal_timing: string;
  dose_quantity: number;
}

export interface CarePlanDraft {
  source_filename?: string;
  extracted_at?: string;
  doctor_name?: string;
  patient_name?: string;
  raw_text?: string;
  extracted_medications: ExtractedMedication[];
  hardware_proposal: HardwareProposal;
  proposed_schedules: ProposedSchedule[];
  status?: string;
}

export interface DeviceConnectivity {
  status: 'demo_simulated' | 'physical_online' | 'physical_stale' | 'physical_offline' | 'hardware_fault';
  badge_label: string;
  badge_color: string;
  is_simulated: boolean;
  is_online: boolean;
  telemetry_age_seconds: number;
  device_id: string;
  firmware_version: string;
  cartridge_count: number;
  current_led_pattern: string;
  current_buzzer_pattern: string;
  explanation: string;
}

export interface CaregiverAlert {
  id: string;
  dose_occurrence_id?: string;
  alert_type: string;
  message: string;
  recipient_contact?: string;
  channel: string;
  delivery_status: 'simulated' | 'queued' | 'sent' | 'delivered' | 'failed';
  provider_message_id?: string;
  provider_response?: string;
  acknowledged: boolean;
  acknowledged_by?: string;
  acknowledged_at?: string;
  created_at: string;
}

export interface InventoryTransaction {
  id: string;
  cartridge_id: string;
  cartridge_number?: number;
  medication_name?: string;
  delta: number;
  previous_stock: number;
  new_stock: number;
  reason: string;
  confirmed_sensor_id?: string;
  timestamp: string;
}

export interface DeviceState {
  device_id: string;
  cartridge_count: number;
  is_online: boolean;
  last_heartbeat: string;
  firmware_version: string;
  current_led_pattern: string;
  current_buzzer_pattern: string;
  active_dose_id?: string;
  is_simulated: boolean;
  updated_at: string;
}

export interface SimulatorState {
  virtual_clock_now: string;
  device_online: boolean;
  cartridge_count?: number;
  current_led_pattern: string;
  current_buzzer_pattern: string;
  active_dose_id?: string;
  active_dose_status?: string;
  active_dose_requested?: number;
  active_dose_confirmed?: number;
  dispensed_at?: string;
  minutes_elapsed_since_dispense: number;
}

export interface CaregiverSettings {
  id: string;
  name: string;
  role: string;
  phone?: string;
  whatsapp_phone?: string;
  notification_channel: 'simulated' | 'sms' | 'whatsapp' | 'webhook';
  sms_consent: boolean;
  whatsapp_consent: boolean;
}

export interface DeviceHardwareConfig {
  device_id: string;
  cartridge_count: number;
  force?: boolean;
}
