import React, { useState } from 'react';
import {
  X,
  Play,
  RotateCcw,
  CheckCircle2,
  AlertTriangle,
  Clock,
  FastForward,
  Wifi,
  WifiOff,
  Volume2,
  Activity,
  Layers,
  ShieldAlert,
  HelpCircle
} from 'lucide-react';
import { SimulatorState } from '../types';
import { api } from '../services/api';
import { sound } from '../services/audio';

interface HardwareSimulatorProps {
  isOpen: boolean;
  onClose: () => void;
  simulatorState: SimulatorState | null;
  onRefresh: () => void;
}

export const HardwareSimulator: React.FC<HardwareSimulatorProps> = ({
  isOpen,
  onClose,
  simulatorState,
  onRefresh
}) => {
  const [loading, setLoading] = useState(false);
  const [feedbackMsg, setFeedbackMsg] = useState<string | null>(null);

  if (!isOpen) return null;

  const runScenario = async (scenario: string, extra?: any) => {
    setLoading(true);
    setFeedbackMsg(null);
    try {
      // Play acoustic cue based on scenario
      if (scenario === 'dispense_perfect_2' || scenario === 'dispense_under_1' || scenario === 'dispense_corrective_step') {
        sound.playDispensingTick();
      } else if (scenario === 'pickup_detected') {
        sound.playPickupChime();
      } else if (scenario === 'fast_forward_5m') {
        sound.playCollectionReminder();
      } else if (scenario === 'fast_forward_10m') {
        sound.playUrgentEscalation();
      } else if (scenario === 'fast_forward_pre_dose_10m' || scenario === 'fast_forward_pre_dose_5m') {
        sound.playPreDoseReminder();
      } else if (scenario === 'dispense_over_fault' || scenario === 'sensor_fault') {
        sound.playFaultAlert();
      }

      const res = await api.triggerSimulationAction(scenario, extra);
      setFeedbackMsg(res.message || 'Action executed successfully.');
      onRefresh();
    } catch (err: any) {
      setFeedbackMsg(`Error: ${err.message}`);
    } finally {
      setLoading(false);
    }
  };

  const led = simulatorState?.current_led_pattern || 'OFF';
  const buzzer = simulatorState?.current_buzzer_pattern || 'SILENT';

  const getLedGlow = (pattern: string) => {
    if (pattern.includes('BLUE')) return 'bg-blue-500 shadow-[0_0_15px_rgba(59,130,246,0.8)]';
    if (pattern.includes('AMBER')) return 'bg-amber-500 shadow-[0_0_15px_rgba(245,158,11,0.8)]';
    if (pattern.includes('RED')) return 'bg-red-600 shadow-[0_0_20px_rgba(220,38,38,0.9)] animate-ping';
    if (pattern.includes('GREEN')) return 'bg-emerald-500 shadow-[0_0_15px_rgba(16,185,129,0.8)]';
    return 'bg-stone-300';
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-3 sm:p-4 bg-black/60 backdrop-blur-xs animate-in fade-in duration-150">
      <div className="bg-white rounded-3xl w-full max-w-2xl max-h-[92vh] flex flex-col shadow-2xl border border-stone-200 overflow-hidden">
        {/* Header */}
        <div className="px-5 py-4 border-b border-stone-200 bg-[#F7F6F1] flex items-center justify-between">
          <div className="flex items-center gap-2.5">
            <div className="w-8 h-8 rounded-lg bg-[#145A4A] flex items-center justify-center text-white">
              <Activity className="w-5 h-5" />
            </div>
            <div>
              <h2 className="text-lg font-bold text-[#17313A]">ESP32 Hardware & Sensor Simulator</h2>
              <p className="text-xs text-[#4F6267]">Two-Sensor Logic, Timed Escalations & Offline Outages</p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="w-9 h-9 rounded-full bg-white hover:bg-stone-200 flex items-center justify-center text-[#4F6267] transition-colors"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Live Hardware Telemetry Dock */}
        <div className="bg-[#17313A] text-white px-5 py-3 grid grid-cols-2 sm:grid-cols-5 gap-3 text-xs">
          <div>
            <span className="text-stone-400 block text-[11px]">Hardware LED:</span>
            <div className="flex items-center gap-2 mt-1">
              <span className={`w-3.5 h-3.5 rounded-full inline-block ${getLedGlow(led)}`} />
              <span className="font-mono font-bold truncate">{led}</span>
            </div>
          </div>

          <div>
            <span className="text-stone-400 block text-[11px]">Hardware Buzzer:</span>
            <div className="flex items-center gap-1.5 mt-1">
              <Volume2 className="w-3.5 h-3.5 text-stone-300" />
              <span className="font-mono font-bold truncate">{buzzer}</span>
            </div>
          </div>

          <div>
            <span className="text-stone-400 block text-[11px]">Carousel Size:</span>
            <span className="font-mono font-bold mt-1 block text-emerald-400">
              {simulatorState?.cartridge_count || 4} Slots
            </span>
          </div>

          <div>
            <span className="text-stone-400 block text-[11px]">Virtual Test Clock:</span>
            <span className="font-mono font-bold mt-1 block">
              {simulatorState?.virtual_clock_now
                ? new Date(simulatorState.virtual_clock_now).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' })
                : '12:00:00'}
            </span>
          </div>

          <div>
            <span className="text-stone-400 block text-[11px]">Wi-Fi Link:</span>
            <span className="font-mono font-bold mt-1 flex items-center gap-1">
              {simulatorState?.device_online ? (
                <span className="text-emerald-400 flex items-center gap-1"><Wifi className="w-3.5 h-3.5" /> Online</span>
              ) : (
                <span className="text-red-400 flex items-center gap-1"><WifiOff className="w-3.5 h-3.5" /> Offline</span>
              )}
            </span>
          </div>
        </div>

        {/* Feedback message banner */}
        {feedbackMsg && (
          <div className="px-5 py-2.5 bg-[#EAF2EC] border-b border-[#c1dbca] text-xs font-semibold text-[#145A4A] flex items-center gap-2">
            <CheckCircle2 className="w-4 h-4 shrink-0 text-[#145A4A]" />
            <span>{feedbackMsg}</span>
          </div>
        )}

        {/* Action Grid */}
        <div className="p-5 overflow-y-auto space-y-5 text-sm">
          {/* Section 1: Sensor 1 Dispensing Scenarios */}
          <div>
            <h3 className="text-xs font-bold text-[#4F6267] uppercase tracking-wider mb-2 flex items-center gap-1.5">
              <Layers className="w-4 h-4 text-[#145A4A]" />
              Sensor 1 — Dispensing & Corrective Loop Scenarios
            </h3>

            <div className="grid grid-cols-1 sm:grid-cols-2 gap-2.5">
              <button
                disabled={loading}
                onClick={() => runScenario('dispense_perfect_2')}
                className="p-3 text-left rounded-xl border border-stone-200 hover:border-[#145A4A] hover:bg-[#EAF2EC]/40 transition-all cursor-pointer group"
              >
                <div className="font-bold text-[#17313A] group-hover:text-[#145A4A] flex items-center gap-1.5">
                  <Play className="w-4 h-4 text-emerald-600 fill-emerald-600" />
                  1. Perfect 2-Pill Dispense
                </div>
                <p className="text-xs text-[#4F6267] mt-1">
                  Sensor 1 confirms 2 tablets on 1st rotation. Stock decrements by 2.
                </p>
              </button>

              <button
                disabled={loading}
                onClick={() => runScenario('dispense_under_1')}
                className="p-3 text-left rounded-xl border border-stone-200 hover:border-[#9A6700] hover:bg-amber-50/50 transition-all cursor-pointer group"
              >
                <div className="font-bold text-[#17313A] group-hover:text-[#9A6700] flex items-center gap-1.5">
                  <RotateCcw className="w-4 h-4 text-[#9A6700]" />
                  2. Under-dispense (1 of 2 pills)
                </div>
                <p className="text-xs text-[#4F6267] mt-1">
                  Detects 1 missing tablet. System triggers bounded corrective loop.
                </p>
              </button>

              <button
                disabled={loading}
                onClick={() => runScenario('dispense_corrective_step')}
                className="p-3 text-left rounded-xl border border-stone-200 hover:border-[#145A4A] hover:bg-[#EAF2EC]/40 transition-all cursor-pointer group"
              >
                <div className="font-bold text-[#17313A] group-hover:text-[#145A4A] flex items-center gap-1.5">
                  <CheckCircle2 className="w-4 h-4 text-[#145A4A]" />
                  3. Deliver Corrective Tablet (1/1)
                </div>
                <p className="text-xs text-[#4F6267] mt-1">
                  Sensor 1 confirms missing pill. Total count reaches 2. Ready for pickup!
                </p>
              </button>

              <button
                disabled={loading}
                onClick={() => runScenario('dispense_over_fault')}
                className="p-3 text-left rounded-xl border border-stone-200 hover:border-red-400 hover:bg-red-50/50 transition-all cursor-pointer group"
              >
                <div className="font-bold text-[#17313A] group-hover:text-red-700 flex items-center gap-1.5">
                  <AlertTriangle className="w-4 h-4 text-red-600" />
                  4. Over-Dispense Safety Halt
                </div>
                <p className="text-xs text-[#4F6267] mt-1">
                  Sensor 1 detects &gt; prescribed pills. Stops motor safely & alerts caregiver.
                </p>
              </button>
            </div>
          </div>

          {/* Section 2: Sensor 2 & Timed Reminder/Escalation */}
          <div>
            <h3 className="text-xs font-bold text-[#4F6267] uppercase tracking-wider mb-2 flex items-center gap-1.5">
              <Clock className="w-4 h-4 text-[#145A4A]" />
              Sensor 2 — Pickup & Deterministic Fast-Forward Timers
            </h3>

            <div className="grid grid-cols-1 sm:grid-cols-2 gap-2.5">
              <button
                disabled={loading}
                onClick={() => runScenario('pickup_detected')}
                className="p-3 text-left rounded-xl border border-emerald-300 bg-emerald-50/40 hover:bg-emerald-100/60 transition-all cursor-pointer group"
              >
                <div className="font-bold text-emerald-900 flex items-center gap-1.5">
                  <CheckCircle2 className="w-4 h-4 text-emerald-700 fill-emerald-100" />
                  Sensor 2: Patient Picked Up Pills
                </div>
                <p className="text-xs text-emerald-800 mt-1">
                  Confirms pickup, plays chime, stops pending reminders & escalations.
                </p>
              </button>

              <button
                disabled={loading}
                onClick={() => runScenario('sensor_fault')}
                className="p-3 text-left rounded-xl border border-stone-200 hover:border-red-400 hover:bg-red-50/50 transition-all cursor-pointer group"
              >
                <div className="font-bold text-red-900 flex items-center gap-1.5">
                  <AlertTriangle className="w-4 h-4 text-red-600" />
                  Chute Jam / Sensor Uncertainty
                </div>
                <p className="text-xs text-[#4F6267] mt-1">
                  Simulates beam blocked &gt; 3s. Safe fault state entered.
                </p>
              </button>

              <button
                disabled={loading}
                onClick={() => runScenario('fast_forward_pre_dose_10m')}
                className="p-3 text-left rounded-xl border border-blue-200 bg-blue-50/40 hover:bg-blue-100/60 transition-all cursor-pointer group"
              >
                <div className="font-bold text-blue-900 flex items-center gap-1.5">
                  <Clock className="w-4 h-4 text-blue-700" />
                  Pre-Dose -10 Min (Soft Chirp)
                </div>
                <p className="text-xs text-blue-800 mt-1">
                  10m pre-dose reminder window. Plays gentle double-chirp and amber soft pulse.
                </p>
              </button>

              <button
                disabled={loading}
                onClick={() => runScenario('fast_forward_pre_dose_5m')}
                className="p-3 text-left rounded-xl border border-blue-200 bg-blue-50/40 hover:bg-blue-100/60 transition-all cursor-pointer group"
              >
                <div className="font-bold text-blue-900 flex items-center gap-1.5">
                  <Clock className="w-4 h-4 text-blue-700" />
                  Pre-Dose -5 Min (Soft Chirp)
                </div>
                <p className="text-xs text-blue-800 mt-1">
                  5m pre-dose prompt before physical rotary dispensing starts.
                </p>
              </button>

              <button
                disabled={loading}
                onClick={() => runScenario('fast_forward_5m')}
                className="p-3 text-left rounded-xl border border-amber-300 bg-amber-50/40 hover:bg-amber-100/60 transition-all cursor-pointer group"
              >
                <div className="font-bold text-amber-900 flex items-center gap-1.5">
                  <FastForward className="w-4 h-4 text-amber-700" />
                  Post-Dispense +5 Min (Reminder)
                </div>
                <p className="text-xs text-amber-800 mt-1">
                  Advances test clock by 5 min. Triggers repeating reminder sound & LED.
                </p>
              </button>

              <button
                disabled={loading}
                onClick={() => runScenario('fast_forward_10m')}
                className="p-3 text-left rounded-xl border border-red-300 bg-red-50/40 hover:bg-red-100/60 transition-all cursor-pointer group"
              >
                <div className="font-bold text-red-900 flex items-center gap-1.5">
                  <ShieldAlert className="w-4 h-4 text-red-700" />
                  Post-Dispense +10 Min (Escalate)
                </div>
                <p className="text-xs text-red-800 mt-1">
                  Advances clock by 10 min uncollected. Sends Caregiver Escalation alert!
                </p>
              </button>

              <button
                disabled={loading}
                onClick={() => runScenario('test_notification')}
                className="p-3 text-left rounded-xl border border-purple-200 bg-purple-50/40 hover:bg-purple-100/60 transition-all cursor-pointer group sm:col-span-2"
              >
                <div className="font-bold text-purple-900 flex items-center gap-1.5">
                  <ShieldAlert className="w-4 h-4 text-purple-700" />
                  Test Caregiver Alert Dispatch
                </div>
                <p className="text-xs text-purple-800 mt-1">
                  Dispatches minimal test alert to caregiver: "CarePill alert: A scheduled medication has not been collected."
                </p>
              </button>
            </div>
          </div>

          {/* Section 3: Network Resilience & Clock Control */}
          <div className="pt-2 border-t border-stone-200 flex flex-wrap items-center justify-between gap-2">
            <button
              disabled={loading}
              onClick={() => runScenario('toggle_offline')}
              className="px-3.5 py-2 rounded-xl border border-stone-300 text-xs font-bold text-[#17313A] hover:bg-stone-100 flex items-center gap-1.5"
            >
              {simulatorState?.device_online ? <WifiOff className="w-4 h-4 text-red-600" /> : <Wifi className="w-4 h-4 text-emerald-600" />}
              {simulatorState?.device_online ? 'Simulate Wi-Fi Outage (Offline)' : 'Reconnect Wi-Fi & Reconcile'}
            </button>

            <button
              disabled={loading}
              onClick={() => runScenario('reset')}
              className="px-3.5 py-2 rounded-xl border border-stone-300 text-xs font-bold text-[#4F6267] hover:text-[#17313A] hover:bg-stone-100 flex items-center gap-1.5"
            >
              <RotateCcw className="w-4 h-4" />
              Reset Virtual Clock
            </button>
          </div>
        </div>
      </div>
    </div>
  );
};
