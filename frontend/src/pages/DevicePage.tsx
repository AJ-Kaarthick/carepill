import React, { useState } from 'react';
import {
  Cpu,
  Wifi,
  WifiOff,
  Battery,
  Volume2,
  VolumeX,
  Square,
  Sliders,
  CheckCircle2,
  AlertTriangle,
  Play,
  RotateCcw,
  Sparkles,
  Layers,
  Terminal,
  ShieldAlert,
  HelpCircle
} from 'lucide-react';
import { SimulatorState, Cartridge, DeviceConnectivity } from '../types';
import { sound } from '../services/audio';
import { api } from '../services/api';

interface DevicePageProps {
  simulatorState: SimulatorState | null;
  connectivity?: DeviceConnectivity | null;
  cartridges: Cartridge[];
  onOpenSimulator: () => void;
  onToggleOperatingMode?: () => void;
}

export const DevicePage: React.FC<DevicePageProps> = ({
  simulatorState,
  connectivity,
  cartridges,
  onOpenSimulator,
  onToggleOperatingMode
}) => {
  const isSimulated = connectivity?.is_simulated ?? true;
  const status = connectivity?.status || (isSimulated ? 'demo_simulated' : 'physical_online');
  const isOnline = isSimulated ? true : status === 'physical_online';

  // Sound States
  const [isMuted, setIsMuted] = useState(() => sound.getMuted());
  const [volume, setVolumeState] = useState(() => Math.round(sound.getVolume() * 100));
  const [playingToneName, setPlayingToneName] = useState<string | null>(null);

  const handleToggleMute = () => {
    const nextMute = !isMuted;
    setIsMuted(nextMute);
    sound.setMuted(nextMute);
  };

  const handleVolumeChange = (newVal: number) => {
    setVolumeState(newVal);
    sound.setVolume(newVal / 100);
    if (isMuted && newVal > 0) {
      setIsMuted(false);
      sound.setMuted(false);
    }
  };

  const handlePlaySound = (name: string, fn: () => void) => {
    setPlayingToneName(name);
    fn();
    setTimeout(() => {
      setPlayingToneName(null);
    }, 1500);
  };

  const handleStopAllSounds = () => {
    sound.stopAllSounds();
    setPlayingToneName(null);
  };

  const indicatorTable = [
    {
      name: 'Pre-Dose Reminder (-10m / -5m)',
      event: 'Pre-Dose Reminder (-10m / -5m)',
      led: 'Amber Soft Pulse',
      buzzer: 'Gentle 1kHz double-chirp',
      previewSound: () => sound.playPreDoseReminder()
    },
    {
      name: 'Dispensing Underway',
      event: 'Dispensing Underway',
      led: 'Blue Running Sweep',
      buzzer: 'Distinctive motor tick cadence',
      previewSound: () => sound.playDispensingTick()
    },
    {
      name: 'Awaiting Collection (Cup in Tray)',
      event: 'Awaiting Collection (Cup in Tray)',
      led: 'Amber Slow Breathe',
      buzzer: 'Silent until 5m timer',
      previewSound: () => {}
    },
    {
      name: '5-Minute Collection Reminder',
      event: '5-Minute Collection Reminder',
      led: 'Amber Rapid Strobe',
      buzzer: 'Repeating 1.5kHz 3-beep alert',
      previewSound: () => sound.playCollectionReminder()
    },
    {
      name: 'Successful Pickup (Sensor 2 Confirmed)',
      event: 'Successful Pickup (Sensor 2 Confirmed)',
      led: 'Green 2s Pulse',
      buzzer: 'Ascending 2-tone chime',
      previewSound: () => sound.playPickupChime()
    },
    {
      name: '10-Minute Caregiver Escalation',
      event: '10-Minute Caregiver Escalation',
      led: 'Red Rapid Strobe',
      buzzer: 'Urgent alternating hi-lo siren',
      previewSound: () => sound.playUrgentEscalation()
    },
    {
      name: 'Dispensing / Sensor Fault',
      event: 'Dispensing / Sensor Fault',
      led: 'Solid Red Warning',
      buzzer: 'Continuous 440Hz warning tone',
      previewSound: () => sound.playFaultAlert()
    }
  ];

  return (
    <div className="space-y-6 pb-20">
      {/* Header */}
      <div className="bg-white rounded-3xl p-5 sm:p-6 border border-[#E5E4E0] shadow-2xs">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
          <div>
            <span className="text-xs font-bold uppercase tracking-wider text-[#145A4A] flex items-center gap-1.5">
              <Cpu className="w-3.5 h-3.5" />
              Microcontroller Hardware Profile & Setup
            </span>
            <h1 className="text-2xl font-black text-[#17313A] mt-1 tracking-tight">
              ESP32 Smart Dispenser #01
            </h1>
            <p className="text-sm text-[#4F6267] mt-1">
              Firmware v1.0.0 • Rotary Actuator • Optoelectronic Verification • LittleFS Schedules
            </p>
          </div>

          <div className="flex items-center gap-2">
            <button
              onClick={onToggleOperatingMode}
              className={`text-xs font-bold px-3.5 py-2 rounded-xl border transition-colors cursor-pointer ${
                isSimulated
                  ? 'bg-violet-50 text-violet-900 border-violet-200 hover:bg-violet-100'
                  : status === 'physical_online'
                  ? 'bg-emerald-50 text-emerald-900 border-emerald-200 hover:bg-emerald-100'
                  : status === 'physical_stale'
                  ? 'bg-amber-50 text-amber-900 border-amber-200 hover:bg-amber-100'
                  : 'bg-rose-50 text-rose-900 border-rose-200 hover:bg-rose-100'
              }`}
              title="Click to toggle between Demo (Simulated) and Physical ESP32 mode"
            >
              {isSimulated
                ? 'Mode: Demo (Simulated)'
                : status === 'physical_online'
                ? 'Mode: ESP32 Online'
                : status === 'physical_stale'
                ? 'Mode: ESP32 Stale'
                : 'Mode: Hardware Fault'}
            </button>
            <button
              onClick={onOpenSimulator}
              className="px-4 py-2 rounded-xl bg-[#145A4A] hover:bg-[#0E4236] text-white text-xs font-bold flex items-center gap-1.5 shadow-xs transition-colors cursor-pointer"
            >
              <Sparkles className="w-3.5 h-3.5" />
              <span>Full Simulator Drawer</span>
            </button>
          </div>
        </div>
      </div>

      {/* Hardware Telemetry Card */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
        <div className="p-4 rounded-3xl bg-white border border-[#E5E4E0]">
          <span className="text-xs font-bold text-[#4F6267] block">Operating Mode & Link</span>
          <div className="mt-2 flex items-center gap-2">
            {isSimulated ? (
              <span className="flex items-center gap-1.5 text-base font-bold text-violet-800">
                <Wifi className="w-5 h-5 text-violet-600" />
                Virtual Simulator Mode
              </span>
            ) : status === 'physical_online' ? (
              <span className="flex items-center gap-1.5 text-base font-bold text-emerald-800">
                <Wifi className="w-5 h-5 text-emerald-600" />
                ESP32 Online (802.11 b/g/n)
              </span>
            ) : (
              <span className="flex items-center gap-1.5 text-base font-bold text-red-700">
                <WifiOff className="w-5 h-5 text-red-600" />
                ESP32 Disconnected
              </span>
            )}
          </div>
          <p className="text-xs text-[#4F6267] mt-1">
            {isSimulated
              ? 'Local mock telemetry with instant state feedback for validation.'
              : 'Physical LittleFS schedule guarantees autonomous offline alarms.'}
          </p>
        </div>

        <div className="p-4 rounded-3xl bg-white border border-[#E5E4E0]">
          <span className="text-xs font-bold text-[#4F6267] block">Sensor 1 — Pill Drop Counter</span>
          <span className="text-base font-bold text-[#17313A] mt-2 block">
            Optical Breakbeam (GPIO 18)
          </span>
          <p className="text-xs text-[#4F6267] mt-1">
            Interrupt-driven pulse counting with 25ms debounce filter.
          </p>
        </div>

        <div className="p-4 rounded-3xl bg-white border border-[#E5E4E0]">
          <span className="text-xs font-bold text-[#4F6267] block">Sensor 2 — Pickup Area</span>
          <span className="text-base font-bold text-[#17313A] mt-2 block">
            Cup Detector (GPIO 19)
          </span>
          <p className="text-xs text-[#4F6267] mt-1">
            Spring microswitch / optical proximity debounced at 500ms.
          </p>
        </div>
      </div>

      {/* Audio & Buzzer Settings Card */}
      <div className="bg-white rounded-3xl p-5 sm:p-6 border border-[#E5E4E0] shadow-2xs space-y-4">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 border-b border-stone-100 pb-3">
          <div>
            <div className="flex items-center gap-2">
              <Volume2 className="w-4 h-4 text-[#145A4A]" />
              <h2 className="text-lg font-black text-[#17313A]">
                Audio & Acoustic Feedback Controls
              </h2>
            </div>
            <p className="text-xs text-[#4F6267] mt-0.5">
              Control browser-synthesized buzzer volume, master mute, and live firmware tone previews.
            </p>
          </div>

          <div className="flex items-center gap-2">
            <button
              onClick={handleToggleMute}
              className={`px-3.5 py-2 rounded-xl text-xs font-bold flex items-center gap-1.5 transition-colors cursor-pointer ${
                isMuted
                  ? 'bg-amber-100 text-amber-900 border border-amber-300'
                  : 'bg-stone-100 hover:bg-stone-200 text-[#17313A]'
              }`}
            >
              {isMuted ? <VolumeX className="w-4 h-4" /> : <Volume2 className="w-4 h-4" />}
              <span>{isMuted ? 'Unmute Audio' : 'Mute All Audio'}</span>
            </button>

            <button
              onClick={handleStopAllSounds}
              className="px-3.5 py-2 rounded-xl bg-red-50 hover:bg-red-100 text-red-700 font-bold text-xs flex items-center gap-1.5 border border-red-200 transition-colors cursor-pointer"
              title="Stop any ongoing buzzer tones immediately"
            >
              <Square className="w-3.5 h-3.5 fill-red-700" />
              <span>Stop Tone</span>
            </button>
          </div>
        </div>

        <div className="flex flex-col sm:flex-row sm:items-center gap-4 bg-[#F7F6F1] p-4 rounded-2xl border border-stone-200">
          <div className="flex items-center gap-2 text-xs font-bold text-[#17313A] shrink-0">
            <Sliders className="w-4 h-4 text-[#145A4A]" />
            <span>Master Volume:</span>
          </div>

          <div className="flex items-center gap-3 flex-1">
            <input
              type="range"
              min="0"
              max="100"
              value={volume}
              onChange={(e) => handleVolumeChange(parseInt(e.target.value) || 0)}
              className="w-full accent-[#145A4A] cursor-pointer"
            />
            <span className="text-xs font-bold text-[#17313A] w-12 text-right">
              {volume}%
            </span>
          </div>

          {isMuted && (
            <span className="text-xs font-bold text-amber-800 bg-amber-50 px-2.5 py-1 rounded-lg border border-amber-200 shrink-0">
              Audio Muted
            </span>
          )}
        </div>
      </div>

      {/* Configurable Event-to-Output Table with Acoustic Preview */}
      <div className="space-y-3">
        <div className="flex items-center justify-between px-1">
          <h2 className="text-xs font-black uppercase tracking-wider text-[#4F6267] flex items-center gap-1.5">
            <Volume2 className="w-4 h-4 text-[#145A4A]" />
            Firmware Event-to-Output Physical Mapping Table
          </h2>
          <span className="text-xs text-[#4F6267]">Click test tone to hear simulated buzzer</span>
        </div>

        <div className="bg-white rounded-3xl border border-[#E5E4E0] shadow-2xs overflow-hidden">
          <div className="divide-y divide-stone-100 text-xs">
            {indicatorTable.map((item, idx) => (
              <div
                key={idx}
                className="p-4 flex flex-col sm:flex-row sm:items-center justify-between gap-3 hover:bg-stone-50/50 transition-colors"
              >
                <div className="space-y-1">
                  <span className="font-bold text-sm text-[#17313A] block">{item.event}</span>
                  <div className="flex flex-wrap gap-2 text-[11px]">
                    <span className="px-2 py-0.5 rounded bg-[#F7F6F1] text-[#17313A] font-semibold border border-[#E5E4E0]">
                      LED: {item.led}
                    </span>
                    <span className="px-2 py-0.5 rounded bg-[#F7F6F1] text-[#4F6267] border border-[#E5E4E0]">
                      Sound: {item.buzzer}
                    </span>
                  </div>
                </div>

                <div className="flex items-center gap-2">
                  <button
                    onClick={() => handlePlaySound(item.name, item.previewSound)}
                    disabled={isMuted || !item.previewSound}
                    className="px-3.5 py-2 rounded-xl bg-stone-100 hover:bg-[#145A4A] hover:text-white text-[#17313A] font-bold text-xs flex items-center gap-1.5 transition-colors cursor-pointer disabled:opacity-50"
                  >
                    <Volume2 className="w-4 h-4" />
                    <span>{playingToneName === item.name ? 'Playing...' : 'Test Tone'}</span>
                  </button>
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* LAN Setup, Firmware Flash & LittleFS Guide */}
      <div className="bg-white rounded-3xl p-5 sm:p-6 border border-[#E5E4E0] shadow-2xs space-y-4">
        <div className="flex items-center gap-2">
          <Terminal className="w-4 h-4 text-[#145A4A]" />
          <h2 className="text-lg font-black text-[#17313A]">
            Physical ESP32 Deployment & LAN Configuration
          </h2>
        </div>

        <p className="text-xs text-[#4F6267] leading-relaxed">
          For physical hardware integration, your laptop and ESP32 must share the same local Wi-Fi network. The backend server must bind to all local interfaces (<code>0.0.0.0</code>) rather than localhost alone.
        </p>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-4 text-xs">
          <div className="p-4 bg-[#F7F6F1] rounded-2xl border border-stone-200 space-y-2">
            <span className="font-bold text-[#17313A] block uppercase tracking-wider text-[11px]">
              1. Host Server Binding
            </span>
            <p className="text-[#4F6267]">
              Start the FastAPI backend listening on <code>0.0.0.0:8000</code> so external devices can reach the REST APIs:
            </p>
            <div className="bg-stone-900 text-emerald-400 p-2.5 rounded-xl font-mono text-[11px] overflow-x-auto">
              ./venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 8000
            </div>
            <p className="text-[11px] text-[#4F6267]">
              Find your laptop's LAN IP address using <code>ip addr show</code> or <code>hostname -I</code> (e.g., <code>192.168.1.150</code>).
            </p>
          </div>

          <div className="p-4 bg-[#F7F6F1] rounded-2xl border border-stone-200 space-y-2">
            <span className="font-bold text-[#17313A] block uppercase tracking-wider text-[11px]">
              2. ESP32 Firmware Configuration
            </span>
            <p className="text-[#4F6267]">
              Open <code>firmware/esp32_pillbox.ino</code> in Arduino IDE and update credentials:
            </p>
            <div className="bg-stone-900 text-stone-200 p-2.5 rounded-xl font-mono text-[11px] space-y-0.5">
              <div><span className="text-purple-400">#define</span> WIFI_SSID <span className="text-amber-300">"YourHomeWiFi"</span></div>
              <div><span className="text-purple-400">#define</span> WIFI_PASS <span className="text-amber-300">"YourPassword"</span></div>
              <div><span className="text-purple-400">#define</span> API_HOST <span className="text-amber-300">"http://192.168.1.150:8000"</span></div>
            </div>
          </div>
        </div>

        {/* LittleFS & Fail-Safe Architecture Note */}
        <div className="p-4 bg-[#EAF2EC] rounded-2xl border border-[#c1dbca] text-xs text-[#145A4A] space-y-1">
          <span className="font-bold block">LittleFS Offline Fail-Safe Architecture:</span>
          <p className="leading-relaxed">
            The ESP32 firmware synchronizes daily schedules via <code>GET /api/device/schedule-sync</code> and persists them directly into on-board flash memory using LittleFS. Even if the home Wi-Fi network goes down or your laptop sleeps, the dispenser's internal Real-Time Clock (RTC) triggers buzzer reminders and optical motor rotations on schedule.
          </p>
        </div>
      </div>
    </div>
  );
};
