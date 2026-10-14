import React, { useState, useEffect } from 'react';
import { X, Disc, AlertTriangle } from 'lucide-react';
import { Cartridge, Medication } from '../types';
import { api } from '../services/api';

interface SetupCartridgeModalProps {
  cartridge: Cartridge | null;
  medications: Medication[];
  isOpen: boolean;
  onClose: () => void;
  onSuccess: () => void;
}

export const SetupCartridgeModal: React.FC<SetupCartridgeModalProps> = ({
  cartridge,
  medications,
  isOpen,
  onClose,
  onSuccess
}) => {
  const [selectedMedId, setSelectedMedId] = useState<string>('');
  const [initialStock, setInitialStock] = useState<number>(14);
  const [lowStockThreshold, setLowStockThreshold] = useState<number>(5);
  const [confirmedPhysical, setConfirmedPhysical] = useState<boolean>(false);
  const [loading, setLoading] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (cartridge) {
      setSelectedMedId(cartridge.medication_id || (medications[0]?.id ?? ''));
      setInitialStock(cartridge.current_stock || 14);
      setLowStockThreshold(cartridge.low_stock_threshold || 5);
      setConfirmedPhysical(cartridge.is_configured);
      setError(null);
    }
  }, [cartridge, medications]);

  if (!isOpen || !cartridge) return null;

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!confirmedPhysical) {
      setError('Please physically confirm that the cartridge is inserted and locked.');
      return;
    }

    setLoading(true);
    setError(null);
    try {
      await api.setupCartridge({
        cartridge_number: cartridge.cartridge_number,
        device_id: cartridge.device_id || 'ESP32_PILLBOX_01',
        medication_id: selectedMedId || undefined,
        initial_stock: Number(initialStock),
        low_stock_threshold: Number(lowStockThreshold),
        confirm_physical_loaded: confirmedPhysical
      });
      onSuccess();
      onClose();
    } catch (err: any) {
      setError(err.message || 'Cartridge configuration failed.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-3 sm:p-4 bg-black/60 backdrop-blur-xs">
      <div className="bg-white rounded-3xl w-full max-w-md shadow-2xl border border-stone-200 overflow-hidden">
        {/* Header */}
        <div className="px-5 py-4 border-b border-stone-200 bg-[#F7F6F1] flex items-center justify-between">
          <div className="flex items-center gap-2.5">
            <div className="w-8 h-8 rounded-lg bg-[#145A4A] flex items-center justify-center text-white">
              <Disc className="w-5 h-5" />
            </div>
            <div>
              <h2 className="text-lg font-bold text-[#17313A]">
                Configure Slot #{cartridge.cartridge_number}
              </h2>
              <p className="text-xs text-[#4F6267]">Device: {cartridge.device_id || 'ESP32_PILLBOX_01'}</p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="w-8 h-8 rounded-full bg-white hover:bg-stone-200 flex items-center justify-center text-[#4F6267] cursor-pointer"
          >
            <X className="w-4 h-4" />
          </button>
        </div>

        {/* Form */}
        <form onSubmit={handleSubmit} className="p-5 space-y-4 text-sm">
          {error && (
            <div className="p-3 rounded-xl bg-red-50 border border-red-200 text-xs text-red-900 font-semibold flex items-center gap-2">
              <AlertTriangle className="w-4 h-4 shrink-0 text-red-600" />
              <span>{error}</span>
            </div>
          )}

          <div>
            <label className="block text-xs font-bold text-[#17313A] mb-1">
              Assign Medication
            </label>
            <select
              value={selectedMedId}
              onChange={(e) => setSelectedMedId(e.target.value)}
              className="w-full px-3.5 py-2.5 rounded-xl border border-stone-300 bg-white font-medium text-sm text-[#17313A] focus:outline-none focus:ring-2 focus:ring-[#145A4A]"
            >
              <option value="">-- Leave Unassigned (Empty) --</option>
              {medications.map((m) => (
                <option key={m.id} value={m.id}>
                  {m.name} ({m.strength || 'standard dose'})
                </option>
              ))}
            </select>
          </div>

          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block text-xs font-bold text-[#17313A] mb-1">
                Initial Pill Count
              </label>
              <input
                type="number"
                min="0"
                max="30"
                value={initialStock}
                onChange={(e) => setInitialStock(Math.max(0, parseInt(e.target.value) || 0))}
                className="w-full px-3.5 py-2.5 rounded-xl border border-stone-300 font-bold text-sm text-[#17313A] focus:outline-none focus:ring-2 focus:ring-[#145A4A]"
              />
              <span className="text-[11px] text-[#4F6267] mt-0.5 block">Max capacity: 30</span>
            </div>

            <div>
              <label className="block text-xs font-bold text-[#17313A] mb-1">
                Low-Stock Alert At
              </label>
              <input
                type="number"
                min="1"
                max="15"
                value={lowStockThreshold}
                onChange={(e) => setLowStockThreshold(Math.max(1, parseInt(e.target.value) || 1))}
                className="w-full px-3.5 py-2.5 rounded-xl border border-stone-300 font-bold text-sm text-[#17313A] focus:outline-none focus:ring-2 focus:ring-[#145A4A]"
              />
              <span className="text-[11px] text-[#4F6267] mt-0.5 block">Threshold for caregiver</span>
            </div>
          </div>

          <div className="p-3.5 bg-[#F7F6F1] rounded-2xl border border-stone-200">
            <label className="flex items-start gap-2.5 cursor-pointer">
              <input
                type="checkbox"
                checked={confirmedPhysical}
                onChange={(e) => setConfirmedPhysical(e.target.checked)}
                className="mt-0.5 w-4 h-4 text-[#145A4A] rounded accent-[#145A4A]"
              />
              <span className="text-xs font-medium text-[#17313A]">
                <strong>Physical verification:</strong> I confirm the circular cartridge is seated into rotary slot {cartridge.cartridge_number} and loaded with the specified tablets.
              </span>
            </label>
          </div>

          <div className="pt-2 flex items-center justify-end gap-2">
            <button
              type="button"
              onClick={onClose}
              className="px-4 py-2.5 rounded-xl border border-stone-300 font-bold text-xs text-[#4F6267] hover:bg-stone-100 cursor-pointer"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={loading}
              className="px-5 py-2.5 rounded-xl bg-[#145A4A] hover:bg-[#0E4236] text-white font-bold text-xs shadow-xs transition-colors cursor-pointer disabled:opacity-50"
            >
              {loading ? 'Saving...' : 'Save Configuration'}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
};
