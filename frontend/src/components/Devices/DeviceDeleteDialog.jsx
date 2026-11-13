import React, { useEffect, useState } from 'react';
import { X, AlertTriangle, Trash2 } from 'lucide-react';
import { Button } from '@/components/ui/button';

export default function DeviceDeleteDialog({ isOpen, onClose, onConfirm, deviceName, isDeleting }) {
  const [purgeConfirmText, setPurgeConfirmText] = useState('');

  useEffect(() => {
    if (isOpen) {
      setPurgeConfirmText('');
    }
  }, [isOpen, deviceName]);

  if (!isOpen) return null;

  const handleConfirm = async () => {
    await onConfirm();
  };

  const canConfirm = purgeConfirmText === deviceName;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 backdrop-blur-sm">
      <div className="w-full max-w-md rounded-lg border border-border bg-card p-6 shadow-lg animate-in fade-in zoom-in-95 duration-200">
        <div className="flex items-center justify-between mb-4">
          <div className="flex items-center gap-2 text-destructive">
            <AlertTriangle className="h-5 w-5" />
            <h3 className="text-lg font-semibold">Purge Device</h3>
          </div>
          <button onClick={onClose} className="text-gray-400 hover:text-white transition-colors">
            <X className="h-5 w-5" />
          </button>
        </div>

        <div className="flex items-start gap-3 p-4 rounded-lg border border-red-500/40 bg-red-500/10 mb-5">
          <Trash2 className="h-5 w-5 mt-0.5 text-red-400" />
          <p className="text-sm text-gray-300">
            Permanently delete <span className="font-semibold text-white">{deviceName}</span> and
            ALL associated data (telemetry, commands, history). This action cannot be undone. To
            hide the device but keep its history, unpair it from the device page instead.
          </p>
        </div>

        <div className="mb-5">
          <p className="text-sm text-red-400 mb-2">
            Type <span className="font-medium text-white">&quot;{deviceName}&quot;</span> to confirm
            permanent deletion.
          </p>
          <input
            type="text"
            value={purgeConfirmText}
            onChange={(e) => setPurgeConfirmText(e.target.value)}
            placeholder={deviceName}
            className="w-full h-9 rounded-md border border-red-500/50 bg-transparent px-3 py-1 text-sm text-white placeholder:text-gray-500 focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-red-500"
          />
        </div>

        <div className="flex justify-end gap-3">
          <Button
            variant="outline"
            onClick={onClose}
            disabled={isDeleting}
            className="border-gray-600 text-gray-300 hover:bg-gray-800 hover:text-white"
          >
            Cancel
          </Button>
          <Button
            variant="destructive"
            onClick={handleConfirm}
            disabled={isDeleting || !canConfirm}
            className="bg-red-600 hover:bg-red-700 text-white"
          >
            {isDeleting ? 'Purging...' : 'Purge Device'}
          </Button>
        </div>
      </div>
    </div>
  );
}
