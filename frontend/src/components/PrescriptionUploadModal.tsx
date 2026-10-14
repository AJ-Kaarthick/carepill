import React, { useState } from 'react';
import {
  X,
  Upload,
  FileText,
  CheckCircle2,
  AlertTriangle,
  Layers,
  ArrowRight,
  ArrowLeft,
  Download,
  ShieldCheck,
  Check,
  Sparkles,
  Info,
  Calendar,
  Clock,
  Utensils
} from 'lucide-react';
import { Prescription, CarePlanDraft, ExtractedMedication, ProposedSchedule } from '../types';
import { api } from '../services/api';

interface PrescriptionUploadModalProps {
  isOpen: boolean;
  onClose: () => void;
  onSuccess: () => void;
}

export const PrescriptionUploadModal: React.FC<PrescriptionUploadModalProps> = ({
  isOpen,
  onClose,
  onSuccess
}) => {
  const [step, setStep] = useState<1 | 2 | 3 | 4>(1);
  const [intakeMode, setIntakeMode] = useState<'paste' | 'upload'>('paste');
  const [pasteText, setPasteText] = useState('');
  const [file, setFile] = useState<File | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Active Draft & Prescription Entity
  const [uploadedRx, setUploadedRx] = useState<Prescription | null>(null);
  const [draft, setDraft] = useState<CarePlanDraft | null>(null);

  // Step 2 Form States
  const [targetCartridgeCount, setTargetCartridgeCount] = useState<number>(4);
  const [medications, setMedications] = useState<ExtractedMedication[]>([]);
  const [schedules, setSchedules] = useState<ProposedSchedule[]>([]);

  // Step 3 Loading States
  const [cartridgeLoads, setCartridgeLoads] = useState<Array<{
    cartridge_number: number;
    medication_name: string;
    strength: string;
    pill_count: number;
    confirm_physical_loaded: boolean;
  }>>([]);

  // Step 4 Notes
  const [caregiverNotes, setCaregiverNotes] = useState('Reviewed and loaded in clinic by Marcus Vance (Caregiver).');
  const [activationSuccess, setActivationSuccess] = useState(false);

  if (!isOpen) return null;

  // STEP 1: Intake & Processing
  const handleTabSwitch = (mode: 'paste' | 'upload') => {
    setIntakeMode(mode);
    setError(null);
  };

  const handleLoadSample = () => {
    const sample =
      "Rx: Dr. Sarah Bennett, MD | Metro Geriatric Clinic\n" +
      "Patient: Eleanor Vance | DOB: 03/12/1948\n\n" +
      "1. Metformin 500mg - Take 1 tablet twice daily with breakfast and dinner\n" +
      "2. Lisinopril 10mg - Take 1 tablet once daily morning before breakfast\n" +
      "3. Atorvastatin 20mg - Take 1 tablet at bedtime\n" +
      "4. Omeprazole 20mg - Take 1 capsule once daily morning before meals\n" +
      "5. Robitussin Cough Syrup 10ml - Take 10ml as needed (PRN) for cough\n";
    setPasteText(sample);
    setError(null);
  };

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    setError(null);
    const selected = e.target.files?.[0];
    if (!selected) {
      setFile(null);
      return;
    }

    // Validate file size: maximum 10MB
    const MAX_SIZE = 10 * 1024 * 1024;
    if (selected.size > MAX_SIZE) {
      setError(`File size (${(selected.size / (1024 * 1024)).toFixed(1)}MB) exceeds the 10MB limit.`);
      setFile(null);
      e.target.value = '';
      return;
    }

    // Validate file extension
    const allowedExtensions = ['.jpg', '.jpeg', '.png', '.pdf', '.txt'];
    const ext = '.' + selected.name.split('.').pop()?.toLowerCase();
    const allowedMimePrefixes = ['image/jpeg', 'image/png', 'application/pdf', 'text/plain'];
    const isExtValid = allowedExtensions.includes(ext);
    const isMimeValid = allowedMimePrefixes.some(mime => selected.type.toLowerCase().includes(mime));

    if (!isExtValid && !isMimeValid) {
      setError(`Unsupported file type (${ext}). Please select a JPG, PNG, PDF, or TXT file.`);
      setFile(null);
      e.target.value = '';
      return;
    }

    setFile(selected);
  };

  const handleProcessIntake = async () => {
    setLoading(true);
    setError(null);
    try {
      let rx: Prescription;
      if (intakeMode === 'paste') {
        if (!pasteText.trim()) {
          throw new Error('Please paste prescription text or load the sample.');
        }
        rx = await api.pastePrescription(pasteText, 'Doctor_Prescription_Intake.txt');
      } else {
        if (!file) {
          throw new Error('Please select a prescription file (image, PDF, or TXT).');
        }
        rx = await api.uploadPrescription(file);
      }

      setUploadedRx(rx);

      // Load generated Care Plan Draft
      const draftData = await api.getPrescriptionDraft(rx.id);
      setDraft(draftData);
      setTargetCartridgeCount(draftData.hardware_proposal.recommended_cartridge_count || 4);
      setMedications(draftData.extracted_medications || []);
      setSchedules(draftData.proposed_schedules || []);

      // Pre-populate physical loading list for Step 3
      const loads = (draftData.hardware_proposal.cartridge_assignments || []).map((a) => ({
        cartridge_number: a.cartridge_number,
        medication_name: a.medicine_name,
        strength: a.strength || '',
        pill_count: 30, // suggested maximum
        confirm_physical_loaded: false
      }));
      setCartridgeLoads(loads);

      setStep(2);
    } catch (err: any) {
      setError(err.message || 'Prescription extraction failed.');
    } finally {
      setLoading(false);
    }
  };

  // STEP 2: Submit Medication & Schedule Review
  const handleReviewSubmit = async () => {
    if (!uploadedRx) return;
    setLoading(true);
    setError(null);
    try {
      const cartridgeAssignments = medications
        .filter((m) => m.is_dispenser_supported)
        .slice(0, targetCartridgeCount)
        .map((m, idx) => ({
          cartridge_number: idx + 1,
          medicine_name: m.medicine_name,
          strength: m.strength,
          dosage_form: m.dosage_form
        }));

      await api.reviewDraft(uploadedRx.id, {
        prescription_id: uploadedRx.id,
        reviewed_by: 'Marcus Vance (Caregiver)',
        target_cartridge_count: targetCartridgeCount,
        medications,
        schedules,
        cartridge_assignments: cartridgeAssignments
      });

      // Update cartridge loads for step 3 based on confirmed target assignments
      const loads = cartridgeAssignments.map((a) => ({
        cartridge_number: a.cartridge_number,
        medication_name: a.medicine_name,
        strength: a.strength || '',
        pill_count: 28,
        confirm_physical_loaded: false
      }));
      setCartridgeLoads(loads);

      setStep(3);
    } catch (err: any) {
      setError(err.message || 'Draft review failed.');
    } finally {
      setLoading(false);
    }
  };

  // STEP 3: Confirm Physical Loading
  const handleLoadingSubmit = async () => {
    if (!uploadedRx) return;
    setLoading(true);
    setError(null);

    // Validate that every cartridge has valid pill count and confirmation
    const invalid = cartridgeLoads.find(
      (c) => !c.confirm_physical_loaded || c.pill_count < 1 || c.pill_count > 30
    );
    if (invalid) {
      setError(
        `Cartridge ${invalid.cartridge_number} (${invalid.medication_name}) must have a valid physical count (1-30) and the physical verification box must be checked.`
      );
      setLoading(false);
      return;
    }

    try {
      await api.confirmPhysicalLoading(uploadedRx.id, {
        prescription_id: uploadedRx.id,
        loaded_by: 'Marcus Vance (Caregiver)',
        cartridge_loads: cartridgeLoads.map((c) => ({
          cartridge_number: c.cartridge_number,
          medication_name: c.medication_name,
          pill_count: Number(c.pill_count),
          confirm_physical_loaded: c.confirm_physical_loaded
        }))
      });
      setStep(4);
    } catch (err: any) {
      setError(err.message || 'Loading confirmation failed.');
    } finally {
      setLoading(false);
    }
  };

  // STEP 4: Activate Prescription
  const handleActivateSubmit = async () => {
    if (!uploadedRx) return;
    setLoading(true);
    setError(null);
    try {
      await api.activatePrescription(uploadedRx.id, {
        prescription_id: uploadedRx.id,
        activated_by: 'Marcus Vance (Caregiver)',
        notes: caregiverNotes
      });
      setActivationSuccess(true);
      setTimeout(() => {
        onSuccess();
        onClose();
      }, 1500);
    } catch (err: any) {
      setError(err.message || 'Activation failed.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-3 sm:p-4 bg-[#17313A]/60 backdrop-blur-xs overflow-y-auto">
      <div className="bg-white rounded-3xl w-full max-w-2xl max-h-[92vh] flex flex-col border border-[#E5E4E0] shadow-2xl overflow-hidden animate-in fade-in zoom-in-95">
        {/* Header with Step Progress Bar */}
        <div className="p-5 border-b border-[#E5E4E0] bg-[#F7F6F1]">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2.5">
              <div className="w-9 h-9 rounded-xl bg-[#145A4A] text-white flex items-center justify-center font-black text-sm">
                {step}
              </div>
              <div>
                <h2 className="text-lg font-black text-[#17313A]">
                  Prescription & Dispenser Setup Wizard
                </h2>
                <p className="text-xs text-[#4F6267] font-medium">
                  {step === 1 && 'Step 1 of 4: Prescription Intake & OCR Parsing'}
                  {step === 2 && 'Step 2 of 4: Medication Review & 4/6/8 Cartridge Sizing'}
                  {step === 3 && 'Step 3 of 4: Physical Loading & Actual Pill Count Verification'}
                  {step === 4 && 'Step 4 of 4: Final Verification & Schedule Activation'}
                </p>
              </div>
            </div>

            <button
              onClick={onClose}
              className="w-8 h-8 rounded-full bg-stone-200 hover:bg-stone-300 flex items-center justify-center text-[#17313A] transition-colors cursor-pointer"
            >
              <X className="w-4 h-4" />
            </button>
          </div>

          {/* Step Pill Indicators */}
          <div className="grid grid-cols-4 gap-1.5 mt-4">
            {[1, 2, 3, 4].map((s) => (
              <div
                key={s}
                className={`h-1.5 rounded-full transition-all ${
                  s === step
                    ? 'bg-[#145A4A]'
                    : s < step
                    ? 'bg-emerald-600'
                    : 'bg-stone-300'
                }`}
              />
            ))}
          </div>
        </div>

        {/* Modal Body */}
        <div className="p-5 overflow-y-auto space-y-4 flex-1">
          {error && (
            <div className="p-3.5 bg-red-50 border border-red-200 rounded-2xl text-xs text-red-900 font-semibold flex items-start gap-2">
              <AlertTriangle className="w-4 h-4 text-red-700 shrink-0 mt-0.5" />
              <span>{error}</span>
            </div>
          )}

          {/* ========================================================================= */}
          {/* STEP 1: PRESCRIPTION INTAKE                                               */}
          {/* ========================================================================= */}
          {step === 1 && (
            <div className="space-y-4">
              {/* Intake Mode Switcher */}
              <div className="flex bg-[#F7F6F1] p-1 rounded-xl border border-[#E5E4E0]">
                <button
                  type="button"
                  onClick={() => handleTabSwitch('paste')}
                  className={`flex-1 py-2 rounded-lg text-xs font-bold transition-all ${
                    intakeMode === 'paste'
                      ? 'bg-white text-[#145A4A] shadow-xs'
                      : 'text-[#4F6267] hover:text-[#17313A]'
                  }`}
                >
                  Paste Doctor's Prescription
                </button>
                <button
                  type="button"
                  onClick={() => handleTabSwitch('upload')}
                  className={`flex-1 py-2 rounded-lg text-xs font-bold transition-all ${
                    intakeMode === 'upload'
                      ? 'bg-white text-[#145A4A] shadow-xs'
                      : 'text-[#4F6267] hover:text-[#17313A]'
                  }`}
                >
                  Upload File / Photo
                </button>
              </div>

              {loading && (
                <div className="p-3 bg-emerald-50 border border-emerald-200 rounded-2xl text-xs text-emerald-900 font-semibold flex items-center gap-2.5 animate-pulse">
                  <div className="w-4 h-4 border-2 border-emerald-700 border-t-transparent rounded-full animate-spin shrink-0" />
                  <span>Extracting care plan and analyzing medication dosages...</span>
                </div>
              )}

              {intakeMode === 'paste' ? (
                <div className="space-y-2">
                  <div className="flex items-center justify-between">
                    <label className="text-xs font-bold text-[#17313A]">
                      Doctor Prescription Text:
                    </label>
                    <button
                      type="button"
                      onClick={handleLoadSample}
                      className="text-xs font-bold text-[#145A4A] hover:underline flex items-center gap-1 cursor-pointer"
                    >
                      <Sparkles className="w-3.5 h-3.5" />
                      Load Sample Prescription
                    </button>
                  </div>
                  <textarea
                    rows={8}
                    value={pasteText}
                    onChange={(e) => {
                      setPasteText(e.target.value);
                      if (error) setError(null);
                    }}
                    placeholder="e.g.&#10;Rx: Dr. Sarah Bennett, MD&#10;Patient: Eleanor Vance&#10;1. Metformin 500mg - Take 1 tablet twice daily with meals&#10;2. Lisinopril 10mg - Take 1 tablet once daily in morning"
                    className="w-full p-3.5 rounded-2xl border border-stone-300 text-xs font-mono focus:border-[#145A4A] focus:outline-hidden leading-relaxed"
                  />
                  <p className="text-[11px] text-[#4F6267]">
                    The local intelligence engine parses medication names, dosage strengths, solid forms, timing hints, and meal context automatically.
                  </p>
                </div>
              ) : (
                <div className="space-y-3">
                  <div className="border-2 border-dashed border-stone-300 rounded-2xl p-6 text-center hover:border-[#145A4A] transition-colors">
                    <Upload className="w-8 h-8 text-stone-400 mx-auto mb-2" />
                    <p className="text-xs font-bold text-[#17313A]">Upload Prescription PDF or Image</p>
                    <p className="text-[11px] text-[#4F6267] mt-1">Accepts JPG, PNG, PDF, or TXT up to 10MB</p>
                    <input
                      type="file"
                      accept=".jpg,.jpeg,.png,.pdf,.txt"
                      onChange={handleFileChange}
                      className="mt-3 text-xs text-[#4F6267]"
                    />
                  </div>
                  {file && (
                    <div className="p-3 bg-[#EAF2EC] rounded-xl text-xs font-bold text-[#145A4A] flex items-center gap-2">
                      <FileText className="w-4 h-4 shrink-0" />
                      <span>Selected: {file.name} ({(file.size / 1024).toFixed(1)} KB)</span>
                    </div>
                  )}
                </div>
              )}
            </div>
          )}

          {/* ========================================================================= */}
          {/* STEP 2: REVIEW MEDS & HARDWARE ALLOCATION                                  */}
          {/* ========================================================================= */}
          {step === 2 && draft && (
            <div className="space-y-4">
              {/* Prescriber & Patient Metadata */}
              <div className="p-3.5 bg-[#F7F6F1] rounded-2xl border border-[#E5E4E0] flex flex-wrap items-center justify-between gap-3 text-xs">
                <div>
                  <span className="text-[#4F6267] block">Physician</span>
                  <span className="font-bold text-[#17313A]">{draft.doctor_name || 'Dr. Prescribing Physician'}</span>
                </div>
                <div>
                  <span className="text-[#4F6267] block">Patient</span>
                  <span className="font-bold text-[#17313A]">{draft.patient_name || 'Eleanor Vance'}</span>
                </div>
                {uploadedRx && (
                  <button
                    onClick={() => window.open(api.exportPrescriptionJsonUrl(uploadedRx.id), '_blank')}
                    className="px-3 py-1.5 rounded-xl bg-white border border-stone-300 hover:bg-stone-50 text-xs font-bold text-[#145A4A] flex items-center gap-1.5 transition-colors cursor-pointer"
                    title="Download structured Care Plan Draft JSON"
                  >
                    <Download className="w-3.5 h-3.5" />
                    <span>Download Draft JSON</span>
                  </button>
                )}
              </div>

              {/* Hardware Sizing Allocation Selector */}
              <div className="p-4 bg-white rounded-2xl border border-[#145A4A]/30 shadow-2xs space-y-2">
                <div className="flex items-center justify-between">
                  <h3 className="text-xs font-bold uppercase tracking-wider text-[#145A4A] flex items-center gap-1.5">
                    <Layers className="w-4 h-4" />
                    Proposed Carousel Hardware Sizing
                  </h3>
                  <span className="text-xs font-extrabold text-[#17313A]">
                    {medications.filter((m) => m.is_dispenser_supported).length} solid oral medication(s)
                  </span>
                </div>

                <div className="flex items-center gap-2 pt-1">
                  {[4, 6, 8].map((count) => {
                    const isSelected = targetCartridgeCount === count;
                    const isRecommended = draft.hardware_proposal.recommended_cartridge_count === count;
                    return (
                      <button
                        key={count}
                        type="button"
                        onClick={() => setTargetCartridgeCount(count)}
                        className={`flex-1 py-2 px-3 rounded-xl border text-xs font-bold transition-all cursor-pointer ${
                          isSelected
                            ? 'bg-[#145A4A] text-white border-[#145A4A] shadow-xs'
                            : 'bg-stone-50 hover:bg-stone-100 text-[#4F6267] border-stone-200'
                        }`}
                      >
                        {count} Cartridges {isRecommended && '(Recommended)'}
                      </button>
                    );
                  })}
                </div>

                {draft.hardware_proposal.capacity_warning && (
                  <div className="p-2.5 bg-amber-50 border border-amber-200 rounded-xl text-xs text-amber-900 font-semibold flex items-center gap-2">
                    <AlertTriangle className="w-4 h-4 text-amber-700 shrink-0" />
                    <span>{draft.hardware_proposal.capacity_warning}</span>
                  </div>
                )}
              </div>

              {/* Extracted Medications List */}
              <div className="space-y-2">
                <h4 className="text-xs font-bold uppercase tracking-wider text-[#4F6267]">
                  Extracted Medications & Formulations
                </h4>

                <div className="space-y-2.5">
                  {medications.map((med, idx) => (
                    <div
                      key={idx}
                      className={`p-3.5 rounded-2xl border transition-all ${
                        med.is_dispenser_supported
                          ? 'bg-white border-[#E5E4E0]'
                          : 'bg-amber-50/60 border-amber-200'
                      }`}
                    >
                      <div className="flex items-start justify-between gap-3">
                        <div>
                          <div className="flex items-center gap-2">
                            <span className="font-black text-sm text-[#17313A]">{med.medicine_name}</span>
                            {med.strength && (
                              <span className="text-xs px-2 py-0.5 rounded-md font-bold bg-[#F7F6F1] text-[#4F6267]">
                                {med.strength}
                              </span>
                            )}
                            <span
                              className={`text-[10px] font-bold px-2 py-0.5 rounded-full ${
                                med.is_dispenser_supported
                                  ? 'bg-emerald-50 text-emerald-800 border border-emerald-200'
                                  : 'bg-amber-100 text-amber-900 border border-amber-300'
                              }`}
                            >
                              {med.is_dispenser_supported
                                ? `Cartridge Slot #${idx + 1}`
                                : 'Manual Administration (Non-Carousel)'}
                            </span>
                          </div>

                          <div className="flex flex-wrap items-center gap-3 mt-1.5 text-xs text-[#4F6267]">
                            <span className="flex items-center gap-1 font-medium">
                              <Clock className="w-3.5 h-3.5 text-stone-400" />
                              {med.frequency}
                            </span>
                            <span className="flex items-center gap-1 font-medium">
                              <Utensils className="w-3.5 h-3.5 text-stone-400" />
                              {med.meal_context.replace('_', ' ')}
                            </span>
                          </div>
                        </div>

                        <div className="text-right shrink-0">
                          <span className="text-xs font-bold text-[#145A4A]">
                            {med.prescribed_dose_qty} {med.dosage_form}
                          </span>
                        </div>
                      </div>

                      {med.unsupported_reason && (
                        <div className="mt-2 p-2 bg-amber-100/70 rounded-xl text-[11px] text-amber-900 font-semibold flex items-center gap-1.5">
                          <Info className="w-3.5 h-3.5 text-amber-700 shrink-0" />
                          <span>{med.unsupported_reason}</span>
                        </div>
                      )}
                    </div>
                  ))}
                </div>
              </div>
            </div>
          )}

          {/* ========================================================================= */}
          {/* STEP 3: PHYSICAL CARTRIDGE LOADING CONFIRMATION                            */}
          {/* ========================================================================= */}
          {step === 3 && (
            <div className="space-y-4">
              <div className="p-3.5 bg-amber-50 border border-amber-200 rounded-2xl text-xs text-amber-900 font-medium">
                <strong>Physical Loading Required:</strong> CarePill requires actual physical verification.
                For each circular cartridge, place the pills into the rotary carousel slot, enter the exact pill count (1–30),
                and check the verification box.
              </div>

              <div className="space-y-3">
                {cartridgeLoads.map((load, idx) => (
                  <div
                    key={load.cartridge_number}
                    className="p-4 bg-white rounded-2xl border border-[#E5E4E0] shadow-2xs space-y-3"
                  >
                    <div className="flex items-center justify-between">
                      <div className="flex items-center gap-3">
                        <div className="w-10 h-10 rounded-xl bg-[#EAF2EC] text-[#145A4A] flex items-center justify-center font-black text-sm">
                          C{load.cartridge_number}
                        </div>
                        <div>
                          <h4 className="font-black text-sm text-[#17313A]">{load.medication_name}</h4>
                          <span className="text-xs text-[#4F6267]">{load.strength || 'Standard Dose'}</span>
                        </div>
                      </div>

                      {/* Pill Count Input */}
                      <div className="flex items-center gap-2">
                        <label className="text-xs font-bold text-[#4F6267]">Loaded Pills:</label>
                        <input
                          type="number"
                          min={1}
                          max={30}
                          value={load.pill_count}
                          onChange={(e) => {
                            const val = Math.max(1, Math.min(30, Number(e.target.value) || 1));
                            const updated = [...cartridgeLoads];
                            updated[idx].pill_count = val;
                            setCartridgeLoads(updated);
                          }}
                          className="w-16 p-2 rounded-xl border border-stone-300 text-sm font-black text-center text-[#145A4A] focus:border-[#145A4A] focus:outline-hidden"
                        />
                      </div>
                    </div>

                    {/* Mandatory Physical Verification Checkbox */}
                    <label className="flex items-center gap-3 p-2.5 rounded-xl bg-[#F7F6F1] border border-stone-200 cursor-pointer hover:bg-stone-100 transition-colors">
                      <input
                        type="checkbox"
                        checked={load.confirm_physical_loaded}
                        onChange={(e) => {
                          const updated = [...cartridgeLoads];
                          updated[idx].confirm_physical_loaded = e.target.checked;
                          setCartridgeLoads(updated);
                        }}
                        className="w-4 h-4 text-[#145A4A] rounded accent-[#145A4A] cursor-pointer"
                      />
                      <span className="text-xs font-semibold text-[#17313A]">
                        I physically verified that {load.pill_count} pills of {load.medication_name} are placed in Cartridge {load.cartridge_number}.
                      </span>
                    </label>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* ========================================================================= */}
          {/* STEP 4: FINAL VERIFICATION & ACTIVATION                                   */}
          {/* ========================================================================= */}
          {step === 4 && (
            <div className="space-y-4">
              {activationSuccess ? (
                <div className="py-8 text-center space-y-3 animate-in zoom-in-95">
                  <div className="w-16 h-16 rounded-full bg-emerald-100 text-emerald-700 flex items-center justify-center mx-auto shadow-sm">
                    <CheckCircle2 className="w-10 h-10 fill-emerald-600 text-white" />
                  </div>
                  <h3 className="text-xl font-black text-[#17313A]">Care Plan Activated!</h3>
                  <p className="text-xs text-[#4F6267] max-w-sm mx-auto">
                    The dispenser hardware has been initialized with {cartridgeLoads.length} configured cartridges.
                    Offline schedules have been synced to LittleFS memory.
                  </p>
                </div>
              ) : (
                <>
                  <div className="p-4 bg-[#EAF2EC] border border-[#c1dbca] rounded-2xl text-xs text-[#145A4A] space-y-1.5">
                    <div className="flex items-center gap-1.5 font-bold text-sm">
                      <ShieldCheck className="w-5 h-5 text-[#145A4A]" />
                      <span>Ready for Activation</span>
                    </div>
                    <p className="text-xs leading-relaxed">
                      Activation will record an auditable clinical event, configure the physical dispenser slots,
                      and synchronize the autonomous schedule to ESP32 LittleFS flash memory.
                      <strong> It will NOT trigger an immediate unprompted dispense.</strong>
                    </p>
                  </div>

                  <div className="p-4 bg-white rounded-2xl border border-[#E5E4E0] space-y-3">
                    <h4 className="text-xs font-bold uppercase tracking-wider text-[#4F6267]">
                      Caregiver Verification Notes
                    </h4>
                    <textarea
                      rows={3}
                      value={caregiverNotes}
                      onChange={(e) => setCaregiverNotes(e.target.value)}
                      placeholder="Enter verification notes or instructions for Eleanor..."
                      className="w-full p-3 rounded-xl border border-stone-300 text-xs focus:border-[#145A4A] focus:outline-hidden"
                    />
                  </div>
                </>
              )}
            </div>
          )}
        </div>

        {/* Footer Actions */}
        <div className="p-4 border-t border-[#E5E4E0] bg-[#F7F6F1] flex items-center justify-between gap-3">
          {step > 1 && !activationSuccess && (
            <button
              type="button"
              onClick={() => setStep((prev) => (prev - 1) as any)}
              className="px-4 py-2.5 rounded-xl border border-stone-300 bg-white hover:bg-stone-50 text-xs font-bold text-[#17313A] flex items-center gap-1.5 transition-colors cursor-pointer"
            >
              <ArrowLeft className="w-4 h-4" />
              <span>Back</span>
            </button>
          )}

          <div className="ml-auto flex items-center gap-2">
            <button
              type="button"
              onClick={onClose}
              className="px-4 py-2.5 rounded-xl border border-stone-300 bg-white hover:bg-stone-50 text-xs font-bold text-[#4F6267] transition-colors cursor-pointer"
            >
              Cancel
            </button>

            {step === 1 && (
              <button
                type="button"
                disabled={loading}
                onClick={handleProcessIntake}
                className="px-5 py-2.5 rounded-xl bg-[#145A4A] hover:bg-[#0E4236] disabled:opacity-50 text-white font-bold text-xs flex items-center gap-1.5 transition-all shadow-xs cursor-pointer"
              >
                {loading ? (
                  <>
                    <div className="w-3.5 h-3.5 border-2 border-white border-t-transparent rounded-full animate-spin" />
                    <span>Extracting Care Plan...</span>
                  </>
                ) : (
                  <>
                    <span>Extract Care Plan</span>
                    <ArrowRight className="w-4 h-4" />
                  </>
                )}
              </button>
            )}

            {step === 2 && (
              <button
                type="button"
                disabled={loading}
                onClick={handleReviewSubmit}
                className="px-5 py-2.5 rounded-xl bg-[#145A4A] hover:bg-[#0E4236] disabled:opacity-50 text-white font-bold text-xs flex items-center gap-1.5 transition-all shadow-xs cursor-pointer"
              >
                <span>Confirm & Proceed to Loading</span>
                <ArrowRight className="w-4 h-4" />
              </button>
            )}

            {step === 3 && (
              <button
                type="button"
                disabled={loading || cartridgeLoads.some((c) => !c.confirm_physical_loaded)}
                onClick={handleLoadingSubmit}
                className="px-5 py-2.5 rounded-xl bg-[#145A4A] hover:bg-[#0E4236] disabled:opacity-50 text-white font-bold text-xs flex items-center gap-1.5 transition-all shadow-xs cursor-pointer"
              >
                <span>Verify & Proceed to Activation</span>
                <ArrowRight className="w-4 h-4" />
              </button>
            )}

            {step === 4 && !activationSuccess && (
              <button
                type="button"
                disabled={loading}
                onClick={handleActivateSubmit}
                className="px-6 py-2.5 rounded-xl bg-emerald-700 hover:bg-emerald-800 disabled:opacity-50 text-white font-black text-xs flex items-center gap-1.5 transition-all shadow-xs cursor-pointer"
              >
                <Check className="w-4 h-4" />
                <span>Activate Medication Plan</span>
              </button>
            )}
          </div>
        </div>
      </div>
    </div>
  );
};
