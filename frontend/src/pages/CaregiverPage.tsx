import React, { useState, useEffect } from 'react';
import {
  Shield,
  CheckCircle2,
  AlertTriangle,
  Bell,
  Clock,
  Phone,
  Check,
  Radio,
  Send,
  MessageSquare,
  Smartphone,
  Globe,
  Settings,
  HelpCircle,
  User
} from 'lucide-react';
import { CaregiverAlert, DoseOccurrence, Cartridge, CaregiverSettings } from '../types';
import { PhoneInput } from '../components/PhoneInput';
import { api } from '../services/api';

interface CaregiverPageProps {
  alerts: CaregiverAlert[];
  doses: DoseOccurrence[];
  cartridges: Cartridge[];
  onRefresh: () => void;
}

export const CaregiverPage: React.FC<CaregiverPageProps> = ({
  alerts,
  doses,
  cartridges,
  onRefresh
}) => {
  const [ackingId, setAckingId] = useState<string | null>(null);

  // Caregiver notification settings state
  const [settings, setSettings] = useState<CaregiverSettings>({
    id: '',
    name: 'Marcus Vance',
    role: 'caregiver',
    phone: '+91 98765 43210',
    whatsapp_phone: '+91 98765 43210',
    notification_channel: 'simulated',
    sms_consent: false,
    whatsapp_consent: false
  });
  const [nameError, setNameError] = useState<string | null>(null);
  const [loadingSettings, setLoadingSettings] = useState(false);
  const [savingSettings, setSavingSettings] = useState(false);
  const [saveSuccess, setSaveSuccess] = useState(false);

  // Test notification state
  const [testingNotification, setTestingNotification] = useState(false);
  const [testResult, setTestResult] = useState<{
    status: string;
    delivery_status: string;
    message?: string;
    provider_response?: string;
    channel?: string;
    recipient?: string;
  } | null>(null);

  useEffect(() => {
    loadSettings();
  }, []);

  const loadSettings = async () => {
    try {
      setLoadingSettings(true);
      const data = await api.getCaregiverSettings();
      setSettings(data);
    } catch (err) {
      console.error('Failed to load caregiver settings:', err);
    } finally {
      setLoadingSettings(false);
    }
  };

  const handleNameChange = (newName: string) => {
    setSettings((prev) => ({ ...prev, name: newName }));
    if (/\d/.test(newName)) {
      setNameError('Caregiver name cannot contain numbers (letters, spaces, and hyphens only).');
    } else {
      setNameError(null);
    }
  };

  const handleSaveSettings = async (e: React.FormEvent) => {
    e.preventDefault();
    if (/\d/.test(settings.name || '')) {
      setNameError('Caregiver name cannot contain numbers (letters, spaces, and hyphens only).');
      return;
    }
    setSavingSettings(true);
    setSaveSuccess(false);
    try {
      const updated = await api.updateCaregiverSettings(settings);
      setSettings(updated);
      setSaveSuccess(true);
      setTimeout(() => setSaveSuccess(false), 3000);
      onRefresh();
    } catch (err: any) {
      alert(`Failed to save settings: ${err.message}`);
    } finally {
      setSavingSettings(false);
    }
  };

  const handleTestNotification = async () => {
    setTestingNotification(true);
    setTestResult(null);
    try {
      const res = await api.testNotification({
        channel: settings.notification_channel,
        custom_message: `CarePill test alert: Verification check from caregiver portal at ${new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}.`
      });
      setTestResult(res);
      onRefresh();
    } catch (err: any) {
      setTestResult({
        status: 'error',
        delivery_status: 'failed',
        provider_response: err.message || 'Dispatch request failed'
      });
    } finally {
      setTestingNotification(false);
    }
  };

  const handleAcknowledge = async (alertId: string) => {
    setAckingId(alertId);
    try {
      await api.acknowledgeAlert(alertId, 'Marcus Vance (Primary Caregiver)');
      onRefresh();
    } catch (err: any) {
      alert(err.message);
    } finally {
      setAckingId(null);
    }
  };

  const unacknowledgedAlerts = alerts.filter((a) => !a.acknowledged);
  const uncollectedDoses = doses.filter((d) =>
    ['collection_reminder', 'escalated'].includes(d.status)
  );
  const faultyDoses = doses.filter((d) =>
    ['dispensing_fault', 'sensor_fault'].includes(d.status)
  );
  const lowStock = cartridges.filter((c) => c.is_configured && c.current_stock <= c.low_stock_threshold);

  const getDeliveryBadge = (status: string) => {
    switch (status) {
      case 'simulated':
        return 'bg-purple-50 text-purple-800 border-purple-200';
      case 'delivered':
        return 'bg-emerald-50 text-emerald-800 border-emerald-200';
      case 'sent':
        return 'bg-blue-50 text-blue-800 border-blue-200';
      case 'queued':
        return 'bg-amber-50 text-amber-800 border-amber-200';
      case 'failed':
        return 'bg-red-50 text-red-800 border-red-200';
      default:
        return 'bg-stone-50 text-stone-700 border-stone-200';
    }
  };

  return (
    <div className="space-y-6 pb-20">
      {/* Header */}
      <div className="bg-white rounded-3xl p-5 sm:p-6 border border-[#E5E4E0] shadow-2xs">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
          <div>
            <span className="text-xs font-bold uppercase tracking-wider text-[#145A4A] flex items-center gap-1.5">
              <Shield className="w-3.5 h-3.5" />
              Caregiver Supervision & Escalations
            </span>
            <h1 className="text-2xl font-black text-[#17313A] mt-1 tracking-tight">
              {settings.name} (Guardian)
            </h1>
            <p className="text-sm text-[#4F6267] mt-1">
              Monitoring: Eleanor Vance • ESP32 Pillbox #01 • Active Channel:{' '}
              <span className="font-bold uppercase text-[#145A4A]">{settings.notification_channel}</span>
            </p>
          </div>

          <div className="flex items-center gap-2 bg-[#F7F6F1] px-4 py-2.5 rounded-2xl border border-[#E5E4E0] self-start sm:self-auto text-xs font-bold text-[#17313A]">
            <Radio className="w-4 h-4 text-emerald-600 animate-pulse" />
            <span>Escalation Listener Active</span>
          </div>
        </div>
      </div>

      {/* Critical Status Summary Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
        {/* Uncollected Doses */}
        <div
          className={`p-4 rounded-3xl border ${
            uncollectedDoses.length > 0
              ? 'bg-amber-50 border-amber-300'
              : 'bg-white border-[#E5E4E0]'
          }`}
        >
          <div className="flex justify-between items-center text-xs font-bold text-[#4F6267]">
            <span>Pending Pickup</span>
            <Clock className="w-4 h-4" />
          </div>
          <div className="mt-2 text-2xl font-black text-[#17313A]">
            {uncollectedDoses.length}
          </div>
          <p className="text-xs text-[#4F6267] mt-1">
            {uncollectedDoses.length > 0
              ? 'Medicine waiting in tray > 5m'
              : 'All dispensed pills collected'}
          </p>
        </div>

        {/* Hardware Faults */}
        <div
          className={`p-4 rounded-3xl border ${
            faultyDoses.length > 0
              ? 'bg-red-50 border-red-300'
              : 'bg-white border-[#E5E4E0]'
          }`}
        >
          <div className="flex justify-between items-center text-xs font-bold text-[#4F6267]">
            <span>Hardware Faults</span>
            <AlertTriangle className="w-4 h-4" />
          </div>
          <div className="mt-2 text-2xl font-black text-[#17313A]">
            {faultyDoses.length}
          </div>
          <p className="text-xs text-[#4F6267] mt-1">
            {faultyDoses.length > 0 ? 'Servo or Sensor 1 disagreement' : 'Sensors operating normally'}
          </p>
        </div>

        {/* Low Stock Cartridges */}
        <div
          className={`p-4 rounded-3xl border ${
            lowStock.length > 0
              ? 'bg-amber-50 border-amber-300'
              : 'bg-white border-[#E5E4E0]'
          }`}
        >
          <div className="flex justify-between items-center text-xs font-bold text-[#4F6267]">
            <span>Low Cartridges</span>
            <Bell className="w-4 h-4" />
          </div>
          <div className="mt-2 text-2xl font-black text-[#17313A]">
            {lowStock.length}
          </div>
          <p className="text-xs text-[#4F6267] mt-1">
            {lowStock.length > 0
              ? `Cartridge ${lowStock.map((c) => c.cartridge_number).join(', ')} low`
              : 'Pill inventory sufficient'}
          </p>
        </div>
      </div>

      {/* Notification Channel & Consent Settings Card */}
      <div className="bg-white rounded-3xl p-5 sm:p-6 border border-[#E5E4E0] shadow-2xs space-y-5">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 border-b border-stone-100 pb-4">
          <div>
            <div className="flex items-center gap-2">
              <Settings className="w-4 h-4 text-[#145A4A]" />
              <h2 className="text-lg font-black text-[#17313A]">
                Notification Channels & Escalation Delivery
              </h2>
            </div>
            <p className="text-xs text-[#4F6267] mt-0.5">
              Configure real SMS or WhatsApp delivery with explicit caregiver opt-in consent.
            </p>
          </div>

          <button
            type="button"
            onClick={handleTestNotification}
            disabled={testingNotification}
            className="px-4 py-2 rounded-xl bg-stone-100 hover:bg-[#145A4A] hover:text-white text-[#17313A] font-bold text-xs flex items-center gap-1.5 transition-colors cursor-pointer self-start sm:self-auto disabled:opacity-50"
          >
            <Send className="w-3.5 h-3.5" />
            <span>{testingNotification ? 'Testing Channel...' : 'Send Test Alert'}</span>
          </button>
        </div>

        {/* Test Alert Result Feedback */}
        {testResult && (
          <div
            className={`p-4 rounded-2xl border text-xs space-y-1 animate-in fade-in ${
              testResult.delivery_status === 'failed'
                ? 'bg-red-50 border-red-200 text-red-900'
                : 'bg-emerald-50 border-emerald-200 text-emerald-900'
            }`}
          >
            <div className="flex items-center justify-between font-bold">
              <span className="flex items-center gap-1.5">
                {testResult.delivery_status === 'failed' ? (
                  <AlertTriangle className="w-4 h-4 text-red-600" />
                ) : (
                  <CheckCircle2 className="w-4 h-4 text-emerald-600" />
                )}
                Channel Test: {testResult.delivery_status.toUpperCase()} ({testResult.channel || settings.notification_channel})
              </span>
              <button
                onClick={() => setTestResult(null)}
                className="text-[11px] underline opacity-70 hover:opacity-100"
              >
                Dismiss
              </button>
            </div>
            {testResult.recipient && (
              <p className="opacity-90">Target: {testResult.recipient}</p>
            )}
            {testResult.provider_response && (
              <p className="font-mono text-[11px] bg-white/70 p-2 rounded-lg border border-stone-200/50">
                {testResult.provider_response}
              </p>
            )}
          </div>
        )}

        <form onSubmit={handleSaveSettings} className="space-y-4">
          {/* Caregiver Name Input */}
          <div>
            <label className="block text-xs font-bold text-[#17313A] mb-1">
              Caregiver Full Name <span className="text-red-500">*</span>
            </label>
            <div className="relative">
              <input
                type="text"
                required
                value={settings.name || ''}
                onChange={(e) => handleNameChange(e.target.value)}
                placeholder="e.g. Marcus Vance"
                className={`w-full px-3.5 py-2.5 rounded-xl border font-medium text-sm text-[#17313A] focus:outline-none focus:ring-2 ${
                  nameError
                    ? 'border-red-400 bg-red-50/50 focus:ring-red-400'
                    : 'border-stone-300 focus:ring-[#145A4A]'
                }`}
              />
            </div>
            {nameError ? (
              <span className="text-[11px] font-semibold text-red-600 mt-1 flex items-center gap-1">
                <AlertTriangle className="w-3.5 h-3.5 shrink-0" />
                {nameError}
              </span>
            ) : (
              <span className="text-[11px] text-[#4F6267] mt-0.5 block">
                Primary guardian name (alphabetic characters, hyphens, and spaces only)
              </span>
            )}
          </div>

          {/* Channel Selector */}
          <div>
            <label className="block text-xs font-bold text-[#17313A] mb-2">
              Primary Escalation Channel:
            </label>
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-2.5">
              {[
                { id: 'simulated', label: 'Simulated', desc: 'In-app local log', icon: MessageSquare },
                { id: 'sms', label: 'Twilio SMS', desc: 'Direct cellular SMS', icon: Smartphone },
                { id: 'whatsapp', label: 'Twilio WhatsApp', desc: 'Encrypted message', icon: Phone },
                { id: 'webhook', label: 'Webhook POST', desc: 'JSON endpoint', icon: Globe }
              ].map((ch) => {
                const isSelected = settings.notification_channel === ch.id;
                const Icon = ch.icon;
                return (
                  <button
                    key={ch.id}
                    type="button"
                    onClick={() => setSettings({ ...settings, notification_channel: ch.id as any })}
                    className={`p-3 text-left rounded-2xl border transition-all cursor-pointer ${
                      isSelected
                        ? 'border-[#145A4A] bg-[#EAF2EC]/60 ring-2 ring-[#145A4A]/20'
                        : 'border-stone-200 bg-white hover:border-stone-300'
                    }`}
                  >
                    <Icon className={`w-4 h-4 mb-1.5 ${isSelected ? 'text-[#145A4A]' : 'text-[#4F6267]'}`} />
                    <div className="font-bold text-xs text-[#17313A]">{ch.label}</div>
                    <div className="text-[10px] text-[#4F6267]">{ch.desc}</div>
                  </button>
                );
              })}
            </div>
          </div>

          {/* Contact Numbers with International Phone Input */}
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 pt-1">
            <PhoneInput
              label="Caregiver Mobile Phone (SMS Target)"
              value={settings.phone || ''}
              onChange={(val) => setSettings({ ...settings, phone: val })}
              helperText="E.164 formatted number used for direct SMS escalation"
              defaultCountryCode="+91"
            />

            <PhoneInput
              label="Caregiver WhatsApp Phone"
              value={settings.whatsapp_phone || ''}
              onChange={(val) => setSettings({ ...settings, whatsapp_phone: val })}
              helperText="E.164 formatted number used for WhatsApp notifications"
              defaultCountryCode="+91"
            />
          </div>

          {/* Consent Checkboxes */}
          <div className="p-4 bg-[#F7F6F1] rounded-2xl border border-stone-200 space-y-3">
            <span className="text-xs font-bold text-[#17313A] block uppercase tracking-wider">
              Caregiver Opt-In Consents (Required by Twilio & Regulatory Compliance)
            </span>

            <label className="flex items-start gap-2.5 cursor-pointer">
              <input
                type="checkbox"
                checked={settings.sms_consent}
                onChange={(e) => setSettings({ ...settings, sms_consent: e.target.checked })}
                className="mt-0.5 w-4 h-4 text-[#145A4A] rounded accent-[#145A4A]"
              />
              <span className="text-xs text-[#17313A]">
                <strong>Explicit SMS Consent:</strong> I agree to receive urgent CarePill medication escalation alerts via cellular SMS at my registered phone number.
              </span>
            </label>

            <label className="flex items-start gap-2.5 cursor-pointer">
              <input
                type="checkbox"
                checked={settings.whatsapp_consent}
                onChange={(e) => setSettings({ ...settings, whatsapp_consent: e.target.checked })}
                className="mt-0.5 w-4 h-4 text-[#145A4A] rounded accent-[#145A4A]"
              />
              <span className="text-xs text-[#17313A]">
                <strong>Explicit WhatsApp Consent:</strong> I agree to receive CarePill medication alerts and device telemetry notifications via WhatsApp.
              </span>
            </label>
          </div>

          {/* Minimal Text Alert Spec Note */}
          <div className="p-3 bg-stone-50 rounded-xl border border-stone-200 text-xs text-[#4F6267] flex items-center justify-between">
            <span>
              <strong>Standard Notification Text:</strong> "CarePill alert: A scheduled medication has not been collected. Please check on the patient. Time: [time]."
            </span>
          </div>

          {/* Action Footer */}
          <div className="flex items-center justify-end gap-3 pt-2">
            {saveSuccess && (
              <span className="text-xs font-bold text-emerald-800 flex items-center gap-1 animate-in fade-in">
                <CheckCircle2 className="w-4 h-4" />
                Preferences Saved!
              </span>
            )}
            <button
              type="submit"
              disabled={savingSettings}
              className="px-5 py-2.5 rounded-xl bg-[#145A4A] hover:bg-[#0E4236] text-white font-bold text-xs shadow-xs transition-colors cursor-pointer disabled:opacity-50"
            >
              {savingSettings ? 'Saving...' : 'Save Notification Preferences'}
            </button>
          </div>
        </form>
      </div>

      {/* Escalation Alerts Feed */}
      <div className="space-y-3">
        <div className="flex items-center justify-between px-1">
          <h2 className="text-xs font-black uppercase tracking-wider text-[#4F6267] flex items-center gap-1.5">
            <Bell className="w-4 h-4 text-[#145A4A]" />
            Caregiver Alert Center & Escalation History
          </h2>
          <span className="text-xs text-[#4F6267]">
            {unacknowledgedAlerts.length} unacknowledged
          </span>
        </div>

        {alerts.length === 0 ? (
          <div className="p-8 text-center bg-white rounded-3xl border border-[#E5E4E0] text-[#4F6267]">
            <CheckCircle2 className="w-8 h-8 text-emerald-600 mx-auto mb-2" />
            <p className="text-sm font-semibold">No alerts recorded. Everything is peaceful.</p>
          </div>
        ) : (
          <div className="space-y-3">
            {alerts.map((alert) => (
              <div
                key={alert.id}
                className={`p-4 sm:p-5 rounded-3xl border transition-all ${
                  !alert.acknowledged
                    ? 'bg-white border-red-300 shadow-sm'
                    : 'bg-[#F7F6F1] border-[#E5E4E0] opacity-80'
                }`}
              >
                <div className="flex items-start justify-between gap-3">
                  <div>
                    <div className="flex items-center gap-2">
                      <span className="text-xs font-bold px-2.5 py-0.5 rounded-full bg-red-100 text-red-900">
                        {alert.alert_type.toUpperCase().replace('_', ' ')}
                      </span>
                      <span
                        className={`text-[11px] font-bold px-2 py-0.5 rounded border uppercase ${getDeliveryBadge(
                          alert.delivery_status
                        )}`}
                      >
                        Delivery: {alert.delivery_status}
                      </span>
                    </div>

                    <p className="font-bold text-sm sm:text-base text-[#17313A] mt-2 leading-snug">
                      {alert.message}
                    </p>

                    {alert.provider_response && (
                      <p className="text-[11px] font-mono text-[#4F6267] mt-1 bg-stone-100 p-1.5 rounded">
                        {alert.provider_response}
                      </p>
                    )}
                  </div>

                  {!alert.acknowledged ? (
                    <button
                      onClick={() => handleAcknowledge(alert.id)}
                      disabled={ackingId === alert.id}
                      className="px-4 py-2 rounded-xl bg-[#145A4A] hover:bg-[#0E4236] text-white font-bold text-xs shrink-0 transition-colors shadow-xs cursor-pointer"
                    >
                      {ackingId === alert.id ? 'Saving...' : 'Acknowledge'}
                    </button>
                  ) : (
                    <span className="text-xs font-semibold text-emerald-800 flex items-center gap-1 shrink-0">
                      <Check className="w-4 h-4" />
                      Acknowledged
                    </span>
                  )}
                </div>

                <div className="mt-3 pt-2 border-t border-stone-200/60 flex items-center justify-between text-[11px] text-[#4F6267]">
                  <span>Sent to: {alert.recipient_contact || 'Registered guardian'} ({alert.channel})</span>
                  <span>{new Date(alert.created_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}</span>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
};
