import React from 'react';

const STATUS_META = {
  proposed: { label: 'Proposed', color: 'bg-gray-500/10 text-gray-400' },
  pending_approval: { label: 'Pending Approval', color: 'bg-yellow-500/10 text-yellow-400' },
  blocked: { label: 'Blocked', color: 'bg-red-500/10 text-red-400' },
  approved: { label: 'Approved', color: 'bg-green-500/10 text-green-400' },
  rejected: { label: 'Rejected', color: 'bg-red-500/10 text-red-400' },
  executing: { label: 'Executing', color: 'bg-blue-500/10 text-blue-400' },
  succeeded: { label: 'Succeeded', color: 'bg-green-500/10 text-green-400' },
  failed: { label: 'Failed', color: 'bg-red-500/10 text-red-400' },
  rolled_back: { label: 'Rolled Back', color: 'bg-purple-500/10 text-purple-400' },
  expired: { label: 'Expired', color: 'bg-gray-500/10 text-gray-400' },
  // Per-step statuses (Phase A dependency-aware plans).
  pending: { label: 'Pending', color: 'bg-gray-500/10 text-gray-400' },
  queued: { label: 'Queued', color: 'bg-blue-500/10 text-blue-400' },
  running: { label: 'Running', color: 'bg-blue-500/10 text-blue-400' },
  done: { label: 'Done', color: 'bg-green-500/10 text-green-400' },
  skipped: { label: 'Skipped', color: 'bg-gray-500/10 text-gray-400' },
  awaiting_approval: {
    label: 'Awaiting Approval',
    color: 'bg-yellow-500/10 text-yellow-400',
  },
  deferred: { label: 'Deferred', color: 'bg-orange-500/10 text-orange-400' },
};

export default function AIStatusBadge({ status }) {
  const meta = STATUS_META[status] || STATUS_META.proposed;
  return (
    <span
      className={`inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium ${meta.color}`}
    >
      {meta.label}
    </span>
  );
}
