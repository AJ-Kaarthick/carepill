import React from 'react';
import {
  Calendar,
  CheckCircle2,
  Clock,
  AlertTriangle,
  Heart,
  Hand,
  Sparkles,
  ChevronRight
} from 'lucide-react';
import { DoseOccurrence, Cartridge } from '../types';
import { PillCard } from '../components/PillCard';

interface PatientDashboardProps {
  doses: DoseOccurrence[];
  currentDose: DoseOccurrence | null;
  cartridges: Cartridge[];
  isSimulated?: boolean;
  onDispense: (doseId: string) => void;
  onSimulateDispense?: (doseId: string) => void;
  onCancelDispense?: (doseId: string) => void;
  onPickup: (doseId: string) => void;
  onManualConfirm: (doseId: string) => void;
  onOpenSimulator: () => void;
}

export const PatientDashboard: React.FC<PatientDashboardProps> = ({
  doses,
  currentDose,
  cartridges,
  isSimulated = true,
  onDispense,
  onSimulateDispense,
  onCancelDispense,
  onPickup,
  onManualConfirm,
  onOpenSimulator
}) => {
  const todayFormatted = new Date().toLocaleDateString('en-US', {
    weekday: 'long',
    month: 'long',
    day: 'numeric'
  });

  // Separate metrics: Collected from Tray vs Confirmed Taken (Ingestion)
  const collectedCount = doses.filter((d) => d.status === 'collected' || d.status === 'confirmed_taken').length;
  const confirmedTakenCount = doses.filter((d) => d.status === 'confirmed_taken').length;
  const totalDoses = doses.length;
  const adherencePct = totalDoses > 0 ? Math.round((collectedCount / totalDoses) * 100) : 100;

  // Find low stock cartridges
  const lowStockCartridges = cartridges.filter(
    (c) => c.is_configured && c.current_stock <= c.low_stock_threshold
  );

  // Check if current dose is due or simply upcoming
  const isCurrentDue = currentDose && (currentDose.is_due ?? (currentDose.status !== 'scheduled'));
  const isFinished = currentDose && (currentDose.status === 'collected' || currentDose.status === 'confirmed_taken');

  return (
    <div className="space-y-6 pb-20">
      {/* 1. Senior-Friendly Greeting & Today's Progress */}
      <div className="bg-white rounded-3xl p-5 sm:p-6 border border-[#E5E4E0] shadow-2xs">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
          <div>
            <span className="text-xs font-bold uppercase tracking-wider text-[#145A4A] flex items-center gap-1.5">
              <Calendar className="w-3.5 h-3.5" />
              {todayFormatted}
            </span>
            <h1 className="text-2xl sm:text-3xl font-black text-[#17313A] mt-1 tracking-tight">
              Good day, Eleanor
            </h1>
            <p className="text-sm text-[#4F6267] mt-1">
              {collectedCount === totalDoses && totalDoses > 0
                ? "All your scheduled medications for today have been collected from the dispenser. Excellent job!"
                : `You have collected ${collectedCount} of ${totalDoses} doses today.`}
            </p>
          </div>

          {/* Adherence Ring / Metric Badges */}
          <div className="flex items-center gap-3 bg-[#F7F6F1] px-4 py-3 rounded-2xl border border-[#E5E4E0] self-start sm:self-auto">
            <div className="w-12 h-12 rounded-full border-4 border-[#145A4A] flex items-center justify-center font-black text-sm text-[#145A4A]">
              {adherencePct}%
            </div>
            <div>
              <span className="text-xs font-bold text-[#17313A] block">Today's Progress</span>
              <div className="text-xs text-[#4F6267] font-medium">
                <span className="text-[#145A4A] font-bold">{collectedCount} of {totalDoses}</span> collected from tray
              </div>
            </div>
          </div>
        </div>

        {/* Low-stock warning banner */}
        {lowStockCartridges.length > 0 && (
          <div className="mt-4 p-3 bg-amber-50 border border-amber-200 rounded-2xl flex items-center justify-between text-xs text-amber-900 font-medium">
            <div className="flex items-center gap-2">
              <AlertTriangle className="w-4 h-4 text-amber-700 shrink-0" />
              <span>
                <strong>Low Stock Notice:</strong> Cartridge{' '}
                {lowStockCartridges.map((c) => c.cartridge_number).join(', ')} has{' '}
                {lowStockCartridges[0].current_stock} pills remaining. Marcus has been notified.
              </span>
            </div>
          </div>
        )}
      </div>

      {/* 2. Hero Section: Current Action Required OR Next Upcoming Dose */}
      {currentDose && !isFinished && (
        <div className="space-y-2">
          <div className="flex items-center justify-between px-1">
            <h2 className="text-xs font-black uppercase tracking-wider text-[#4F6267]">
              {isCurrentDue ? 'Current Action Required' : 'Next Scheduled Dose (Upcoming)'}
            </h2>
            <span
              className={`text-xs font-bold px-2 py-0.5 rounded-full ${
                isCurrentDue ? 'bg-amber-100 text-amber-900' : 'bg-stone-100 text-stone-600'
              }`}
            >
              {isCurrentDue ? 'Due for Intake' : `Scheduled for ${currentDose.scheduled_time_local}`}
            </span>
          </div>

          <PillCard
            dose={currentDose}
            isCurrent={true}
            isSimulated={isSimulated}
            onDispense={onDispense}
            onSimulateDispense={onSimulateDispense}
            onCancelDispense={onCancelDispense}
            onPickup={onPickup}
          />
        </div>
      )}

      {/* 3. Chronological Daily Timeline */}
      <div className="space-y-3">
        <div className="flex items-center justify-between px-1">
          <h2 className="text-xs font-black uppercase tracking-wider text-[#4F6267]">
            Today's Schedule & Occurrences
          </h2>
          <span className="text-xs text-[#4F6267] font-medium">{doses.length} total doses</span>
        </div>

        {doses.length === 0 ? (
          <div className="p-8 text-center bg-white rounded-3xl border border-[#E5E4E0] text-[#4F6267]">
            <Clock className="w-8 h-8 mx-auto text-stone-300 mb-2" />
            <p className="text-sm font-semibold">No doses scheduled for today.</p>
          </div>
        ) : (
          <div className="space-y-3">
            {doses.map((dose) => (
              <PillCard
                key={dose.id}
                dose={dose}
                isCurrent={currentDose?.id === dose.id}
                isSimulated={isSimulated}
                onDispense={onDispense}
                onSimulateDispense={onSimulateDispense}
                onCancelDispense={onCancelDispense}
                onPickup={onPickup}
              />
            ))}
          </div>
        )}
      </div>

      {/* Helpful Assist Banner */}
      <div className="p-5 bg-[#EAF2EC] border border-[#c1dbca] rounded-3xl flex items-center justify-between gap-4">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-2xl bg-[#145A4A] text-white flex items-center justify-center shrink-0">
            <Heart className="w-5 h-5 fill-white" />
          </div>
          <div>
            <h3 className="text-sm font-bold text-[#17313A]">Need help with your medication?</h3>
            <p className="text-xs text-[#4F6267]">
              Marcus Vance (Caregiver) is connected and monitoring your medication schedule.
            </p>
          </div>
        </div>
      </div>
    </div>
  );
};
