import React, { useState } from 'react';
import {
  Disc,
  Plus,
  AlertTriangle,
  RotateCcw,
  CheckCircle2,
  Clock,
  Layers,
  History,
  Settings
} from 'lucide-react';
import { Cartridge, InventoryTransaction, Medication } from '../types';
import { RefillModal } from '../components/RefillModal';
import { SetupCartridgeModal } from '../components/SetupCartridgeModal';
import { api } from '../services/api';

interface CartridgesPageProps {
  cartridges: Cartridge[];
  transactions: InventoryTransaction[];
  medications: Medication[];
  onRefresh: () => void;
}

export const CartridgesPage: React.FC<CartridgesPageProps> = ({
  cartridges,
  transactions,
  medications,
  onRefresh
}) => {
  const [selectedCartridge, setSelectedCartridge] = useState<Cartridge | null>(null);
  const [isRefillOpen, setIsRefillOpen] = useState(false);
  const [isSetupOpen, setIsSetupOpen] = useState(false);
  const [loadingConfig, setLoadingConfig] = useState(false);
  const [configSuccessMsg, setConfigSuccessMsg] = useState<string | null>(null);
  const [confirmDownsize, setConfirmDownsize] = useState<{
    targetCount: number;
    message: string;
    affected_cartridges: any[];
  } | null>(null);
  const [reconcilingNum, setReconcilingNum] = useState<number | null>(null);

  const handleClearReconciliation = async (cartridgeNumber: number) => {
    if (!window.confirm(`Confirm physical check: Have you physically inspected Cartridge ${cartridgeNumber} and verified that all pills are removed?`)) {
      return;
    }
    setReconcilingNum(cartridgeNumber);
    try {
      const res = await api.reconcileCartridge(cartridgeNumber, {
        reconciled_by: 'Marcus Vance (Caregiver)',
        notes: 'Physically unloaded and verified empty by caregiver',
        confirm_physically_empty: true
      });
      alert(res.message);
      onRefresh();
    } catch (err: any) {
      alert(`Failed to clear reconciliation: ${err.message}`);
    } finally {
      setReconcilingNum(null);
    }
  };

  const handleOpenRefill = (cart: Cartridge) => {
    setSelectedCartridge(cart);
    setIsRefillOpen(true);
  };

  const handleOpenSetup = (cart: Cartridge) => {
    setSelectedCartridge(cart);
    setIsSetupOpen(true);
  };

  const handleConfigChange = async (targetCount: number, force = false) => {
    setLoadingConfig(true);
    setConfigSuccessMsg(null);
    try {
      const res = await api.configureDeviceHardware({
        device_id: 'ESP32_PILLBOX_01',
        cartridge_count: targetCount,
        force
      });
      setConfirmDownsize(null);
      setConfigSuccessMsg(res.message);
      onRefresh();
    } catch (err: any) {
      if (err.requires_confirmation || err.detail?.requires_confirmation) {
        const detail = err.detail || err;
        setConfirmDownsize({
          targetCount,
          message: detail.message,
          affected_cartridges: detail.affected_cartridges || []
        });
      } else {
        alert(err.message || err.detail || 'Hardware configuration failed');
      }
    } finally {
      setLoadingConfig(false);
    }
  };

  return (
    <div className="space-y-6 pb-20">
      {/* Header */}
      <div className="bg-white rounded-3xl p-5 sm:p-6 border border-[#E5E4E0] shadow-2xs">
        <h1 className="text-2xl font-black text-[#17313A] tracking-tight">
          Physical Cartridges & Hardware Layout
        </h1>
        <p className="text-sm text-[#4F6267] mt-1">
          Detachable circular rotary cartridges with optoelectronic drop verification.
        </p>
      </div>

      {/* Hardware Configuration Bar */}
      <div className="bg-white rounded-3xl p-5 border border-[#E5E4E0] shadow-2xs">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
          <div>
            <div className="flex items-center gap-2">
              <span className="text-xs font-bold uppercase tracking-wider text-[#145A4A] flex items-center gap-1.5">
                <Layers className="w-3.5 h-3.5" />
                Physical Carousel Sizing
              </span>
              <span className="text-[11px] font-bold px-2.5 py-0.5 rounded-full bg-[#EAF2EC] text-[#145A4A]">
                Device: ESP32_PILLBOX_01
              </span>
            </div>
            <h2 className="text-lg font-black text-[#17313A] mt-1">
              Active Carousel Slots: {cartridges.length} Cartridges
            </h2>
            <p className="text-xs text-[#4F6267] mt-0.5">
              Select circular cartridge capacity: 4 (default), 6, or 8 slots.
            </p>
          </div>

          <div className="flex items-center bg-[#F7F6F1] p-1.5 rounded-2xl border border-stone-200 self-start sm:self-auto">
            {[4, 6, 8].map((count) => {
              const isActive = cartridges.length === count;
              return (
                <button
                  key={count}
                  onClick={() => handleConfigChange(count, false)}
                  disabled={loadingConfig || isActive}
                  className={`px-4 py-2 rounded-xl text-xs font-black transition-all cursor-pointer ${
                    isActive
                      ? 'bg-[#145A4A] text-white shadow-xs'
                      : 'text-[#4F6267] hover:text-[#17313A] hover:bg-stone-200/60'
                  }`}
                >
                  {count} Cartridges
                </button>
              );
            })}
          </div>
        </div>

        {configSuccessMsg && (
          <div className="mt-3 p-3 bg-emerald-50 border border-emerald-200 rounded-xl text-xs font-semibold text-emerald-900 flex items-center gap-2 animate-in fade-in">
            <CheckCircle2 className="w-4 h-4 text-emerald-700 shrink-0" />
            <span>{configSuccessMsg}</span>
          </div>
        )}
      </div>

      {/* Cartridges Grid (Responsive for 4, 6, or 8 items) */}
      <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-4">
        {cartridges.map((cart) => {
          const fillPct = Math.round((cart.current_stock / cart.capacity) * 100);
          const isLow = cart.is_configured && cart.current_stock <= cart.low_stock_threshold;

          return (
            <div
              key={cart.id}
              className={`bg-white rounded-3xl p-5 border transition-all flex flex-col justify-between ${
                isLow
                  ? 'border-amber-400 ring-2 ring-amber-200'
                  : 'border-[#E5E4E0] shadow-2xs'
              }`}
            >
              <div>
                <div className="flex items-start justify-between">
                  <div className="flex items-center gap-3">
                    <div
                      className={`w-12 h-12 rounded-2xl flex items-center justify-center font-black text-lg ${
                        isLow ? 'bg-amber-100 text-amber-900' : 'bg-[#EAF2EC] text-[#145A4A]'
                      }`}
                    >
                      C{cart.cartridge_number}
                    </div>
                    <div>
                      <h3 className="font-bold text-base text-[#17313A] line-clamp-1">
                        {cart.medication_name || 'Empty Slot'}
                      </h3>
                      <span className="text-xs font-semibold text-[#4F6267]">
                        {cart.medication_strength || 'Unassigned'}
                      </span>
                    </div>
                  </div>

                  {cart.needs_reconciliation ? (
                    <span className="text-[10px] font-extrabold px-2 py-0.5 rounded-full bg-rose-100 text-rose-900 border border-rose-300">
                      Quarantined
                    </span>
                  ) : cart.is_configured ? (
                    <span className="text-[11px] font-bold px-2 py-0.5 rounded-full bg-emerald-50 text-emerald-800">
                      Active
                    </span>
                  ) : (
                    <span className="text-[11px] font-bold px-2 py-0.5 rounded-full bg-stone-100 text-stone-600">
                      Empty
                    </span>
                  )}
                </div>

                {/* Pill Level Visual Bar */}
                <div className="mt-4 space-y-1.5">
                  <div className="flex justify-between text-xs font-semibold">
                    <span className="text-[#4F6267]">Stock Level</span>
                    <span className={isLow ? 'text-amber-800 font-bold' : 'text-[#17313A]'}>
                      {cart.current_stock} of {cart.capacity} pills ({fillPct}%)
                    </span>
                  </div>

                  <div className="w-full h-3 bg-[#F7F6F1] rounded-full overflow-hidden border border-stone-200">
                    <div
                      className={`h-full transition-all duration-500 rounded-full ${
                        isLow ? 'bg-amber-500' : 'bg-[#145A4A]'
                      }`}
                      style={{ width: `${Math.min(100, fillPct)}%` }}
                    />
                  </div>
                </div>

                {/* Quarantine Alert & Clearance Button */}
                {cart.needs_reconciliation && (
                  <div className="mt-3 p-3 bg-rose-50 border border-rose-200 rounded-2xl space-y-2 text-xs">
                    <div className="flex items-start gap-1.5 font-bold text-rose-950">
                      <AlertTriangle className="w-4 h-4 text-rose-700 shrink-0 mt-0.5" />
                      <span>Physical Reconciliation Required</span>
                    </div>
                    <p className="text-[11px] leading-relaxed text-rose-800">
                      {cart.quarantine_reason || 'Pills remain in this slot from a previous medication. Verify the slot is physically empty before refilling or reassigning.'}
                    </p>
                    <button
                      onClick={() => handleClearReconciliation(cart.cartridge_number)}
                      disabled={reconcilingNum === cart.cartridge_number}
                      className="w-full py-1.5 px-3 rounded-xl bg-rose-700 hover:bg-rose-800 disabled:opacity-50 text-white font-bold text-xs flex items-center justify-center gap-1.5 transition-colors cursor-pointer"
                    >
                      <CheckCircle2 className="w-3.5 h-3.5" />
                      <span>{reconcilingNum === cart.cartridge_number ? 'Clearing...' : 'Verify Empty & Clear Quarantine'}</span>
                    </button>
                  </div>
                )}

                {/* Status Warning */}
                {!cart.needs_reconciliation && isLow && (
                  <div className="mt-3 p-2 bg-amber-50 border border-amber-200 rounded-xl text-xs font-semibold text-amber-900 flex items-center gap-1.5">
                    <AlertTriangle className="w-3.5 h-3.5 shrink-0 text-amber-700" />
                    <span>Low stock warning!</span>
                  </div>
                )}
              </div>

              {/* Action Buttons */}
              <div className="mt-4 pt-3 border-t border-stone-100 flex items-center justify-between gap-2">
                <button
                  onClick={() => handleOpenSetup(cart)}
                  className="flex-1 justify-center px-2.5 py-2 rounded-xl border border-stone-300 hover:bg-stone-100 text-[#4F6267] hover:text-[#17313A] font-bold text-xs flex items-center gap-1 transition-colors cursor-pointer"
                  title="Configure Slot"
                >
                  <Settings className="w-3.5 h-3.5 shrink-0" />
                  <span className="truncate">Configure</span>
                </button>

                <button
                  onClick={() => handleOpenRefill(cart)}
                  disabled={Boolean(cart.needs_reconciliation)}
                  className={`flex-1 justify-center px-2.5 py-2 rounded-xl text-white font-bold text-xs flex items-center gap-1 shadow-xs transition-colors ${
                    cart.needs_reconciliation
                      ? 'bg-stone-300 cursor-not-allowed opacity-60'
                      : 'bg-[#145A4A] hover:bg-[#0E4236] cursor-pointer'
                  }`}
                  title={cart.needs_reconciliation ? 'Clear physical reconciliation before refilling' : 'Refill Slot'}
                >
                  <Plus className="w-3.5 h-3.5 shrink-0" />
                  <span className="truncate">Refill</span>
                </button>
              </div>
            </div>
          );
        })}
      </div>

      {/* Inventory Audit Trail */}
      <div className="space-y-3 pt-2">
        <h2 className="text-xs font-black uppercase tracking-wider text-[#4F6267] flex items-center gap-1.5">
          <History className="w-4 h-4 text-[#145A4A]" />
          Auditable Inventory Decrement & Refill History
        </h2>

        <div className="bg-white rounded-3xl border border-[#E5E4E0] shadow-2xs overflow-hidden">
          <div className="divide-y divide-stone-100 text-xs">
            {transactions.slice(0, 8).map((tx) => (
              <div key={tx.id} className="p-3.5 sm:px-5 flex items-center justify-between gap-3">
                <div className="flex items-center gap-3">
                  <div
                    className={`w-8 h-8 rounded-xl flex items-center justify-center font-bold text-xs ${
                      tx.delta < 0 ? 'bg-blue-50 text-blue-900' : 'bg-emerald-50 text-emerald-900'
                    }`}
                  >
                    {tx.delta > 0 ? `+${tx.delta}` : tx.delta}
                  </div>
                  <div>
                    <span className="font-bold text-[#17313A] block">
                      Cartridge {tx.cartridge_number} • {tx.medication_name}
                    </span>
                    <span className="text-[11px] text-[#4F6267]">
                      {tx.reason === 'dispense_confirmed'
                        ? 'Sensor 1 confirmed physical dispense'
                        : tx.reason === 'refill'
                        ? 'Manual pill refill'
                        : 'Manual adjustment'}
                      {tx.confirmed_sensor_id ? ` via ${tx.confirmed_sensor_id}` : ''}
                    </span>
                  </div>
                </div>

                <div className="text-right shrink-0">
                  <span className="text-[#17313A] font-semibold block">
                    {tx.previous_stock} → {tx.new_stock}
                  </span>
                  <span className="text-[10px] text-[#4F6267]">
                    {new Date(tx.timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                  </span>
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* Refill Modal */}
      <RefillModal
        cartridge={selectedCartridge}
        isOpen={isRefillOpen}
        onClose={() => setIsRefillOpen(false)}
        onSuccess={onRefresh}
      />

      {/* Setup Cartridge Modal */}
      <SetupCartridgeModal
        cartridge={selectedCartridge}
        medications={medications}
        isOpen={isSetupOpen}
        onClose={() => setIsSetupOpen(false)}
        onSuccess={onRefresh}
      />

      {/* Downsize Confirmation Modal */}
      {confirmDownsize && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/60 backdrop-blur-xs">
          <div className="bg-white rounded-3xl w-full max-w-md shadow-2xl border border-amber-300 p-6 space-y-4">
            <div className="flex items-center gap-3 text-amber-700">
              <div className="w-10 h-10 rounded-2xl bg-amber-100 flex items-center justify-center">
                <AlertTriangle className="w-6 h-6 text-amber-600" />
              </div>
              <div>
                <h3 className="font-black text-base text-[#17313A]">Hardware Downsize Warning</h3>
                <span className="text-xs text-[#4F6267]">Stock or medication found in slots</span>
              </div>
            </div>

            <p className="text-xs text-[#17313A] leading-relaxed">
              {confirmDownsize.message}
            </p>

            {confirmDownsize.affected_cartridges && confirmDownsize.affected_cartridges.length > 0 && (
              <div className="bg-amber-50 p-3 rounded-2xl border border-amber-200 space-y-1.5 text-xs">
                <span className="font-bold text-amber-900 block">Affected Cartridges:</span>
                {confirmDownsize.affected_cartridges.map((c: any) => (
                  <div key={c.cartridge_number} className="flex justify-between text-amber-800">
                    <span>Slot {c.cartridge_number}: {c.medication_name}</span>
                    <span className="font-bold">{c.current_stock} pills</span>
                  </div>
                ))}
              </div>
            )}

            <div className="flex items-center justify-end gap-2 pt-2">
              <button
                onClick={() => setConfirmDownsize(null)}
                className="px-4 py-2.5 rounded-xl border border-stone-300 font-bold text-xs text-[#4F6267] hover:bg-stone-100 cursor-pointer"
              >
                Cancel
              </button>
              <button
                onClick={() => handleConfigChange(confirmDownsize.targetCount, true)}
                className="px-5 py-2.5 rounded-xl bg-red-600 hover:bg-red-700 text-white font-bold text-xs shadow-xs transition-colors cursor-pointer"
              >
                Confirm Force Reconfiguration
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
