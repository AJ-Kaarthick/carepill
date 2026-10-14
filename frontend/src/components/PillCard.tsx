import React, { useState } from 'react';
import {
  CheckCircle2,
  Clock,
  AlertTriangle,
  Play,
  RotateCcw,
  Hand,
  ChevronDown,
  ChevronUp,
  Info,
  Layers,
  Utensils,
  Sparkles,
  XCircle
} from 'lucide-react';
import { DoseOccurrence } from '../types';

interface PillCardProps {
  dose: DoseOccurrence;
  isCurrent?: boolean;
  isSimulated?: boolean;
  onDispense: (doseId: string) => void;
  onSimulateDispense?: (doseId: string) => void;
  onCancelDispense?: (doseId: string) => void;
  onPickup: (doseId: string) => void;
  onManualConfirm?: (doseId: string) => void;
}

export const PillCard: React.FC<PillCardProps> = ({
  dose,
  isCurrent = false,
  isSimulated = true,
  onDispense,
  onSimulateDispense,
  onCancelDispense,
  onPickup,
  onManualConfirm
}) => {
  const [expanded, setExpanded] = useState(false);

  // Format meal label
  const formatMealLabel = (meal?: string) => {
    if (!meal || meal === 'none') return 'No meal requirement';
    return meal
      .split('_')
      .map((w) => w.charAt(0).toUpperCase() + w.slice(1))
      .join(' ');
  };

  // Status Badge Configuration
  const getStatusConfig = (status: string) => {
    switch (status) {
      case 'confirmed_taken':
        return {
          bg: 'bg-emerald-50',
          text: 'text-emerald-900 font-bold',
          border: 'border-emerald-300',
          icon: CheckCircle2,
          label: 'Confirmed Taken (Ingested)'
        };
      case 'collected':
        return {
          bg: 'bg-[#EAF2EC]',
          text: 'text-[#145A4A] font-semibold',
          border: 'border-[#c1dbca]',
          icon: Hand,
          label: 'Collected from Tray'
        };
      case 'awaiting_collection':
        return {
          bg: 'bg-[#FEF3C7]',
          text: 'text-[#9A6700] font-bold',
          border: 'border-[#fcd34d]',
          icon: Clock,
          label: 'Awaiting Pickup in Tray'
        };
      case 'collection_reminder':
        return {
          bg: 'bg-amber-100',
          text: 'text-amber-900 font-bold',
          border: 'border-amber-400',
          icon: AlertTriangle,
          label: '5-Min Reminder: Uncollected'
        };
      case 'escalated':
        return {
          bg: 'bg-[#FEE2E2]',
          text: 'text-[#B91C1C] font-black',
          border: 'border-[#fca5a5]',
          icon: AlertTriangle,
          label: '10-Min Escalated to Caregiver'
        };
      case 'dispensing':
      case 'corrective_dispensing':
        return {
          bg: 'bg-blue-50',
          text: 'text-blue-800 font-semibold',
          border: 'border-blue-300',
          icon: RotateCcw,
          label: status === 'corrective_dispensing' ? 'Correcting Pill Count...' : 'Dispensing Underway...'
        };
      case 'dispensing_fault':
      case 'sensor_fault':
        return {
          bg: 'bg-red-50',
          text: 'text-red-800 font-bold',
          border: 'border-red-300',
          icon: AlertTriangle,
          label: 'Dispenser Safety Fault'
        };
      default:
        return {
          bg: 'bg-[#F7F6F1]',
          text: 'text-[#4F6267]',
          border: 'border-[#E5E4E0]',
          icon: Clock,
          label: 'Scheduled'
        };
    }
  };

  const statusConfig = getStatusConfig(dose.status);
  const StatusIcon = statusConfig.icon;

  // Determine if actionable for dispensing
  const canDispenseNow = dose.can_dispense ?? (dose.status === 'scheduled');

  return (
    <div
      className={`rounded-2xl bg-white border transition-all ${
        isCurrent
          ? 'border-[#145A4A] ring-2 ring-[#145A4A]/20 shadow-sm'
          : 'border-[#E5E4E0] shadow-2xs hover:border-[#CBD5E1]'
      }`}
    >
      <div className="p-4 sm:p-5">
        {/* 1. Scheduled Time & Meal Label */}
        <div className="flex items-center justify-between gap-2 pb-2 border-b border-[#F7F6F1]">
          <div className="flex items-center gap-2">
            <span className="text-xl sm:text-2xl font-black text-[#17313A] tracking-tight">
              {dose.scheduled_time_local}
            </span>
            <span className="text-xs px-2.5 py-0.5 rounded-full font-medium bg-[#F7F6F1] text-[#4F6267] flex items-center gap-1">
              <Utensils className="w-3 h-3" />
              {formatMealLabel(dose.meal_context_snapshot)}
            </span>
          </div>

          {/* Cartridge Tag */}
          <span className="text-xs font-semibold px-2.5 py-1 rounded-md bg-[#F7F6F1] text-[#17313A] border border-[#E5E4E0] flex items-center gap-1">
            <Layers className="w-3.5 h-3.5 text-[#145A4A]" />
            Cartridge {dose.cartridge_number || '—'}
          </span>
        </div>

        {/* 2 & 3. Medicine Name, Strength & Prescribed Qty */}
        <div className="mt-3 flex items-start justify-between gap-4">
          <div>
            <h3 className="text-lg sm:text-xl font-bold text-[#17313A] leading-snug">
              {dose.medication_name}
            </h3>
            {dose.medication_strength && (
              <span className="inline-block mt-0.5 text-sm font-semibold text-[#4F6267]">
                {dose.medication_strength}
              </span>
            )}
          </div>

          <div className="text-right shrink-0">
            <span className="text-xs font-medium text-[#4F6267] block">Prescribed</span>
            <span className="text-base sm:text-lg font-black text-[#145A4A]">
              {dose.requested_pills} {dose.requested_pills === 1 ? 'tablet' : 'tablets'}
            </span>
          </div>
        </div>

        {/* 6. Current State Indicator */}
        <div className="mt-3">
          <div
            className={`flex items-center gap-2 px-3 py-2 rounded-xl border text-xs sm:text-sm ${statusConfig.bg} ${statusConfig.text} ${statusConfig.border}`}
          >
            <StatusIcon className="w-4 h-4 shrink-0" />
            <span className="font-semibold">{statusConfig.label}</span>
            {dose.confirmed_pills > 0 && dose.status !== 'confirmed_taken' && dose.status !== 'collected' && (
              <span className="ml-auto text-xs font-mono font-bold bg-white/70 px-2 py-0.5 rounded">
                Sensor 1: {dose.confirmed_pills}/{dose.requested_pills}
              </span>
            )}
          </div>

          {/* Fault details banner if any */}
          {dose.fault_reason && (
            <div className="mt-2 p-3 rounded-xl bg-red-50 border border-red-200 text-xs text-red-900 font-medium flex items-start justify-between gap-2">
              <div>
                <strong>Safety Fault:</strong> {dose.fault_reason}
              </div>
              {onCancelDispense && (
                <button
                  onClick={() => onCancelDispense(dose.id)}
                  className="px-2.5 py-1 rounded bg-red-800 text-white font-bold text-[11px] shrink-0 hover:bg-red-900 transition-colors"
                >
                  Reset
                </button>
              )}
            </div>
          )}
        </div>

        {/* 7. Primary Action Button */}
        <div className="mt-4 pt-1">
          {/* Scheduled State */}
          {dose.status === 'scheduled' && (
            <>
              {canDispenseNow ? (
                isSimulated ? (
                  <button
                    onClick={() => (onSimulateDispense ? onSimulateDispense(dose.id) : onDispense(dose.id))}
                    className="w-full min-h-[56px] rounded-xl bg-violet-700 hover:bg-violet-800 text-white font-bold text-base flex items-center justify-center gap-2 transition-all shadow-xs cursor-pointer active:scale-[0.99]"
                    title="Simulate rotary dispensing and optoelectronic drop pulse counting"
                  >
                    <Sparkles className="w-5 h-5 fill-violet-200 text-violet-700" />
                    <span>Simulate Dispensing (Demo)</span>
                  </button>
                ) : (
                  <button
                    onClick={() => onDispense(dose.id)}
                    className="w-full min-h-[56px] rounded-xl bg-[#145A4A] hover:bg-[#0E4236] text-white font-bold text-base flex items-center justify-center gap-2 transition-all shadow-xs cursor-pointer active:scale-[0.99]"
                    title="Sends DISPENSE command to physical ESP32"
                  >
                    <Play className="w-5 h-5 fill-white" />
                    <span>Dispense Scheduled Dose</span>
                  </button>
                )
              ) : (
                <div className="w-full py-3 px-4 rounded-xl bg-stone-100 border border-stone-200 text-[#4F6267] text-xs font-semibold flex items-center justify-between gap-2">
                  <div className="flex items-center gap-2">
                    <Clock className="w-4 h-4 text-stone-400" />
                    <span>Upcoming at {dose.scheduled_time_local}</span>
                  </div>
                  <span className="text-[11px] text-stone-500 font-normal">
                    Dispense unlocks in pre-dose window (-10m)
                  </span>
                </div>
              )}
            </>
          )}

          {/* In-progress Dispensing */}
          {(dose.status === 'dispensing' || dose.status === 'corrective_dispensing') && (
            <div className="space-y-2">
              <div className="w-full py-3 px-4 rounded-xl bg-blue-50 border border-blue-200 text-blue-900 text-xs sm:text-sm font-semibold flex items-center justify-between gap-2">
                <div className="flex items-center gap-2">
                  <RotateCcw className="w-4 h-4 animate-spin text-blue-700 shrink-0" />
                  <span>
                    {isSimulated
                      ? 'Simulating drop pulses & stock check...'
                      : 'Rotary Dispenser Active... Waiting for ESP32 Sensor 1 (30s)'}
                  </span>
                </div>
                {onCancelDispense && (
                  <button
                    onClick={() => onCancelDispense(dose.id)}
                    className="px-2.5 py-1 rounded-lg bg-blue-200 hover:bg-blue-300 text-blue-900 font-bold text-xs transition-colors cursor-pointer"
                  >
                    Cancel
                  </button>
                )}
              </div>
            </div>
          )}

          {/* Awaiting Collection / Escalated */}
          {(dose.status === 'awaiting_collection' ||
            dose.status === 'collection_reminder' ||
            dose.status === 'escalated') && (
            <div className="w-full py-3 px-4 rounded-xl bg-amber-50 border border-amber-200 text-amber-900 text-xs sm:text-sm font-semibold flex flex-col sm:flex-row sm:items-center justify-between gap-3">
              <div className="flex items-center gap-2">
                <Hand className="w-4 h-4 text-amber-700 shrink-0" />
                <span>Medicine ready in cup tray. Please pick up the cup to take your dose.</span>
              </div>
              {onPickup && (
                <button
                  onClick={() => onPickup(dose.id)}
                  className="px-3.5 py-2 rounded-xl bg-[#145A4A] hover:bg-[#0E4236] text-white font-bold text-xs flex items-center justify-center gap-1.5 transition-all shadow-xs cursor-pointer active:scale-95 self-start sm:self-auto"
                  title="Simulate Sensor 2 detecting cup removal from tray"
                >
                  <Hand className="w-3.5 h-3.5" />
                  <span>Cup Picked Up (Sensor 2)</span>
                </button>
              )}
            </div>
          )}

          {/* Collected from Tray */}
          {(dose.status === 'collected' || dose.status === 'confirmed_taken') && (
            <div className="w-full py-2.5 px-3.5 rounded-xl bg-[#EAF2EC] border border-[#c1dbca] text-[#145A4A] text-xs sm:text-sm font-semibold flex items-center gap-2">
              <CheckCircle2 className="w-4 h-4 text-[#145A4A] shrink-0" />
              <span>
                Collected from tray at{' '}
                {dose.collected_at
                  ? new Date(dose.collected_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
                  : 'scheduled time'}
              </span>
            </div>
          )}
        </div>

        {/* 8. Additional Details Disclosure */}
        <div className="mt-3 pt-2 border-t border-[#F7F6F1]">
          <button
            onClick={() => setExpanded(!expanded)}
            className="w-full py-1.5 flex items-center justify-between text-xs font-medium text-[#4F6267] hover:text-[#17313A] transition-colors cursor-pointer"
          >
            <span className="flex items-center gap-1.5">
              <Info className="w-3.5 h-3.5" />
              Sensor audit & telemetry details
            </span>
            {expanded ? <ChevronUp className="w-4 h-4" /> : <ChevronDown className="w-4 h-4" />}
          </button>

          {expanded && (
            <div className="mt-2 p-3 rounded-xl bg-[#F7F6F1] text-xs text-[#17313A] space-y-1.5 font-mono">
              <div className="flex justify-between">
                <span className="text-[#4F6267]">Dose ID:</span>
                <span className="font-semibold">{dose.id.slice(0, 8)}...</span>
              </div>
              {dose.command_id && (
                <div className="flex justify-between">
                  <span className="text-[#4F6267]">Command ID:</span>
                  <span className="font-semibold">{dose.command_id.slice(0, 8)}...</span>
                </div>
              )}
              <div className="flex justify-between">
                <span className="text-[#4F6267]">Sensor 1 Drops:</span>
                <span className="font-semibold text-emerald-800">{dose.confirmed_pills}/{dose.requested_pills} pills</span>
              </div>
              <div className="flex justify-between">
                <span className="text-[#4F6267]">Correction Attempts:</span>
                <span>{dose.correction_attempts_used}</span>
              </div>
              {dose.dispensed_at && (
                <div className="flex justify-between">
                  <span className="text-[#4F6267]">Dispensed At:</span>
                  <span>{new Date(dose.dispensed_at).toLocaleTimeString()}</span>
                </div>
              )}
              {dose.collected_at && (
                <div className="flex justify-between">
                  <span className="text-[#4F6267]">Collected At:</span>
                  <span>{new Date(dose.collected_at).toLocaleTimeString()}</span>
                </div>
              )}
              {dose.manual_confirmed_at && (
                <div className="flex justify-between">
                  <span className="text-[#4F6267]">Confirmed Taken At:</span>
                  <span>{new Date(dose.manual_confirmed_at).toLocaleTimeString()}</span>
                </div>
              )}
              {dose.operations && dose.operations.length > 0 && (
                <div className="pt-2 border-t border-stone-200">
                  <span className="text-[#4F6267] block mb-1">Attempt Telemetry Log:</span>
                  {dose.operations.map((op) => (
                    <div key={op.id} className="text-[11px] bg-white p-1.5 rounded mb-1 border border-stone-200">
                      Attempt #{op.attempt_number}: Target {op.target_pills_this_attempt} pill(s) → Sensor 1 Detected {op.sensor1_detected_count} ({op.status})
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  );
};
