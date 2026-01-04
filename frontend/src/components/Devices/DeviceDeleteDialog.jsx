import React, { useEffect } from 'react';
import { X, AlertTriangle } from 'lucide-react';
import { Button } from '@/components/ui/button';
// import { trackActivity } from '@/utils/analytics'; // Uncomment if analytics is needed

export default function DeviceDeleteDialog({ isOpen, onClose, onConfirm, deviceName, isDeleting }) {
  // Track when the dialog opens
  useEffect(() => {
    if (isOpen) {
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

    await onConfirm();

    // trackActivity('device_deleted', '/devices/delete', {
    //   device: deviceName,
    // });
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 backdrop-blur-sm">
      <div className="w-full max-w-md rounded-lg border border-border bg-card p-6 shadow-lg animate-in fade-in zoom-in-95 duration-200">
        <div className="flex items-center justify-between mb-4">
          <div className="flex items-center gap-2 text-destructive">
            <AlertTriangle className="h-5 w-5" />
            <h3 className="text-lg font-semibold">Delete Device</h3>
          </div>
          <button
            onClick={handleClose}
            className="text-gray-400 hover:text-white transition-colors"
          >
            <X className="h-5 w-5" />
          </button>
        </div>

        <div className="mb-6">
          <p className="text-gray-300 mb-2">
            Are you sure you want to delete{' '}
            <span className="font-semibold text-white">{deviceName}</span>?
          </p>
          <p className="text-sm text-gray-400">
            This action cannot be undone. All data associated with this device will be permanently
            removed.
          </p>
        </div>

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
            disabled={isDeleting}
            className="bg-red-600 hover:bg-red-700 text-white"
          >
            {isDeleting ? 'Deleting...' : 'Delete Device'}
          </Button>
        </div>
      </div>
    </div>
  );
}
