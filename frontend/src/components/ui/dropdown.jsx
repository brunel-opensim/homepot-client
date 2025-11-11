import React from 'react';

/**
 * Reusable Dropdown component
 * Props:
 *  - label?: string (optional)
 *  - options: Array<{ label: string, value: string }>
 *  - value: string
 *  - onChange: function(e)
 *  - placeholder?: string
 */
const Dropdown = ({ label, options = [], value, onChange, placeholder = 'Select an option' }) => {
  return (
    <div className="relative w-full">
      {label && <label className="block text-sm text-gray-300 mb-2">{label}</label>}
      <select
        value={value}
        onChange={onChange}
        className="w-full px-4 py-4 pr-10 bg-gray-800/50 border border-gray-600 rounded-lg text-white focus:outline-none focus:border-teal-500 focus:ring-1 focus:ring-teal-500 transition-all duration-200 appearance-none"
      >
        <option value="" disabled>
          {placeholder}
        </option>
        {options.map((opt) => (
          <option key={opt.value} value={opt.value}>
            {opt.label}
          </option>
        ))}
      </select>

      {/* Dropdown arrow icon */}
      <svg
        className="absolute right-3 top-1/2 -translate-y-1/2 h-5 w-5 text-gray-400 pointer-events-none"
        xmlns="http://www.w3.org/2000/svg"
        fill="none"
        viewBox="0 0 24 24"
        stroke="currentColor"
      >
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
      </svg>
    </div>
  );
};

export default Dropdown;
