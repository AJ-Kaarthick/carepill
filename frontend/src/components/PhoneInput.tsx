import React, { useState, useEffect } from 'react';
import { Phone, CheckCircle2, AlertCircle } from 'lucide-react';

export interface CountryCode {
  name: string;
  code: string;
  flag: string;
  digits: number;
}

export const COUNTRIES: CountryCode[] = [
  { name: 'India', code: '+91', flag: '🇮🇳', digits: 10 },
  { name: 'United States', code: '+1', flag: '🇺🇸', digits: 10 },
  { name: 'United Kingdom', code: '+44', flag: '🇬🇧', digits: 10 },
  { name: 'Australia', code: '+61', flag: '🇦🇺', digits: 9 },
  { name: 'United Arab Emirates', code: '+971', flag: '🇦🇪', digits: 9 },
  { name: 'Singapore', code: '+65', flag: '🇸🇬', digits: 8 },
  { name: 'Germany', code: '+49', flag: '🇩🇪', digits: 10 },
  { name: 'Canada', code: '+1', flag: '🇨🇦', digits: 10 },
];

interface PhoneInputProps {
  value: string;
  onChange: (value: string, isValid: boolean) => void;
  label: string;
  helperText?: string;
  defaultCountryCode?: string;
  placeholder?: string;
  disabled?: boolean;
}

export const PhoneInput: React.FC<PhoneInputProps> = ({
  value,
  onChange,
  label,
  helperText,
  defaultCountryCode = '+91',
  placeholder = '98765 43210',
  disabled = false
}) => {
  const [selectedCountry, setSelectedCountry] = useState<CountryCode>(() => {
    // Detect country from initial value if present
    if (value) {
      for (const country of COUNTRIES) {
        if (value.startsWith(country.code)) {
          return country;
        }
      }
    }
    return COUNTRIES.find((c) => c.code === defaultCountryCode) || COUNTRIES[0];
  });

  const extractSubscriberNumber = (val: string, country: CountryCode): string => {
    if (!val) return '';
    let raw = val.trim();
    if (raw.startsWith(country.code)) {
      raw = raw.slice(country.code.length).trim();
    }
    return raw;
  };

  const [subscriberNumber, setSubscriberNumber] = useState<string>(() =>
    extractSubscriberNumber(value, selectedCountry)
  );

  useEffect(() => {
    // When external value changes, sync subscriberNumber
    setSubscriberNumber(extractSubscriberNumber(value, selectedCountry));
  }, [value, selectedCountry]);

  const handleCountryChange = (e: React.ChangeEvent<HTMLSelectElement>) => {
    const code = e.target.value;
    const country = COUNTRIES.find((c) => c.code === code) || COUNTRIES[0];
    setSelectedCountry(country);
    triggerChange(subscriberNumber, country);
  };

  const handleSubscriberChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    let input = e.target.value;

    // Reject alphabetic characters
    if (/[a-zA-Z]/.test(input)) {
      return;
    }

    // Strip out leading country code if pasted
    for (const c of COUNTRIES) {
      if (input.startsWith(c.code)) {
        input = input.slice(c.code.length).trim();
        setSelectedCountry(c);
        triggerChange(input, c);
        return;
      }
    }

    // Clean internal formatting (allow spaces and dashes as user types, strip illegal symbols)
    const cleaned = input.replace(/[^0-9\s\-]/g, '');
    setSubscriberNumber(cleaned);
    triggerChange(cleaned, selectedCountry);
  };

  const triggerChange = (subNum: string, country: CountryCode) => {
    const digitsOnly = subNum.replace(/\D/g, '');
    const isValid = digitsOnly.length >= 7 && digitsOnly.length <= 15;
    const formatted = subNum.trim() ? `${country.code} ${subNum.trim()}` : '';
    onChange(formatted, isValid);
  };

  const digitsOnly = subscriberNumber.replace(/\D/g, '');
  const isLengthValid = digitsOnly.length >= 7 && digitsOnly.length <= 15;
  const isInputNonEmpty = digitsOnly.length > 0;

  return (
    <div className="space-y-1.5">
      <div className="flex items-center justify-between">
        <label className="block text-xs font-bold text-[#17313A]">{label}</label>
        {isInputNonEmpty && (
          <span className="text-[11px] flex items-center gap-1 font-semibold">
            {isLengthValid ? (
              <span className="text-emerald-700 flex items-center gap-0.5">
                <CheckCircle2 className="w-3.5 h-3.5" /> Valid international format
              </span>
            ) : (
              <span className="text-amber-700 flex items-center gap-0.5">
                <AlertCircle className="w-3.5 h-3.5" /> Expecting {selectedCountry.digits} digits
              </span>
            )}
          </span>
        )}
      </div>

      <div className="flex rounded-xl border border-stone-300 overflow-hidden focus-within:ring-2 focus-within:ring-[#145A4A] focus-within:border-transparent transition-all bg-white shadow-2xs">
        {/* Country Code Dropdown */}
        <div className="bg-stone-50 border-r border-stone-200 px-2 flex items-center shrink-0">
          <span className="text-base mr-1">{selectedCountry.flag}</span>
          <select
            value={selectedCountry.code}
            onChange={handleCountryChange}
            disabled={disabled}
            className="bg-transparent text-xs font-bold text-[#17313A] focus:outline-none cursor-pointer py-2.5 pr-1"
          >
            {COUNTRIES.map((c, idx) => (
              <option key={`${c.code}-${idx}`} value={c.code}>
                {c.code} ({c.name})
              </option>
            ))}
          </select>
        </div>

        {/* Subscriber Phone Number Input */}
        <div className="relative flex-1 flex items-center">
          <Phone className="w-4 h-4 text-[#4F6267] absolute left-3 pointer-events-none" />
          <input
            type="tel"
            inputMode="numeric"
            value={subscriberNumber}
            onChange={handleSubscriberChange}
            disabled={disabled}
            placeholder={placeholder}
            className="w-full pl-9 pr-3.5 py-2.5 font-medium text-sm text-[#17313A] placeholder-stone-400 focus:outline-none bg-transparent"
          />
        </div>
      </div>

      {helperText && <p className="text-[11px] text-[#4F6267] mt-0.5">{helperText}</p>}
    </div>
  );
};
