import React from 'react';
import { Shield, Heart, User } from 'lucide-react';

interface NavbarProps {
  currentRole: 'patient' | 'caregiver';
  onRoleChange: (role: 'patient' | 'caregiver') => void;
}

export const Navbar: React.FC<NavbarProps> = ({
  currentRole,
  onRoleChange
}) => {
  return (
    <header className="sticky top-0 z-30 bg-[#FFFFFF] border-b border-[#E5E4E0] shadow-xs">
      <div className="max-w-4xl mx-auto px-4 py-3 flex items-center justify-between">
        {/* Brand & Identity */}
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-2xl bg-[#145A4A] flex items-center justify-center text-white shadow-xs">
            <Heart className="w-6 h-6 fill-white" />
          </div>
          <div>
            <span className="font-black text-xl text-[#17313A] tracking-tight">CarePill</span>
            <p className="text-xs text-[#4F6267] hidden sm:block">Smart Medication Guardian</p>
          </div>
        </div>

        {/* Temporary Role Switcher for Development & Demonstration */}
        <div className="flex items-center bg-[#F7F6F1] p-1 rounded-2xl border border-[#E5E4E0]">
          <button
            onClick={() => onRoleChange('patient')}
            className={`px-3.5 py-1.5 rounded-xl text-xs font-bold flex items-center gap-1.5 transition-all cursor-pointer ${
              currentRole === 'patient'
                ? 'bg-[#145A4A] text-white shadow-xs'
                : 'text-[#4F6267] hover:text-[#17313A]'
            }`}
          >
            <User className="w-3.5 h-3.5" />
            <span>Patient</span>
          </button>
          <button
            onClick={() => onRoleChange('caregiver')}
            className={`px-3.5 py-1.5 rounded-xl text-xs font-bold flex items-center gap-1.5 transition-all cursor-pointer ${
              currentRole === 'caregiver'
                ? 'bg-[#145A4A] text-white shadow-xs'
                : 'text-[#4F6267] hover:text-[#17313A]'
            }`}
          >
            <Shield className="w-3.5 h-3.5" />
            <span>Caregiver</span>
          </button>
        </div>
      </div>
    </header>
  );
};
