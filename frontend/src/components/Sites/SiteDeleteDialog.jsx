import React, { useEffect } from 'react';
import { X, AlertTriangle } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { trackActivity } from '@/utils/analytics';

export default function SiteDeleteDialog({ isOpen, onClose, onConfirm, siteName, isDeleting }) {
  // Track when the dialog opens
  useEffect(() => {
    if (isOpen) {
      trackActivity('modal_open', '/sites/delete', {
        modal: 'delete_site_dialog',
        site: siteName,
      });
    }
  }, [isOpen, siteName]);

  if (!isOpen) return null;

  const handleClose = () => {
    trackActivity('modal_close', '/sites/delete', {
      modal: 'delete_site_dialog',
      site: siteName,
    });

    onClose();
  };

  const handleConfirm = async () => {
    trackActivity('delete_confirm_click', '/sites/delete', {
      site: siteName,
    });

    try {
      await onConfirm();

      trackActivity('site_deleted', '/sites/delete', {
        site: siteName,
      });
    } catch (err) {
      trackActivity('delete_failed', '/sites/delete', {
        site: siteName,
        error: err?.message || 'Delete failed',
      });

      throw err; // bubble up if parent handles it
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 backdrop-blur-sm">
      <div className="w-full max-w-md rounded-lg bg-[#141a24] p-6 shadow-lg border border-[#1f2735] animate-in fade-in zoom-in-95 duration-200">
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-lg font-semibold text-white flex items-center gap-2">
            <AlertTriangle className="h-5 w-5 text-red-500" />
            Delete Site
          </h2>
          <button
            onClick={handleClose}
            className="text-gray-400 hover:text-white transition-colors"
          >
            <X className="h-5 w-5" />
          </button>
        </div>

        <p className="text-gray-300 mb-6">
          Are you sure you want to delete{' '}
          <span className="font-medium text-white">"{siteName}"</span>? This action cannot be undone
          and will remove all associated devices and data.
        </p>

        <div className="flex justify-end gap-3">
          <Button
            variant="outline"
            onClick={handleClose}
            disabled={isDeleting}
            className="border-[#1f2735] bg-transparent text-gray-300 hover:bg-[#1f2735] hover:text-white"
          >
            Cancel
          </Button>
          <Button
            variant="destructive"
            onClick={handleConfirm}
            disabled={isDeleting}
            className="bg-transparent text-red-500 border border-red-500 hover:bg-red-500/10"
          >
            {isDeleting ? 'Deleting...' : 'Delete Site'}
          </Button>
        </div>
      </div>
    </div>
  );
}
