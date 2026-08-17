import React, { useEffect, useState } from 'react';
import { X, AlertTriangle, Archive, Trash2 } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { trackActivity } from '@/utils/analytics';

export default function SiteDeleteDialog({ isOpen, onClose, onConfirm, siteName, isDeleting }) {
  const [mode, setMode] = useState('archive');
  const [purgeConfirmText, setPurgeConfirmText] = useState('');

  useEffect(() => {
    if (isOpen) {
      setMode('archive');
      setPurgeConfirmText('');
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
      mode,
    });

    try {
      await onConfirm(mode);

      trackActivity('site_deleted', '/sites/delete', {
        site: siteName,
        mode,
      });
    } catch (err) {
      trackActivity('delete_failed', '/sites/delete', {
        site: siteName,
        mode,
        error: err?.message || 'Delete failed',
      });

      throw err; // bubble up if parent handles it
    }
  };

  const isPurge = mode === 'purge';
  const canConfirm = !isPurge || purgeConfirmText === siteName;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 backdrop-blur-sm">
      <div className="w-full max-w-md rounded-lg bg-[#141a24] p-6 shadow-lg border border-[#1f2735] animate-in fade-in zoom-in-95 duration-200">
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-lg font-semibold text-white flex items-center gap-2">
            <AlertTriangle className="h-5 w-5 text-red-500" />
            {isPurge ? 'Purge Site' : 'Archive Site'}
          </h2>
          <button
            onClick={handleClose}
            className="text-gray-400 hover:text-white transition-colors"
          >
            <X className="h-5 w-5" />
          </button>
        </div>

        <p className="text-gray-300 mb-5">
          Choose how you want to remove <span className="font-medium text-white">"{siteName}"</span>
          .
        </p>

        <div className="space-y-3 mb-4">
          <button
            type="button"
            onClick={() => setMode('archive')}
            className={`w-full flex items-start gap-3 p-4 rounded-lg border text-left transition-colors ${
              !isPurge
                ? 'border-teal-500 bg-teal-500/10'
                : 'border-[#1f2735] bg-transparent hover:bg-[#1f2735]'
            }`}
          >
            <Archive className={`h-5 w-5 mt-0.5 ${!isPurge ? 'text-teal-400' : 'text-gray-400'}`} />
            <div>
              <p className={`font-medium ${!isPurge ? 'text-teal-400' : 'text-white'}`}>Archive</p>
              <p className="text-sm text-gray-400 mt-0.5">
                Hide the site and its devices from the Dashboard. All historical data is retained
                and the site can be restored later.
              </p>
            </div>
          </button>

          <button
            type="button"
            onClick={() => setMode('purge')}
            className={`w-full flex items-start gap-3 p-4 rounded-lg border text-left transition-colors ${
              isPurge
                ? 'border-red-500 bg-red-500/10'
                : 'border-[#1f2735] bg-transparent hover:bg-[#1f2735]'
            }`}
          >
            <Trash2 className={`h-5 w-5 mt-0.5 ${isPurge ? 'text-red-400' : 'text-gray-400'}`} />
            <div>
              <p className={`font-medium ${isPurge ? 'text-red-400' : 'text-white'}`}>Purge</p>
              <p className="text-sm text-gray-400 mt-0.5">
                Permanently delete the site and ALL associated data (devices, metrics, commands,
                history). This action cannot be undone.
              </p>
            </div>
          </button>
        </div>

        {isPurge && (
          <div className="mb-5">
            <p className="text-sm text-red-400 mb-2">
              Type <span className="font-medium text-white">"{siteName}"</span> to confirm permanent
              deletion.
            </p>
            <input
              type="text"
              value={purgeConfirmText}
              onChange={(e) => setPurgeConfirmText(e.target.value)}
              placeholder={siteName}
              className="w-full h-9 rounded-md border border-red-500/50 bg-transparent px-3 py-1 text-sm text-white placeholder:text-gray-500 focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-red-500"
            />
          </div>
        )}

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
                ? 'Purge Site'
                : 'Archive Site'}
          </Button>
        </div>
      </div>
    </div>
  );
}
