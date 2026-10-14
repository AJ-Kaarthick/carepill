import {
  DoseOccurrence,
  Medication,
  Cartridge,
  Schedule,
  Prescription,
  CaregiverAlert,
  InventoryTransaction,
  DeviceState,
  SimulatorState,
  CaregiverSettings,
  DeviceHardwareConfig,
  DeviceConnectivity,
  CarePlanDraft
} from '../types';

const API_BASE = '/api';

export const api = {
  // Doses
  getTodayDoses: async (): Promise<DoseOccurrence[]> => {
    const res = await fetch(`${API_BASE}/doses/today`);
    if (!res.ok) throw new Error('Failed to fetch today doses');
    return res.json();
  },
  getCurrentDose: async (): Promise<DoseOccurrence | null> => {
    const res = await fetch(`${API_BASE}/doses/current`);
    if (!res.ok) return null;
    return res.json();
  },
  triggerDispense: async (doseId: string) => {
    const res = await fetch(`${API_BASE}/doses/${doseId}/dispense`, { method: 'POST' });
    if (!res.ok) {
      const err = await res.json();
      throw new Error(err.detail || 'Dispense failed');
    }
    return res.json();
  },
  simulateDispense: async (doseId: string) => {
    const res = await fetch(`${API_BASE}/doses/${doseId}/simulate-dispense`, { method: 'POST' });
    if (!res.ok) {
      const err = await res.json();
      throw new Error(err.detail || 'Simulated dispense failed');
    }
    return res.json();
  },
  cancelDispense: async (doseId: string) => {
    const res = await fetch(`${API_BASE}/doses/${doseId}/cancel-dispense`, { method: 'POST' });
    if (!res.ok) {
      const err = await res.json();
      throw new Error(err.detail || 'Cancel dispense failed');
    }
    return res.json();
  },
  recordSensor1Drop: async (doseId: string, detectedCount = 1, status = 'ok') => {
    const res = await fetch(`${API_BASE}/doses/${doseId}/sensor1-drop?detected_count=${detectedCount}&sensor_status=${status}`, {
      method: 'POST'
    });
    if (!res.ok) {
      const err = await res.json();
      throw new Error(err.detail || 'Sensor 1 drop recording failed');
    }
    return res.json();
  },
  recordPickup: async (doseId: string, isCollected = true) => {
    const res = await fetch(`${API_BASE}/doses/${doseId}/pickup?is_collected=${isCollected}`, {
      method: 'POST'
    });
    if (!res.ok) {
      const err = await res.json();
      throw new Error(err.detail || 'Pickup recording failed');
    }
    return res.json();
  },
  manualConfirmDose: async (doseId: string, confirmedBy = 'Patient', notes?: string) => {
    const res = await fetch(`${API_BASE}/doses/${doseId}/manual-confirm`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ confirmed_by: confirmedBy, notes })
    });
    if (!res.ok) {
      const err = await res.json();
      throw new Error(err.detail || 'Manual confirmation failed');
    }
    return res.json();
  },

  // Medications
  getMedications: async (): Promise<Medication[]> => {
    const res = await fetch(`${API_BASE}/medications/`);
    if (!res.ok) throw new Error('Failed to fetch medications');
    return res.json();
  },
  createMedication: async (data: Partial<Medication> & { schedules?: any[] }): Promise<Medication> => {
    const res = await fetch(`${API_BASE}/medications/`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(data)
    });
    if (!res.ok) {
      const err = await res.json();
      throw new Error(err.detail || 'Failed to create medication');
    }
    return res.json();
  },
  updateMedication: async (id: string, data: Partial<Medication> & { schedules?: any[] }): Promise<Medication> => {
    const res = await fetch(`${API_BASE}/medications/${id}`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(data)
    });
    if (!res.ok) {
      const err = await res.json();
      throw new Error(err.detail || 'Failed to update medication');
    }
    return res.json();
  },
  getMedicationDependencies: async (id: string) => {
    const res = await fetch(`${API_BASE}/medications/${id}/dependencies`);
    if (!res.ok) {
      const err = await res.json();
      throw new Error(err.detail || 'Failed to fetch medication dependencies');
    }
    return res.json();
  },
  deleteOrDeactivateMedication: async (id: string, force = false, caregiverName?: string, reason?: string) => {
    let url = `${API_BASE}/medications/${id}?force=${force}`;
    if (caregiverName) url += `&caregiver_name=${encodeURIComponent(caregiverName)}`;
    if (reason) url += `&reason=${encodeURIComponent(reason)}`;
    const res = await fetch(url, {
      method: 'DELETE'
    });
    if (!res.ok) {
      const err = await res.json();
      throw new Error(err.detail || 'Failed to remove or deactivate medication');
    }
    return res.json();
  },
  reactivateMedication: async (id: string): Promise<Medication> => {
    const res = await fetch(`${API_BASE}/medications/${id}/reactivate`, {
      method: 'POST'
    });
    if (!res.ok) {
      const err = await res.json();
      throw new Error(err.detail || 'Failed to reactivate medication');
    }
    return res.json();
  },

  // Cartridges
  getCartridges: async (deviceId?: string): Promise<Cartridge[]> => {
    const url = deviceId ? `${API_BASE}/cartridges/?device_id=${encodeURIComponent(deviceId)}` : `${API_BASE}/cartridges/`;
    const res = await fetch(url);
    if (!res.ok) throw new Error('Failed to fetch cartridges');
    return res.json();
  },
  setupCartridge: async (data: { cartridge_number: number; device_id?: string; medication_id?: string; initial_stock: number; low_stock_threshold: number; confirm_physical_loaded: boolean; clear_reconciliation?: boolean }) => {
    const res = await fetch(`${API_BASE}/cartridges/setup`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ device_id: 'ESP32_PILLBOX_01', ...data })
    });
    if (!res.ok) {
      const err = await res.json();
      throw new Error(err.detail || 'Failed to setup cartridge');
    }
    return res.json();
  },
  reconcileCartridge: async (cartridgeNumber: number, data?: { reconciled_by?: string; notes?: string; confirm_physically_empty?: boolean; device_id?: string }) => {
    const res = await fetch(`${API_BASE}/cartridges/${cartridgeNumber}/reconcile`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        device_id: data?.device_id || 'ESP32_PILLBOX_01',
        reconciled_by: data?.reconciled_by || 'Marcus Vance (Caregiver)',
        notes: data?.notes || 'Physically unloaded and verified slot is empty',
        confirm_physically_empty: data?.confirm_physically_empty ?? true
      })
    });
    if (!res.ok) {
      const err = await res.json();
      throw new Error(err.detail || 'Failed to clear cartridge reconciliation');
    }
    return res.json();
  },
  refillCartridge: async (cartridgeNumber: number, addedPills: number, notes?: string, deviceId = 'ESP32_PILLBOX_01') => {
    const res = await fetch(`${API_BASE}/cartridges/refill`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ cartridge_number: cartridgeNumber, added_pills: addedPills, notes, device_id: deviceId })
    });
    if (!res.ok) {
      const err = await res.json();
      throw new Error(err.detail || 'Refill failed');
    }
    return res.json();
  },
  getInventoryTransactions: async (): Promise<InventoryTransaction[]> => {
    const res = await fetch(`${API_BASE}/cartridges/transactions`);
    if (!res.ok) throw new Error('Failed to fetch transactions');
    return res.json();
  },

  // Schedules
  getSchedules: async (): Promise<Schedule[]> => {
    const res = await fetch(`${API_BASE}/schedules/`);
    if (!res.ok) throw new Error('Failed to fetch schedules');
    return res.json();
  },
  createSchedule: async (data: Partial<Schedule>): Promise<Schedule> => {
    const res = await fetch(`${API_BASE}/schedules/`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(data)
    });
    if (!res.ok) throw new Error('Failed to create schedule');
    return res.json();
  },

  // Prescriptions
  getPrescriptions: async (): Promise<Prescription[]> => {
    const res = await fetch(`${API_BASE}/prescriptions/`);
    if (!res.ok) throw new Error('Failed to fetch prescriptions');
    return res.json();
  },
  uploadPrescription: async (file: File): Promise<Prescription> => {
    const formData = new FormData();
    formData.append('file', file);
    const res = await fetch(`${API_BASE}/prescriptions/upload`, {
      method: 'POST',
      body: formData
    });
    if (!res.ok) {
      const err = await res.json();
      throw new Error(err.detail || 'Upload failed');
    }
    return res.json();
  },
  pastePrescription: async (text: string, filename = 'Pasted Prescription'): Promise<Prescription> => {
    const res = await fetch(`${API_BASE}/prescriptions/paste`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ raw_text: text, filename })
    });
    if (!res.ok) {
      const err = await res.json();
      throw new Error(err.detail || 'Paste intake failed');
    }
    return res.json();
  },
  getPrescriptionDraft: async (prescriptionId: string): Promise<CarePlanDraft> => {
    const res = await fetch(`${API_BASE}/prescriptions/${prescriptionId}/draft`);
    if (!res.ok) throw new Error('Failed to fetch prescription care plan draft');
    return res.json();
  },
  exportPrescriptionJsonUrl: (prescriptionId: string): string => {
    return `${API_BASE}/prescriptions/${prescriptionId}/export-json`;
  },
  reviewDraft: async (prescriptionId: string, data: any) => {
    const res = await fetch(`${API_BASE}/prescriptions/${prescriptionId}/review-draft`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(data)
    });
    if (!res.ok) {
      const err = await res.json();
      throw new Error(err.detail || 'Review draft failed');
    }
    return res.json();
  },
  confirmPhysicalLoading: async (prescriptionId: string, data: any) => {
    const res = await fetch(`${API_BASE}/prescriptions/${prescriptionId}/confirm-loading`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(data)
    });
    if (!res.ok) {
      const err = await res.json();
      throw new Error(err.detail || 'Loading confirmation failed');
    }
    return res.json();
  },
  activatePrescription: async (prescriptionId: string, data: any) => {
    const res = await fetch(`${API_BASE}/prescriptions/${prescriptionId}/activate`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(data)
    });
    if (!res.ok) {
      const err = await res.json();
      throw new Error(err.detail || 'Prescription activation failed');
    }
    return res.json();
  },
  reviewPrescription: async (data: any) => {
    const res = await fetch(`${API_BASE}/prescriptions/review`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(data)
    });
    if (!res.ok) {
      const err = await res.json();
      throw new Error(err.detail || 'Review submission failed');
    }
    return res.json();
  },

  // Caregiver
  getCaregiverDashboard: async () => {
    const res = await fetch(`${API_BASE}/caregiver/dashboard`);
    if (!res.ok) throw new Error('Failed to fetch caregiver dashboard');
    return res.json();
  },
  getCaregiverAlerts: async (): Promise<CaregiverAlert[]> => {
    const res = await fetch(`${API_BASE}/caregiver/alerts`);
    if (!res.ok) throw new Error('Failed to fetch alerts');
    return res.json();
  },
  getCaregiverSettings: async (): Promise<CaregiverSettings> => {
    const res = await fetch(`${API_BASE}/caregiver/settings`);
    if (!res.ok) throw new Error('Failed to fetch caregiver settings');
    return res.json();
  },
  updateCaregiverSettings: async (settings: Partial<CaregiverSettings>): Promise<CaregiverSettings> => {
    const res = await fetch(`${API_BASE}/caregiver/settings`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(settings)
    });
    if (!res.ok) {
      const err = await res.json();
      throw new Error(err.detail || 'Failed to update caregiver settings');
    }
    return res.json();
  },
  testNotification: async (data: { channel?: string; recipient_override?: string; custom_message?: string }) => {
    const res = await fetch(`${API_BASE}/caregiver/test-notification`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(data)
    });
    if (!res.ok) {
      const err = await res.json();
      throw new Error(err.detail || 'Test notification failed');
    }
    return res.json();
  },
  acknowledgeAlert: async (alertId: string, acknowledgedBy = 'Caregiver') => {
    const res = await fetch(`${API_BASE}/caregiver/alerts/${alertId}/acknowledge`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ acknowledged_by: acknowledgedBy })
    });
    if (!res.ok) throw new Error('Failed to acknowledge alert');
    return res.json();
  },

  // Device & Hardware
  getDeviceState: async (deviceId = 'ESP32_PILLBOX_01'): Promise<DeviceState> => {
    const res = await fetch(`${API_BASE}/device/state?device_id=${encodeURIComponent(deviceId)}`);
    if (!res.ok) throw new Error('Failed to fetch device state');
    return res.json();
  },
  getConnectivity: async (deviceId = 'ESP32_PILLBOX_01'): Promise<DeviceConnectivity> => {
    const res = await fetch(`${API_BASE}/device/connectivity?device_id=${encodeURIComponent(deviceId)}`);
    if (!res.ok) throw new Error('Failed to fetch hardware connectivity');
    return res.json();
  },
  setDeviceMode: async (mode: 'simulated' | 'physical', deviceId = 'ESP32_PILLBOX_01'): Promise<DeviceConnectivity> => {
    const res = await fetch(`${API_BASE}/device/mode`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ mode, device_id: deviceId })
    });
    if (!res.ok) throw new Error('Failed to update operating mode');
    return res.json();
  },
  configureDeviceHardware: async (config: DeviceHardwareConfig) => {
    const res = await fetch(`${API_BASE}/device/configure-hardware`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(config)
    });
    if (!res.ok) {
      const err = await res.json();
      throw err;
    }
    return res.json();
  },

  // Simulator
  getSimulatorState: async (): Promise<SimulatorState> => {
    const res = await fetch(`${API_BASE}/simulator/state`);
    if (!res.ok) throw new Error('Failed to fetch simulator state');
    return res.json();
  },
  triggerSimulationAction: async (scenario: string, extra?: any) => {
    const res = await fetch(`${API_BASE}/simulator/action`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ scenario, ...extra })
    });
    if (!res.ok) {
      const err = await res.json();
      throw new Error(err.detail || 'Simulation action failed');
    }
    return res.json();
  }
};
