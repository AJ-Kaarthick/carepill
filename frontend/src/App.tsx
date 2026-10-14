import React, { useState, useEffect, useCallback } from 'react';
import { Navbar } from './components/Navbar';
import { BottomNav, TabType } from './components/BottomNav';
import { HardwareSimulator } from './components/HardwareSimulator';
import { PatientDashboard } from './pages/PatientDashboard';
import { MedicinesPage } from './pages/MedicinesPage';
import { CartridgesPage } from './pages/CartridgesPage';
import { CaregiverPage } from './pages/CaregiverPage';
import { DevicePage } from './pages/DevicePage';
import { api } from './services/api';
import {
  DoseOccurrence,
  Medication,
  Cartridge,
  Prescription,
  CaregiverAlert,
  InventoryTransaction,
  SimulatorState,
  DeviceConnectivity
} from './types';

export function App() {
  const [currentTab, setCurrentTab] = useState<TabType>('today');
  const [currentRole, setCurrentRole] = useState<'patient' | 'caregiver'>('patient');
  const [isSimulatorOpen, setIsSimulatorOpen] = useState(false);

  // Data states
  const [doses, setDoses] = useState<DoseOccurrence[]>([]);
  const [currentDose, setCurrentDose] = useState<DoseOccurrence | null>(null);
  const [medications, setMedications] = useState<Medication[]>([]);
  const [cartridges, setCartridges] = useState<Cartridge[]>([]);
  const [prescriptions, setPrescriptions] = useState<Prescription[]>([]);
  const [alerts, setAlerts] = useState<CaregiverAlert[]>([]);
  const [transactions, setTransactions] = useState<InventoryTransaction[]>([]);
  const [simulatorState, setSimulatorState] = useState<SimulatorState | null>(null);
  const [connectivity, setConnectivity] = useState<DeviceConnectivity | null>(null);
  const [loading, setLoading] = useState(true);

  const fetchAllData = useCallback(async () => {
    try {
      const [
        dosesData,
        currDoseData,
        medsData,
        cartsData,
        rxData,
        alertsData,
        txData,
        simState,
        connData
      ] = await Promise.all([
        api.getTodayDoses(),
        api.getCurrentDose(),
        api.getMedications(),
        api.getCartridges(),
        api.getPrescriptions(),
        api.getCaregiverAlerts(),
        api.getInventoryTransactions(),
        api.getSimulatorState(),
        api.getConnectivity()
      ]);

      setDoses(dosesData);
      setCurrentDose(currDoseData);
      setMedications(medsData);
      setCartridges(cartsData);
      setPrescriptions(rxData);
      setAlerts(alertsData);
      setTransactions(txData);
      setSimulatorState(simState);
      setConnectivity(connData);
    } catch (err) {
      console.error('Failed to load application data:', err);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchAllData();
    // Poll telemetry and dose state every 3 seconds
    const interval = setInterval(fetchAllData, 3000);
    return () => clearInterval(interval);
  }, [fetchAllData]);

  // When role changes, switch view context appropriately
  const handleRoleChange = (role: 'patient' | 'caregiver') => {
    setCurrentRole(role);
    if (role === 'caregiver') {
      setCurrentTab('caregiver');
    } else {
      setCurrentTab('today');
    }
  };

  // Enforce patient interface separation: patient can only access 'today' and 'medicines'
  useEffect(() => {
    if (currentRole === 'patient' && currentTab !== 'today' && currentTab !== 'medicines') {
      setCurrentTab('today');
    }
  }, [currentRole, currentTab]);

  const handleToggleOperatingMode = async () => {
    try {
      const nextMode = connectivity?.is_simulated ? 'physical' : 'simulated';
      const updated = await api.setDeviceMode(nextMode);
      setConnectivity(updated);
      await fetchAllData();
    } catch (err: any) {
      alert(err.message || 'Failed to toggle device mode');
    }
  };

  // Dose Actions
  const handleDispense = async (doseId: string) => {
    try {
      await api.triggerDispense(doseId);
      await fetchAllData();
    } catch (err: any) {
      alert(err.message);
    }
  };

  const handleSimulateDispense = async (doseId: string) => {
    try {
      await api.simulateDispense(doseId);
      await fetchAllData();
    } catch (err: any) {
      alert(err.message);
    }
  };

  const handleCancelDispense = async (doseId: string) => {
    try {
      await api.cancelDispense(doseId);
      await fetchAllData();
    } catch (err: any) {
      alert(err.message);
    }
  };

  const handlePickup = async (doseId: string) => {
    try {
      await api.recordPickup(doseId, true);
      await fetchAllData();
    } catch (err: any) {
      alert(err.message);
    }
  };

  const handleManualConfirm = async (doseId: string) => {
    try {
      await api.manualConfirmDose(doseId, currentRole === 'patient' ? 'Eleanor Vance (Patient)' : 'Marcus Vance (Caregiver)');
      await fetchAllData();
    } catch (err: any) {
      alert(err.message);
    }
  };

  const unacknowledgedCount = alerts.filter((a) => !a.acknowledged).length;

  return (
    <div className="min-h-screen bg-[#F7F6F1] flex flex-col text-[#17313A]">
      {/* Top Header */}
      <Navbar
        currentRole={currentRole}
        onRoleChange={handleRoleChange}
      />

      {/* Main Page Content */}
      <main className="flex-1 max-w-4xl w-full mx-auto p-4 sm:p-6">
        {loading ? (
          <div className="py-20 text-center text-[#4F6267]">
            <div className="w-8 h-8 border-3 border-[#145A4A] border-t-transparent rounded-full animate-spin mx-auto mb-3" />
            <p className="text-sm font-semibold">Connecting to Smart Pill Dispenser...</p>
          </div>
        ) : (
          <>
            {currentTab === 'today' && (
              <PatientDashboard
                doses={doses}
                currentDose={currentDose}
                cartridges={cartridges}
                isSimulated={connectivity?.is_simulated ?? true}
                onDispense={handleDispense}
                onSimulateDispense={handleSimulateDispense}
                onCancelDispense={handleCancelDispense}
                onPickup={handlePickup}
                onManualConfirm={handleManualConfirm}
                onOpenSimulator={() => setIsSimulatorOpen(true)}
              />
            )}

            {(currentTab === 'medicines' || currentTab === 'prescriptions') && (
              <MedicinesPage
                currentRole={currentRole}
                medications={medications}
                prescriptions={prescriptions}
                onRefresh={fetchAllData}
              />
            )}

            {currentTab === 'cartridges' && (
              <CartridgesPage
                cartridges={cartridges}
                transactions={transactions}
                medications={medications}
                onRefresh={fetchAllData}
              />
            )}

            {currentTab === 'caregiver' && (
              <CaregiverPage
                alerts={alerts}
                doses={doses}
                cartridges={cartridges}
                onRefresh={fetchAllData}
              />
            )}

            {currentTab === 'device' && (
              <DevicePage
                simulatorState={simulatorState}
                connectivity={connectivity}
                cartridges={cartridges}
                onOpenSimulator={() => setIsSimulatorOpen(true)}
                onToggleOperatingMode={handleToggleOperatingMode}
              />
            )}
          </>
        )}
      </main>

      {/* Mobile Bottom Navigation */}
      <BottomNav
        currentRole={currentRole}
        currentTab={currentTab}
        onTabChange={setCurrentTab}
        unacknowledgedAlertsCount={unacknowledgedCount}
      />

      {/* Hardware Simulator Drawer */}
      <HardwareSimulator
        isOpen={isSimulatorOpen}
        onClose={() => setIsSimulatorOpen(false)}
        simulatorState={simulatorState}
        onRefresh={fetchAllData}
      />
    </div>
  );
}

export default App;
