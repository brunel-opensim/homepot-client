import React from 'react';
import { Loader2 } from 'lucide-react';
import { Button } from '@/components/ui/button';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';

export default function ConfirmDialog({
  open,
  onClose,
  onConfirm,
  title,
  description,
  confirmLabel = 'Confirm',
  confirmClassName = 'bg-teal-600 text-white hover:bg-teal-700',
  loading = false,
  showReason = false,
  reason = '',
  onReasonChange,
}) {
  return (
    <Dialog open={open} onOpenChange={(o) => !o && !loading && onClose()}>
      <DialogContent className="max-w-md bg-[#06181c] border-[#1f2735] text-white">
        <DialogHeader>
          <DialogTitle className="text-lg font-semibold text-white">{title}</DialogTitle>
          <DialogDescription className="mt-1.5 text-sm text-slate-400">
            {description}
          </DialogDescription>
        </DialogHeader>

        {showReason && (
          <textarea
            value={reason}
            onChange={(e) => onReasonChange && onReasonChange(e.target.value)}
            placeholder="Reason (optional)"
            rows={3}
            className="w-full rounded-md border border-gray-700 bg-[#1a1f2e] px-3 py-2 text-sm text-gray-200 placeholder-gray-500 focus:outline-none focus:ring-1 focus:ring-indigo-500"
          />
        )}

        <DialogFooter>
          <Button
            variant="outline"
            onClick={onClose}
            disabled={loading}
            className="border-gray-700 bg-transparent text-gray-300 hover:text-white hover:bg-gray-800"
          >
            Cancel
          </Button>
          <Button className={confirmClassName} onClick={onConfirm} disabled={loading}>
            {loading && <Loader2 className="h-4 w-4 mr-2 animate-spin" />}
            {confirmLabel}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
