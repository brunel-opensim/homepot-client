import React, { useEffect, useState } from 'react';
import { X, AlertTriangle, Archive, Trash2 } from 'lucide-react';
import { Button } from '@/components/ui/button';
// import { trackActivity } from '@/utils/analytics'; // Uncomment if analytics is needed

export default function DeviceDeleteDialog({ isOpen, onClose, onConfirm, deviceName, isDeleting }) {
  const [mode, setMode] = useState('archive');
  const [purgeConfirmText, setPurgeConfirmText] = useState('');

  // Track when the dialog opens
  useEffect(() => {
    if (isOpen) {
      setMode('archive');
      setPurgeConfirmText('');
      // trackActivity('modal_open', '/devices/delete', {
      //   modal: 'delete_device_dialog',
      //   device: deviceName,
      // });
    }
  }, [isOpen, deviceName]);

  if (!isOpen) return null;

  const handleClose = () => {
    // trackActivity('modal_close', '/devices/delete', {
    //   modal: 'delete_device_dialog',
    //   device: deviceName,
    // });

    onClose();
  };

  const handleConfirm = async () => {
    // trackActivity('delete_confirm_click', '/devices/delete', {
    //   device: deviceName,
    // });

    await onConfirm(mode);

    // trackActivity('device_deleted', '/devices/delete', {
    //   device: deviceName,
    // });
  };

  const isPurge = mode === 'purge';
  const canConfirm = !isPurge || purgeConfirmText === deviceName;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 backdrop-blur-sm">
      <div className="w-full max-w-md rounded-lg border border-border bg-card p-6 shadow-lg animate-in fade-in zoom-in-95 duration-200">
        <div className="flex items-center justify-between mb-4">
          <div className="flex items-center gap-2 text-destructive">
            <AlertTriangle className="h-5 w-5" />
            <h3 className="text-lg font-semibold">{isPurge ? 'Purge Device' : 'Archive Device'}</h3>
          </div>
          <button
            onClick={handleClose}
            className="text-gray-400 hover:text-white transition-colors"
          >
            <X className="h-5 w-5" />
          </button>
        </div>

        <p className="text-gray-300 mb-5">
          Choose how you want to remove{' '}
          <span className="font-semibold text-white">{deviceName}</span>.
        </p>

        <div className="space-y-3 mb-4">
          <button
            type="button"
            onClick={() => setMode('archive')}
            className={`w-full flex items-start gap-3 p-4 rounded-lg border text-left transition-colors ${
              !isPurge
                ? 'border-teal-500 bg-teal-500/10'
                : 'border-gray-700 bg-transparent hover:bg-gray-800'
            }`}
          >
            <Archive className={`h-5 w-5 mt-0.5 ${!isPurge ? 'text-teal-400' : 'text-gray-400'}`} />
            <div>
              <p className={`font-medium ${!isPurge ? 'text-teal-400' : 'text-white'}`}>Archive</p>
              <p className="text-sm text-gray-400 mt-0.5">
                Unpair the device and retain its historical data. The device can be re-paired or
                restored later.
              </p>
            </div>
          </button>

          <button
            type="button"
            onClick={() => setMode('purge')}
            className={`w-full flex items-start gap-3 p-4 rounded-lg border text-left transition-colors ${
              isPurge
                ? 'border-red-500 bg-red-500/10'
                : 'border-gray-700 bg-transparent hover:bg-gray-800'
            }`}
          >
            <Trash2 className={`h-5 w-5 mt-0.5 ${isPurge ? 'text-red-400' : 'text-gray-400'}`} />
            <div>
              <p className={`font-medium ${isPurge ? 'text-red-400' : 'text-white'}`}>Purge</p>
              <p className="text-sm text-gray-400 mt-0.5">
                Permanently delete the device and ALL associated data (telemetry, commands,
                history). This action cannot be undone.
              </p>
            </div>
          </button>
        </div>

        {isPurge && (
          <div className="mb-5">
            <p className="text-sm text-red-400 mb-2">
              Type <span className="font-medium text-white">"{deviceName}"</span> to confirm
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
        )}

        <div className="flex justify-end gap-3">
          <Button
            variant="outline"
            onClick={handleClose}
            disabled={isDeleting}
            className="border-gray-600 text-gray-300 hover:bg-gray-800 hover:text-white"
          >
            Cancel
          </Button>
          <Button
            variant="destructive"
            onClick={handleConfirm}
            disabled={isDeleting || !canConfirm}
            className={
              isPurge
                ? 'bg-red-600 hover:bg-red-700 text-white'
                : 'bg-transparent text-teal-400 border border-teal-500 hover:bg-teal-500/10'
            }
          >
            {isDeleting
              ? isPurge
                ? 'Purging...'
                : 'Archiving...'
              : isPurge
                ? 'Purge Device'
                : 'Archive Device'}
          </Button>
        </div>
      </div>
    </div>
  );
}
