import React from 'react';
import { Ban, Loader2 } from 'lucide-react';
import { Button } from '@/components/ui/button';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogFooter,
  DialogTitle,
} from '@/components/ui/dialog';
import { formatCommandType } from '@/utils/commandLifecycle';

export default function CancelCommandDialog({
  command,
  isOpen,
  onClose,
  onConfirm,
  isCancelling = false,
  error = null,
}) {
  return (
    <Dialog open={isOpen} onOpenChange={(open) => !open && onClose()}>
      <DialogContent className="max-w-md bg-[#06181c] border-[#1f2735] text-white">
        <DialogHeader>
          <div className="flex items-start gap-3">
            <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg border border-red-500/30 bg-red-500/10">
              <Ban className="h-5 w-5 text-red-400" />
            </span>
            <div>
              <DialogTitle className="text-lg font-semibold text-white">Cancel Command</DialogTitle>
              <DialogDescription className="mt-1.5 text-sm text-slate-400">
                Terminate this in-flight command so it no longer blocks the queue. This cannot be
                undone.
              </DialogDescription>
            </div>
          </div>
        </DialogHeader>

        {command && (
          <div className="my-2 rounded-lg border border-[#1f2735] bg-[#0b2024]/50 p-3 text-sm">
            <div className="flex items-center justify-between gap-4">
              <span className="text-slate-500">Type</span>
              <span className="text-slate-200">{formatCommandType(command.command_type)}</span>
            </div>
            <div className="mt-1.5 flex items-center justify-between gap-4">
              <span className="text-slate-500">Command ID</span>
              <span className="font-mono text-[11px] text-teal-300 break-all text-right">
                {command.command_id}
              </span>
            </div>
            {command.created_at && (
              <div className="mt-1.5 flex items-center justify-between gap-4">
                <span className="text-slate-500">Queued</span>
                <span className="text-slate-200">
                  {new Date(command.created_at).toLocaleString()}
                </span>
              </div>
            )}
          </div>
        )}

        {error && (
          <div className="rounded-lg border border-red-500/40 bg-red-500/10 px-3 py-2 text-xs text-red-300">
            {error}
          </div>
        )}

        <DialogFooter>
          <Button
            variant="outline"
            onClick={onClose}
            disabled={isCancelling}
            className="border-gray-700 bg-transparent text-gray-300 hover:text-white hover:bg-gray-800"
          >
            Keep Command
          </Button>
          <Button
            className="bg-red-600 hover:bg-red-700 text-white"
            onClick={onConfirm}
            disabled={isCancelling}
          >
            {isCancelling ? (
              <Loader2 className="h-4 w-4 mr-2 animate-spin" />
            ) : (
              <Ban className="h-4 w-4 mr-2" />
            )}
            {isCancelling ? 'Cancelling...' : 'Cancel Command'}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
