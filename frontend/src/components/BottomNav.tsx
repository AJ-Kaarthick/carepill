import React from 'react';
import { Calendar, Pill, Disc, Shield, Cpu, FileText, LucideIcon } from 'lucide-react';

export type TabType = 'today' | 'medicines' | 'cartridges' | 'caregiver' | 'prescriptions' | 'device';

interface BottomNavProps {
  currentRole: 'patient' | 'caregiver';
  currentTab: TabType;
  onTabChange: (tab: TabType) => void;
  unacknowledgedAlertsCount?: number;
}

interface TabItem {
  id: TabType;
  label: string;
  icon: LucideIcon;
  badge?: number;
}

export const BottomNav: React.FC<BottomNavProps> = ({
  currentRole,
  currentTab,
  onTabChange,
  unacknowledgedAlertsCount = 0
}) => {
  // Role-specific navigation tabs: Patient has ONLY Today and My Medicines
  const patientTabs: TabItem[] = [
    { id: 'today', label: 'Today', icon: Calendar },
    { id: 'medicines', label: 'My Medicines', icon: Pill }
  ];

  const caregiverTabs: TabItem[] = [
    { id: 'caregiver', label: 'Supervision', icon: Shield, badge: unacknowledgedAlertsCount },
    { id: 'prescriptions', label: 'Prescriptions', icon: FileText },
    { id: 'cartridges', label: 'Cartridges', icon: Disc },
    { id: 'device', label: 'Device & Setup', icon: Cpu }
  ];

  const tabs = currentRole === 'patient' ? patientTabs : caregiverTabs;

  return (
    <nav className="fixed bottom-0 left-0 right-0 z-30 bg-[#FFFFFF] border-t border-[#E5E4E0] shadow-md pb-safe">
      <div className="max-w-xl mx-auto flex items-center justify-around px-2 py-1">
        {tabs.map((tab) => {
          const Icon = tab.icon;
          const isActive = currentTab === tab.id;
          return (
            <button
              key={tab.id}
              onClick={() => onTabChange(tab.id)}
              className={`relative flex flex-col items-center justify-center flex-1 py-2 px-1 min-h-[58px] rounded-xl transition-all cursor-pointer ${
                isActive
                  ? 'text-[#145A4A] font-bold'
                  : 'text-[#4F6267] hover:text-[#17313A] font-medium'
              }`}
            >
              <div className="relative">
                <Icon className={`w-6 h-6 transition-transform ${isActive ? 'scale-110 stroke-[2.5]' : 'stroke-2'}`} />
                {tab.badge && tab.badge > 0 ? (
                  <span className="absolute -top-1.5 -right-2 px-1.5 py-0.2 text-[10px] font-black text-white bg-[#B91C1C] rounded-full min-w-4 text-center">
                    {tab.badge}
                  </span>
                ) : null}
              </div>
              <span className={`text-[12px] mt-1 ${isActive ? 'font-bold' : 'font-medium'}`}>
                {tab.label}
              </span>
              {isActive && (
                <span className="absolute bottom-1 w-6 h-1 rounded-full bg-[#145A4A]" />
              )}
            </button>
          );
        })}
      </div>
    </nav>
  );
};
