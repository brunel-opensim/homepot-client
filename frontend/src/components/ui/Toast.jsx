import React, { useEffect } from 'react';
import { X } from 'lucide-react';

export const Toast = ({ title, message, type = 'success', onClose }) => {
  useEffect(() => {
    const timer = setTimeout(onClose, 3000);
    return () => clearTimeout(timer);
  }, [onClose]);

  return (
    <div
      className={`fixed top-6 right-6 z-50 px-4 py-3 rounded-lg shadow-lg border flex items-start gap-3 animate-in slide-in-from-right-5 duration-300 ${
        type === 'success'
          ? 'bg-[#062125] border-teal-500/50 text-teal-100'
          : 'bg-[#250606] border-red-500/50 text-red-100'
      }`}
    >
      <div
        className={`w-2 h-2 mt-1.5 rounded-full ${type === 'success' ? 'bg-teal-400' : 'bg-red-400'}`}
      />
      <div className="flex-1">
        {title && <div className="text-sm font-semibold mb-0.5">{title}</div>}
        <div className="text-sm font-medium opacity-90">{message}</div>
      </div>
      <button onClick={onClose} className="text-current opacity-50 hover:opacity-100">
        <X className="h-4 w-4" />
      </button>
    </div>
  );
};
