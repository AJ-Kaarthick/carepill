import React, { useState } from 'react';
import {
  Pill,
  Plus,
  FileText,
  Layers,
  Utensils,
  AlertTriangle,
  CheckCircle2,
  Calendar,
  Clock,
  Trash2,
  Edit2,
  RotateCcw,
  Info,
  ShieldAlert,
  ChevronDown,
  ChevronUp,
  X
} from 'lucide-react';
import {
  Medication,
  Prescription,
  Schedule,
  MedicationDependencyResponse
} from '../types';
import { PrescriptionUploadModal } from '../components/PrescriptionUploadModal';
import { api } from '../services/api';

interface MedicinesPageProps {
  currentRole?: 'patient' | 'caregiver';
  medications: Medication[];
  prescriptions: Prescription[];
  onRefresh: () => void;
}

interface ScheduleDraft {
  time_of_day: string;
  time_of_day_label: string;
  dose_quantity: number;
  recurrence: string;
  start_date?: string;
  end_date?: string;
}

const MEAL_OPTIONS = [
  { value: 'none', label: 'No food relationship / Any time' },
  { value: 'before_breakfast', label: 'Before breakfast (empty stomach)' },
  { value: 'with_breakfast', label: 'With breakfast' },
  { value: 'after_breakfast', label: 'After breakfast' },
  { value: 'before_lunch', label: 'Before lunch' },
  { value: 'with_lunch', label: 'With lunch' },
  { value: 'after_lunch', label: 'After lunch' },
  { value: 'before_dinner', label: 'Before dinner' },
  { value: 'with_dinner', label: 'With dinner' },
  { value: 'after_dinner', label: 'After dinner' },
  { value: 'with_food', label: 'With food (generic)' }
];

const DOSAGE_FORMS = [
  { value: 'tablet', label: 'Tablet' },
  { value: 'capsule', label: 'Capsule' },
  { value: 'liquid', label: 'Liquid' },
  { value: 'drops', label: 'Drops' },
  { value: 'inhaler', label: 'Inhaler' },
  { value: 'patch', label: 'Skin Patch' }
];

export const MedicinesPage: React.FC<MedicinesPageProps> = ({
  currentRole = 'caregiver',
  medications,
  prescriptions,
  onRefresh
}) => {
  const [isRxModalOpen, setIsRxModalOpen] = useState(false);
  const [isFormOpen, setIsFormOpen] = useState(false);
  const [editingMed, setEditingMed] = useState<Medication | null>(null);

  // Form State
  const [name, setName] = useState('');
  const [strength, setStrength] = useState('');
  const [dosageForm, setDosageForm] = useState('tablet');
  const [instructions, setInstructions] = useState('');
  const [mealContext, setMealContext] = useState('with_breakfast');
  const [prescribedDoseQty, setPrescribedDoseQty] = useState(1);
  const [lowStock, setLowStock] = useState(5);
  const [schedules, setSchedules] = useState<ScheduleDraft[]>([
    {
      time_of_day: '08:00',
      time_of_day_label: 'morning',
      dose_quantity: 1,
      recurrence: 'daily'
    }
  ]);
  const [formSubmitting, setFormSubmitting] = useState(false);

  // Deletion / Archival Dependency Check State
  const [deactivatingMed, setDeactivatingMed] = useState<Medication | null>(null);
  const [dependencyInfo, setDependencyInfo] = useState<MedicationDependencyResponse | null>(null);
  const [loadingDep, setLoadingDep] = useState(false);
  const [actionInProgress, setActionInProgress] = useState(false);
  const [showArchived, setShowArchived] = useState(false);
  const [caregiverAuditName, setCaregiverAuditName] = useState('Marcus Vance (Caregiver)');
  const [caregiverAuditReason, setCaregiverAuditReason] = useState('Prescription discontinued / modified by physician');
  const [confirmPhysicalQuarantine, setConfirmPhysicalQuarantine] = useState(false);

  // Helpers
  const activeMedications = medications.filter((m) => m.is_active !== false);
  const archivedMedications = medications.filter((m) => m.is_active === false);

  const resetForm = () => {
    setEditingMed(null);
    setName('');
    setStrength('');
    setDosageForm('tablet');
    setInstructions('');
    setMealContext('with_breakfast');
    setPrescribedDoseQty(1);
    setLowStock(5);
    setSchedules([
      {
        time_of_day: '08:00',
        time_of_day_label: 'morning',
        dose_quantity: 1,
        recurrence: 'daily'
      }
    ]);
  };

  const handleOpenAddForm = () => {
    resetForm();
    setIsFormOpen(true);
  };

  const handleOpenEditForm = (med: Medication) => {
    setEditingMed(med);
    setName(med.name);
    setStrength(med.strength || '');
    setDosageForm(med.dosage_form || 'tablet');
    setInstructions(med.instructions || '');
    setMealContext(med.meal_context || 'none');
    setPrescribedDoseQty(med.prescribed_dose_qty || 1);
    setLowStock(med.low_stock_threshold || 5);

    if (med.schedules && med.schedules.length > 0) {
      setSchedules(
        med.schedules.map((s) => ({
          time_of_day: s.time_of_day || s.scheduled_time_str || '08:00',
          time_of_day_label: s.time_of_day_label || 'morning',
          dose_quantity: s.dose_quantity || 1,
          recurrence: s.recurrence || 'daily',
          start_date: s.start_date || undefined,
          end_date: s.end_date || undefined
        }))
      );
    } else {
      setSchedules([
        {
          time_of_day: '08:00',
          time_of_day_label: 'morning',
          dose_quantity: med.prescribed_dose_qty || 1,
          recurrence: 'daily'
        }
      ]);
    }

    setIsFormOpen(true);
  };

  const handleAddScheduleSlot = () => {
    setSchedules((prev) => [
      ...prev,
      {
        time_of_day: '20:00',
        time_of_day_label: 'evening',
        dose_quantity: prescribedDoseQty,
        recurrence: 'daily'
      }
    ]);
  };

  const handleRemoveScheduleSlot = (index: number) => {
    setSchedules((prev) => prev.filter((_, i) => i !== index));
  };

  const handleScheduleChange = (index: number, field: keyof ScheduleDraft, val: any) => {
    setSchedules((prev) => {
      const copy = [...prev];
      copy[index] = { ...copy[index], [field]: val };
      return copy;
    });
  };

  const handleSubmitMedication = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!name.trim()) return;

    setFormSubmitting(true);
    try {
      const payload: any = {
        name: name.trim(),
        strength: strength.trim(),
        dosage_form: dosageForm,
        instructions: instructions.trim(),
        meal_context: mealContext,
        prescribed_dose_qty: prescribedDoseQty,
        low_stock_threshold: lowStock,
        is_active: true,
        schedules: schedules.map((s) => ({
          time_of_day: s.time_of_day,
          time_of_day_label: s.time_of_day_label,
          dose_quantity: s.dose_quantity || prescribedDoseQty,
          meal_context: mealContext,
          recurrence: s.recurrence,
          start_date: s.start_date || undefined,
          end_date: s.end_date || undefined
        }))
      };

      if (editingMed) {
        await api.updateMedication(editingMed.id, payload);
      } else {
        await api.createMedication(payload);
      }

      setIsFormOpen(false);
      resetForm();
      onRefresh();
    } catch (err: any) {
      alert(`Error saving medication: ${err.message}`);
    } finally {
      setFormSubmitting(false);
    }
  };

  // Safe Archival Flow
  const handleInitiateDeactivation = async (med: Medication) => {
    setDeactivatingMed(med);
    setLoadingDep(true);
    setConfirmPhysicalQuarantine(false);
    setCaregiverAuditReason('Prescription discontinued / modified by physician');
    try {
      const dep = await api.getMedicationDependencies(med.id);
      setDependencyInfo(dep);
    } catch (err: any) {
      alert(`Failed to check dependencies: ${err.message}`);
      setDeactivatingMed(null);
    } finally {
      setLoadingDep(false);
    }
  };

  const handleConfirmDeactivation = async (force = false) => {
    if (!deactivatingMed) return;
    setActionInProgress(true);
    try {
      const res = await api.deleteOrDeactivateMedication(
        deactivatingMed.id,
        force,
        caregiverAuditName,
        caregiverAuditReason
      );
      alert(res.message);
      setDeactivatingMed(null);
      setDependencyInfo(null);
      onRefresh();
    } catch (err: any) {
      alert(`Action failed: ${err.message}`);
    } finally {
      setActionInProgress(false);
    }
  };

  const handleReactivate = async (medId: string) => {
    try {
      const res = await api.reactivateMedication(medId);
      alert(`Medication "${res.name}" reactivated successfully.`);
      onRefresh();
    } catch (err: any) {
      alert(`Reactivation failed: ${err.message}`);
    }
  };

  const formatMealContext = (mc: string) => {
    const opt = MEAL_OPTIONS.find((o) => o.value === mc);
    if (opt) return opt.label;
    return mc.replace(/_/g, ' ');
  };

  // PATIENT VIEW: Senior-Friendly, Calm, Read-Only Daily Medicines
  if (currentRole === 'patient') {
    return (
      <div className="space-y-6 pb-20">
        <div className="bg-white rounded-3xl p-5 sm:p-6 border border-[#E5E4E0] shadow-2xs">
          <span className="text-xs font-bold uppercase tracking-wider text-[#145A4A] flex items-center gap-1.5">
            <Pill className="w-3.5 h-3.5" />
            My Prescribed Medications
          </span>
          <h1 className="text-2xl sm:text-3xl font-black text-[#17313A] mt-1 tracking-tight">
            My Medicines
          </h1>
          <p className="text-sm text-[#4F6267] mt-1">
            Here are your current active prescriptions and scheduled dose times. Everything is managed safely by your pill dispenser.
          </p>
        </div>

        {activeMedications.length === 0 ? (
          <div className="p-8 text-center bg-white rounded-3xl border border-[#E5E4E0] text-[#4F6267]">
            <Pill className="w-8 h-8 text-stone-300 mx-auto mb-2" />
            <p className="text-sm font-semibold">No active medications registered right now.</p>
          </div>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {activeMedications.map((med) => (
              <div
                key={med.id}
                className="bg-white rounded-3xl p-5 sm:p-6 border border-[#E5E4E0] shadow-2xs space-y-4"
              >
                <div className="flex items-start justify-between gap-3">
                  <div className="flex items-center gap-3">
                    <div className="w-12 h-12 rounded-2xl bg-[#EAF2EC] flex items-center justify-center text-[#145A4A] shrink-0">
                      <Pill className="w-6 h-6" />
                    </div>
                    <div>
                      <h3 className="font-bold text-xl text-[#17313A]">{med.name}</h3>
                      <span className="text-xs font-semibold text-[#4F6267]">
                        {med.strength || 'Standard dose'} • {med.dosage_form || 'tablet'}
                      </span>
                    </div>
                  </div>

                  {med.assigned_cartridge_number ? (
                    <span className="text-xs font-bold px-3 py-1 rounded-xl bg-[#EAF2EC] text-[#145A4A] border border-[#c1dbca]">
                      Slot #{med.assigned_cartridge_number}
                    </span>
                  ) : (
                    <span className="text-xs font-semibold px-2.5 py-1 rounded-xl bg-stone-100 text-[#4F6267]">
                      Outside Dispenser
                    </span>
                  )}
                </div>

                {/* Instructions */}
                <p className="text-sm text-[#17313A] bg-[#F7F6F1] p-3 rounded-2xl border border-stone-200/70 font-medium leading-relaxed">
                  {med.instructions || 'Take as instructed by your physician.'}
                </p>

                {/* Scheduled Times */}
                <div className="space-y-1.5 pt-1">
                  <span className="text-xs font-bold text-[#4F6267] uppercase tracking-wider block">
                    Daily Schedule
                  </span>
                  {med.schedules && med.schedules.length > 0 ? (
                    <div className="flex flex-wrap gap-2">
                      {med.schedules.map((s, idx) => (
                        <div
                          key={idx}
                          className="px-3 py-1.5 rounded-xl bg-stone-50 border border-stone-200 text-xs font-bold text-[#17313A] flex items-center gap-1.5"
                        >
                          <Clock className="w-3.5 h-3.5 text-[#145A4A]" />
                          <span>{s.time_of_day || s.scheduled_time_str || 'Scheduled'}</span>
                          <span className="text-[#4F6267] font-semibold capitalize">
                            ({s.time_of_day_label || 'Scheduled'})
                          </span>
                        </div>
                      ))}
                    </div>
                  ) : (
                    <span className="text-xs text-[#4F6267] font-medium">Daily routine schedule</span>
                  )}
                </div>

                {/* Meal Relationship */}
                <div className="pt-3 border-t border-stone-100 flex items-center justify-between text-xs">
                  <span className="text-[#17313A] font-semibold flex items-center gap-1.5">
                    <Utensils className="w-4 h-4 text-[#145A4A]" />
                    {formatMealContext(med.meal_context)}
                  </span>
                  <span className="text-[#4F6267] font-medium">
                    {med.prescribed_dose_qty || 1} pill per dose
                  </span>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    );
  }

  // CAREGIVER VIEW: Full Management with Safe Deactivate, Add/Edit with Schedules
  return (
    <div className="space-y-6 pb-20">
      {/* Top Banner & Actions */}
      <div className="bg-white rounded-3xl p-5 sm:p-6 border border-[#E5E4E0] shadow-2xs flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-black text-[#17313A] tracking-tight">
            Prescriptions & Medications
          </h1>
          <p className="text-sm text-[#4F6267] mt-1">
            Verified medications, clock-time schedules, and physical cartridge assignments.
          </p>
        </div>

        <div className="flex items-center gap-2">
          <button
            onClick={() => setIsRxModalOpen(true)}
            className="px-4 py-2.5 rounded-xl bg-[#145A4A] hover:bg-[#0E4236] text-white font-bold text-xs flex items-center gap-1.5 shadow-xs transition-colors cursor-pointer"
          >
            <FileText className="w-4 h-4" />
            <span>Import Prescription (OCR)</span>
          </button>

          <button
            onClick={handleOpenAddForm}
            className="px-4 py-2.5 rounded-xl border border-stone-300 hover:bg-stone-100 text-[#17313A] font-bold text-xs flex items-center gap-1.5 transition-colors cursor-pointer"
          >
            <Plus className="w-4 h-4" />
            <span>Add Medication</span>
          </button>
        </div>
      </div>

      {/* Add / Edit Medication Modal */}
      {isFormOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/60 backdrop-blur-xs overflow-y-auto">
          <div className="bg-white rounded-3xl w-full max-w-2xl shadow-2xl border border-stone-200 p-6 space-y-4 my-8">
            <div className="flex items-center justify-between border-b border-stone-100 pb-3">
              <div>
                <h3 className="font-black text-lg text-[#17313A]">
                  {editingMed ? `Edit Medication: ${editingMed.name}` : 'Add New Medication'}
                </h3>
                <span className="text-xs text-[#4F6267]">
                  Configure clinical information and daily dispensing schedules.
                </span>
              </div>
              <button
                onClick={() => setIsFormOpen(false)}
                className="p-1 rounded-xl text-stone-400 hover:text-stone-700"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            <form onSubmit={handleSubmitMedication} className="space-y-4">
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 text-xs">
                <div>
                  <label className="block font-bold text-[#17313A] mb-1">
                    Medicine Name <span className="text-red-500">*</span>
                  </label>
                  <input
                    type="text"
                    required
                    placeholder="e.g. Metformin Hydrochloride"
                    value={name}
                    onChange={(e) => setName(e.target.value)}
                    className="w-full px-3 py-2 rounded-xl border border-stone-300 text-sm focus:outline-none focus:ring-2 focus:ring-[#145A4A]"
                  />
                </div>

                <div>
                  <label className="block font-bold text-[#17313A] mb-1">Strength:</label>
                  <input
                    type="text"
                    placeholder="e.g. 500mg"
                    value={strength}
                    onChange={(e) => setStrength(e.target.value)}
                    className="w-full px-3 py-2 rounded-xl border border-stone-300 text-sm focus:outline-none focus:ring-2 focus:ring-[#145A4A]"
                  />
                </div>

                <div>
                  <label className="block font-bold text-[#17313A] mb-1">Dosage Form:</label>
                  <select
                    value={dosageForm}
                    onChange={(e) => setDosageForm(e.target.value)}
                    className="w-full px-3 py-2 rounded-xl border border-stone-300 text-sm focus:outline-none focus:ring-2 focus:ring-[#145A4A]"
                  >
                    {DOSAGE_FORMS.map((df) => (
                      <option key={df.value} value={df.value}>
                        {df.label}
                      </option>
                    ))}
                  </select>
                </div>

                <div>
                  <label className="block font-bold text-[#17313A] mb-1">
                    Prescribed Dose Quantity (Pills):
                  </label>
                  <input
                    type="number"
                    min="1"
                    max="5"
                    value={prescribedDoseQty}
                    onChange={(e) => setPrescribedDoseQty(parseInt(e.target.value) || 1)}
                    className="w-full px-3 py-2 rounded-xl border border-stone-300 text-sm focus:outline-none focus:ring-2 focus:ring-[#145A4A]"
                  />
                </div>

                <div>
                  <label className="block font-bold text-[#17313A] mb-1">Meal Relationship:</label>
                  <select
                    value={mealContext}
                    onChange={(e) => setMealContext(e.target.value)}
                    className="w-full px-3 py-2 rounded-xl border border-stone-300 text-sm focus:outline-none focus:ring-2 focus:ring-[#145A4A]"
                  >
                    {MEAL_OPTIONS.map((opt) => (
                      <option key={opt.value} value={opt.value}>
                        {opt.label}
                      </option>
                    ))}
                  </select>
                </div>

                <div>
                  <label className="block font-bold text-[#17313A] mb-1">Low-Stock Alert Level:</label>
                  <input
                    type="number"
                    min="1"
                    max="20"
                    value={lowStock}
                    onChange={(e) => setLowStock(parseInt(e.target.value) || 5)}
                    className="w-full px-3 py-2 rounded-xl border border-stone-300 text-sm focus:outline-none focus:ring-2 focus:ring-[#145A4A]"
                  />
                </div>
              </div>

              <div>
                <label className="block text-xs font-bold text-[#17313A] mb-1">
                  Physician Instructions:
                </label>
                <input
                  type="text"
                  placeholder="e.g. Swallow whole with a full glass of water. Do not crush."
                  value={instructions}
                  onChange={(e) => setInstructions(e.target.value)}
                  className="w-full px-3 py-2 rounded-xl border border-stone-300 text-sm focus:outline-none focus:ring-2 focus:ring-[#145A4A]"
                />
              </div>

              {/* Exact Clock Time Schedules Builder */}
              <div className="border border-stone-200 rounded-2xl p-4 bg-[#F7F6F1] space-y-3">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <Clock className="w-4 h-4 text-[#145A4A]" />
                    <span className="text-xs font-bold text-[#17313A] uppercase tracking-wider">
                      Daily Dosing Times & Recurrence
                    </span>
                  </div>
                  <button
                    type="button"
                    onClick={handleAddScheduleSlot}
                    className="px-3 py-1 rounded-xl bg-white border border-stone-300 hover:border-stone-400 text-xs font-bold text-[#145A4A] flex items-center gap-1 shadow-2xs"
                  >
                    <Plus className="w-3.5 h-3.5" />
                    <span>Add Time</span>
                  </button>
                </div>

                <div className="space-y-2.5">
                  {schedules.map((slot, idx) => (
                    <div
                      key={idx}
                      className="p-3 bg-white rounded-xl border border-stone-200 flex flex-col sm:flex-row sm:items-center justify-between gap-3 text-xs"
                    >
                      <div className="flex flex-wrap items-center gap-2 flex-1">
                        <div>
                          <label className="block font-semibold text-[#4F6267] text-[10px] mb-0.5">
                            Clock Time:
                          </label>
                          <input
                            type="time"
                            required
                            value={slot.time_of_day}
                            onChange={(e) => handleScheduleChange(idx, 'time_of_day', e.target.value)}
                            className="px-2.5 py-1.5 rounded-lg border border-stone-300 font-bold text-xs"
                          />
                        </div>

                        <div>
                          <label className="block font-semibold text-[#4F6267] text-[10px] mb-0.5">
                            Label:
                          </label>
                          <select
                            value={slot.time_of_day_label}
                            onChange={(e) => handleScheduleChange(idx, 'time_of_day_label', e.target.value)}
                            className="px-2.5 py-1.5 rounded-lg border border-stone-300 font-semibold text-xs"
                          >
                            <option value="morning">Morning</option>
                            <option value="noon">Noon / Afternoon</option>
                            <option value="evening">Evening</option>
                            <option value="bedtime">Bedtime</option>
                          </select>
                        </div>

                        <div>
                          <label className="block font-semibold text-[#4F6267] text-[10px] mb-0.5">
                            Pills:
                          </label>
                          <input
                            type="number"
                            min="1"
                            max="5"
                            value={slot.dose_quantity}
                            onChange={(e) =>
                              handleScheduleChange(idx, 'dose_quantity', parseInt(e.target.value) || 1)
                            }
                            className="w-16 px-2.5 py-1.5 rounded-lg border border-stone-300 text-xs font-bold"
                          />
                        </div>

                        <div>
                          <label className="block font-semibold text-[#4F6267] text-[10px] mb-0.5">
                            Recurrence:
                          </label>
                          <select
                            value={slot.recurrence}
                            onChange={(e) => handleScheduleChange(idx, 'recurrence', e.target.value)}
                            className="px-2.5 py-1.5 rounded-lg border border-stone-300 font-semibold text-xs"
                          >
                            <option value="daily">Daily</option>
                            <option value="weekdays">Weekdays</option>
                            <option value="weekends">Weekends</option>
                          </select>
                        </div>
                      </div>

                      {schedules.length > 1 && (
                        <button
                          type="button"
                          onClick={() => handleRemoveScheduleSlot(idx)}
                          className="text-stone-400 hover:text-red-600 p-1 self-end sm:self-auto"
                          title="Remove Time Slot"
                        >
                          <Trash2 className="w-4 h-4" />
                        </button>
                      )}
                    </div>
                  ))}
                </div>
                <p className="text-[11px] text-[#4F6267] mt-1.5 italic">
                  * Autonomous rotary slots require recurring scheduled times. PRN (as-needed) medications are non-scheduled and taken manually on demand.
                </p>
              </div>

              <div className="flex justify-end gap-2 pt-2 border-t border-stone-100">
                <button
                  type="button"
                  onClick={() => setIsFormOpen(false)}
                  className="px-4 py-2.5 rounded-xl border border-stone-300 text-xs font-semibold text-[#4F6267] hover:bg-stone-50 cursor-pointer"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={formSubmitting}
                  className="px-6 py-2.5 rounded-xl bg-[#145A4A] hover:bg-[#0E4236] text-white text-xs font-bold shadow-xs transition-colors cursor-pointer disabled:opacity-50"
                >
                  {formSubmitting
                    ? 'Saving...'
                    : editingMed
                    ? 'Update Medication'
                    : 'Save Medication & Schedule'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Dependency Check / Safe Deactivation Modal */}
      {deactivatingMed && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/60 backdrop-blur-xs">
          <div className="bg-white rounded-3xl w-full max-w-md shadow-2xl border border-stone-200 p-6 space-y-4">
            <div className="flex items-center gap-3">
              <div
                className={`w-10 h-10 rounded-2xl flex items-center justify-center ${
                  dependencyInfo?.has_active_cartridge && dependencyInfo?.current_stock > 0
                    ? 'bg-amber-100 text-amber-700'
                    : 'bg-red-100 text-red-700'
                }`}
              >
                <ShieldAlert className="w-6 h-6" />
              </div>
              <div>
                <h3 className="font-black text-base text-[#17313A]">
                  {dependencyInfo?.can_hard_delete ? 'Delete Draft Medication' : 'Archive Medication'}
                </h3>
                <span className="text-xs text-[#4F6267]">{deactivatingMed.name}</span>
              </div>
            </div>

            {loadingDep ? (
              <div className="py-8 text-center text-xs text-[#4F6267]">
                <div className="w-6 h-6 border-2 border-[#145A4A] border-t-transparent rounded-full animate-spin mx-auto mb-2" />
                Analyzing clinical audit history and physical cartridge dependencies...
              </div>
            ) : dependencyInfo ? (
              <div className="space-y-3 text-xs">
                <p className="text-[#17313A] leading-relaxed bg-[#F7F6F1] p-3 rounded-2xl border border-stone-200">
                  {dependencyInfo.warning_message}
                </p>

                <div className="space-y-1.5 p-3 rounded-2xl bg-stone-50 border border-stone-200 text-[#4F6267]">
                  <div className="flex justify-between">
                    <span>Audit history logs:</span>
                    <span className="font-bold text-[#17313A]">
                      {dependencyInfo.historical_doses_count} past doses
                    </span>
                  </div>
                  <div className="flex justify-between">
                    <span>Inventory transactions:</span>
                    <span className="font-bold text-[#17313A]">
                      {dependencyInfo.inventory_transactions_count}
                    </span>
                  </div>
                  <div className="flex justify-between">
                    <span>Future doses to cancel:</span>
                    <span className="font-bold text-[#17313A]">
                      {dependencyInfo.pending_doses_count}
                    </span>
                  </div>
                  {dependencyInfo.has_active_cartridge && (
                    <div className="flex justify-between text-amber-800 font-semibold pt-1 border-t border-stone-200">
                      <span>Cartridge #{dependencyInfo.cartridge_number} Stock:</span>
                      <span className="font-bold">{dependencyInfo.current_stock} pills</span>
                    </div>
                  )}
                </div>

                {dependencyInfo.has_active_cartridge && dependencyInfo.current_stock > 0 && (
                  <div className="p-3.5 bg-rose-50 border border-rose-200 rounded-2xl space-y-2.5">
                    <div className="flex items-start gap-2 text-rose-900 font-bold text-xs">
                      <AlertTriangle className="w-4 h-4 text-rose-700 shrink-0 mt-0.5" />
                      <span>Safety Lock: Physical Pills Remain in Cartridge #{dependencyInfo.cartridge_number}</span>
                    </div>
                    <p className="text-[11px] text-rose-800 leading-relaxed">
                      Archiving will immediately lock Cartridge #{dependencyInfo.cartridge_number} in a
                      <strong> Quarantine (Stock Reconciliation)</strong> state. The rotary slot cannot be refilled, reassigned, or dispensed until physically emptied.
                    </p>
                    <div className="space-y-2 pt-1 text-xs">
                      <div>
                        <label className="block text-[11px] font-bold text-[#17313A] mb-1">Caregiver Name:</label>
                        <input
                          type="text"
                          value={caregiverAuditName}
                          onChange={(e) => setCaregiverAuditName(e.target.value)}
                          className="w-full px-3 py-1.5 rounded-xl border border-stone-300 text-xs font-semibold focus:outline-hidden focus:border-rose-600"
                        />
                      </div>
                      <div>
                        <label className="block text-[11px] font-bold text-[#17313A] mb-1">Archival & Reconciliation Reason:</label>
                        <input
                          type="text"
                          value={caregiverAuditReason}
                          onChange={(e) => setCaregiverAuditReason(e.target.value)}
                          className="w-full px-3 py-1.5 rounded-xl border border-stone-300 text-xs font-semibold focus:outline-hidden focus:border-rose-600"
                        />
                      </div>
                      <label className="flex items-start gap-2 pt-1 cursor-pointer">
                        <input
                          type="checkbox"
                          checked={confirmPhysicalQuarantine}
                          onChange={(e) => setConfirmPhysicalQuarantine(e.target.checked)}
                          className="mt-0.5 w-4 h-4 text-rose-700 rounded accent-rose-700"
                        />
                        <span className="text-[11px] text-rose-900 font-semibold leading-tight">
                          I acknowledge that {dependencyInfo.current_stock} pills remain in Cartridge #{dependencyInfo.cartridge_number} and require physical removal.
                        </span>
                      </label>
                    </div>
                  </div>
                )}

                <div className="flex items-center justify-end gap-2 pt-2">
                  <button
                    onClick={() => {
                      setDeactivatingMed(null);
                      setDependencyInfo(null);
                    }}
                    className="px-4 py-2.5 rounded-xl border border-stone-300 text-xs font-semibold text-[#4F6267] hover:bg-stone-50"
                  >
                    Keep Medication
                  </button>

                  {dependencyInfo.can_hard_delete ? (
                    <button
                      onClick={() => handleConfirmDeactivation(false)}
                      disabled={actionInProgress}
                      className="px-5 py-2.5 rounded-xl bg-red-600 hover:bg-red-700 text-white font-bold text-xs shadow-xs transition-colors"
                    >
                      {actionInProgress ? 'Deleting...' : 'Delete Draft'}
                    </button>
                  ) : dependencyInfo.has_active_cartridge && dependencyInfo.current_stock > 0 ? (
                    <button
                      onClick={() => handleConfirmDeactivation(true)}
                      disabled={actionInProgress || !confirmPhysicalQuarantine}
                      className="px-5 py-2.5 rounded-xl bg-rose-700 hover:bg-rose-800 disabled:opacity-50 text-white font-bold text-xs shadow-xs transition-colors"
                      title="Locks slot in quarantine and archives medication with audit record"
                    >
                      {actionInProgress ? 'Quarantining...' : 'Quarantine Slot & Archive'}
                    </button>
                  ) : (
                    <button
                      onClick={() => handleConfirmDeactivation(false)}
                      disabled={actionInProgress}
                      className="px-5 py-2.5 rounded-xl bg-red-600 hover:bg-red-700 text-white font-bold text-xs shadow-xs transition-colors"
                    >
                      {actionInProgress ? 'Archiving...' : 'Safe Archive (Cancel Future)'}
                    </button>
                  )}
                </div>
              </div>
            ) : null}
          </div>
        </div>
      )}

      {/* Medication Cards */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {activeMedications.map((med) => (
          <div
            key={med.id}
            className="bg-white rounded-3xl p-5 border border-[#E5E4E0] shadow-2xs space-y-3 flex flex-col justify-between"
          >
            <div>
              <div className="flex items-start justify-between gap-2">
                <div className="flex items-center gap-3">
                  <div className="w-10 h-10 rounded-2xl bg-[#EAF2EC] flex items-center justify-center text-[#145A4A] shrink-0">
                    <Pill className="w-5 h-5" />
                  </div>
                  <div>
                    <h3 className="font-bold text-lg text-[#17313A]">{med.name}</h3>
                    <span className="text-xs font-semibold text-[#4F6267]">
                      {med.strength || 'No strength specified'} • {med.dosage_form || 'tablet'}
                    </span>
                  </div>
                </div>

                {med.assigned_cartridge_number ? (
                  <span className="text-xs font-bold px-2.5 py-1 rounded-lg bg-[#EAF2EC] text-[#145A4A] border border-[#c1dbca]">
                    Slot {med.assigned_cartridge_number}
                  </span>
                ) : (
                  <span className="text-xs font-semibold px-2.5 py-1 rounded-lg bg-stone-100 text-[#4F6267]">
                    Unassigned
                  </span>
                )}
              </div>

              <p className="text-xs text-[#4F6267] mt-3 leading-relaxed">
                {med.instructions || 'Routine daily prescription.'}
              </p>

              {/* Schedules Preview */}
              {med.schedules && med.schedules.length > 0 && (
                <div className="mt-3 flex flex-wrap gap-1.5 text-[11px]">
                  {med.schedules.map((s, idx) => (
                    <span
                      key={idx}
                      className="px-2 py-0.5 rounded-md bg-[#F7F6F1] text-[#17313A] border border-stone-200 font-semibold"
                    >
                      {s.time_of_day || s.scheduled_time_str || 'Scheduled'} ({s.time_of_day_label || 'Dose'})
                    </span>
                  ))}
                </div>
              )}
            </div>

            <div>
              <div className="pt-3 border-t border-stone-100 flex items-center justify-between text-xs">
                <span className="text-[#4F6267] flex items-center gap-1">
                  <Utensils className="w-3.5 h-3.5 text-[#145A4A]" />
                  {med.meal_context ? med.meal_context.replace(/_/g, ' ') : 'any time'}
                </span>

                {med.current_stock !== undefined && med.current_stock !== null ? (
                  <span
                    className={`font-bold ${
                      med.current_stock <= med.low_stock_threshold
                        ? 'text-amber-800'
                        : 'text-emerald-800'
                    }`}
                  >
                    Stock: {med.current_stock} pills
                  </span>
                ) : null}
              </div>

              {/* Action Toolbar */}
              <div className="mt-3 pt-2.5 border-t border-stone-100 flex items-center justify-end gap-2">
                <button
                  type="button"
                  onClick={() => handleOpenEditForm(med)}
                  className="px-3 py-1.5 rounded-xl border border-stone-300 hover:bg-stone-50 text-xs font-bold text-[#17313A] flex items-center gap-1 transition-colors cursor-pointer"
                >
                  <Edit2 className="w-3.5 h-3.5 text-[#4F6267]" />
                  <span>Edit</span>
                </button>

                <button
                  type="button"
                  onClick={() => handleInitiateDeactivation(med)}
                  className="px-3 py-1.5 rounded-xl border border-red-200 hover:bg-red-50 text-xs font-bold text-red-700 flex items-center gap-1 transition-colors cursor-pointer"
                >
                  <Trash2 className="w-3.5 h-3.5" />
                  <span>Archive</span>
                </button>
              </div>
            </div>
          </div>
        ))}
      </div>

      {/* Archived Medications Section (Collapsible) */}
      {archivedMedications.length > 0 && (
        <div className="bg-white rounded-3xl border border-[#E5E4E0] shadow-2xs overflow-hidden">
          <button
            onClick={() => setShowArchived(!showArchived)}
            className="w-full p-4 sm:p-5 flex items-center justify-between text-left hover:bg-stone-50 transition-colors"
          >
            <div className="flex items-center gap-2">
              <RotateCcw className="w-4 h-4 text-[#4F6267]" />
              <span className="font-bold text-sm text-[#17313A]">
                Archived Inactive Medications ({archivedMedications.length})
              </span>
            </div>
            {showArchived ? (
              <ChevronUp className="w-4 h-4 text-stone-400" />
            ) : (
              <ChevronDown className="w-4 h-4 text-stone-400" />
            )}
          </button>

          {showArchived && (
            <div className="p-4 sm:p-5 pt-0 border-t border-stone-100 divide-y divide-stone-100">
              {archivedMedications.map((arch) => (
                <div key={arch.id} className="py-3 flex items-center justify-between gap-3 text-xs">
                  <div>
                    <span className="font-bold text-sm text-[#17313A] block">{arch.name}</span>
                    <span className="text-[#4F6267]">
                      {arch.strength} • Archived prescription history preserved
                    </span>
                  </div>

                  <button
                    onClick={() => handleReactivate(arch.id)}
                    className="px-3 py-1.5 rounded-xl bg-stone-100 hover:bg-[#145A4A] hover:text-white text-[#17313A] font-bold text-xs flex items-center gap-1 transition-colors"
                  >
                    <RotateCcw className="w-3.5 h-3.5" />
                    <span>Reactivate</span>
                  </button>
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {/* Prescription Import Records */}
      <div className="space-y-3 pt-2">
        <h2 className="text-xs font-black uppercase tracking-wider text-[#4F6267]">
          Prescription Attachments & Audit History
        </h2>

        {prescriptions.map((rx) => (
          <div
            key={rx.id}
            className="p-4 rounded-2xl bg-white border border-[#E5E4E0] flex items-center justify-between gap-3 text-xs"
          >
            <div className="flex items-center gap-3">
              <FileText className="w-5 h-5 text-[#145A4A]" />
              <div>
                <span className="font-bold text-sm text-[#17313A] block">{rx.filename}</span>
                <span className="text-[#4F6267]">
                  Uploaded {new Date(rx.uploaded_at).toLocaleDateString()}
                  {rx.reviewed_by ? ` • Verified by ${rx.reviewed_by}` : ''}
                </span>
              </div>
            </div>

            <span
              className={`px-3 py-1 rounded-full font-bold ${
                rx.review_status === 'confirmed'
                  ? 'bg-[#EAF2EC] text-[#145A4A]'
                  : 'bg-amber-100 text-amber-900'
              }`}
            >
              {rx.review_status === 'confirmed' ? 'Verified & Active' : 'Unreviewed'}
            </span>
          </div>
        ))}
      </div>

      {/* OCR Prescription Upload Modal */}
      <PrescriptionUploadModal
        isOpen={isRxModalOpen}
        onClose={() => setIsRxModalOpen(false)}
        onSuccess={onRefresh}
      />
    </div>
  );
};
