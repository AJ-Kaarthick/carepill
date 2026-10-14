import React, { useState } from 'react';
import { X, Plus, Disc, CheckCircle2, AlertTriangle } from 'lucide-react';
import { Cartridge } from '../types';
import { api } from '../services/api';

interface RefillModalProps {
  cartridge: Cartridge | null;
  isOpen: boolean;
  onClose: () => void;
  onSuccess: () => void;
}

export const RefillModal: React.FC<RefillModalProps> = ({
  cartridge,
  isOpen,
  onClose,
  onSuccess
}) => {
  const [addedPills, setAddedPills] = useState<number>(10);
  const [notes, setNotes] = useState<string>('Routine weekly refill');
  const [confirmedPhysical, setConfirmedPhysical] = useState<boolean>(false);
  const [loading, setLoading] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);

  if (!isOpen || !cartridge) return null;

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!confirmedPhysical) {
      setError('Please physically confirm that pills are loaded into the circular cartridge.');
      return;
    }
    if (addedPills <= 0) {
      setError('Added pills must be greater than zero.');
      return;
    }

    setLoading(true);
    setError(null);
    try {
      await api.refillCartridge(cartridge.cartridge_number, addedPills, notes);
      onSuccess();
      onClose();
    } catch (err: any) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  const newProjectedStock = Math.min(cartridge.capacity, cartridge.current_stock + addedPills);

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
                Refill Cartridge {cartridge.cartridge_number}
              </h2>
              <p className="text-xs text-[#4F6267]">{cartridge.medication_name || 'Unassigned'}</p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="w-8 h-8 rounded-full bg-white hover:bg-stone-200 flex items-center justify-center text-[#4F6267]"
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

          <div className="p-3 bg-[#F7F6F1] rounded-2xl flex items-center justify-between">
            <div>
              <span className="text-xs text-[#4F6267] block">Current Pill Count:</span>
              <span className="text-lg font-bold text-[#17313A]">{cartridge.current_stock} / {cartridge.capacity}</span>
            </div>
            <div className="text-right">
              <span className="text-xs text-[#4F6267] block">Projected Total:</span>
              <span className="text-lg font-bold text-emerald-800">{newProjectedStock} pills</span>
            </div>
          </div>

          <div>
            <label className="block text-xs font-bold text-[#17313A] mb-1">
              Pills to Add into Compartments:
            </label>
            <div className="flex items-center gap-2">
              <input
                type="number"
                min="1"
                max={cartridge.capacity - cartridge.current_stock}
                value={addedPills}
                onChange={(e) => setAddedPills(parseInt(e.target.value) || 0)}
                className="w-full px-3 py-2 rounded-xl border border-stone-300 font-bold text-base text-[#17313A] focus:outline-[#145A4A]"
              />
              <div className="flex gap-1">
                {[5, 10, 15].map((amt) => (
                  <button
                    key={amt}
                    type="button"
                    onClick={() => setAddedPills(amt)}
                    className="px-2.5 py-2 text-xs font-bold rounded-lg bg-stone-100 hover:bg-stone-200 text-[#17313A]"
                  >
                    +{amt}
                  </button>
                ))}
              </div>
            </div>
          </div>

          <div>
            <label className="block text-xs font-bold text-[#17313A] mb-1">
              Refill Note (Audit Trail):
            </label>
            <input
              type="text"
              value={notes}
              onChange={(e) => setNotes(e.target.value)}
              className="w-full px-3 py-2 rounded-xl border border-stone-300 text-xs text-[#17313A]"
            />
          </div>

          {/* Physical Confirmation Checkbox */}
          <label className="flex items-start gap-2.5 p-3 rounded-xl border border-stone-200 bg-stone-50 cursor-pointer">
            <input
              type="checkbox"
              checked={confirmedPhysical}
              onChange={(e) => setConfirmedPhysical(e.target.checked)}
              className="mt-0.5 w-4 h-4 rounded text-[#145A4A] accent-[#145A4A]"
            />
            <span className="text-xs text-[#17313A] leading-relaxed">
              I have physically loaded these pills into Cartridge {cartridge.cartridge_number} and confirmed the circular rotary seating.
            </span>
          </label>

          <div className="pt-2 flex justify-end gap-2">
            <button
              type="button"
              onClick={onClose}
              className="px-4 py-2.5 rounded-xl border border-stone-300 text-xs font-semibold text-[#4F6267]"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={loading || !confirmedPhysical}
              className="px-6 py-2.5 rounded-xl bg-[#145A4A] hover:bg-[#0E4236] text-white font-bold text-xs disabled:opacity-50 transition-colors shadow-xs"
            >
              {loading ? 'Recording...' : 'Confirm Refill'}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
};
