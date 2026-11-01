import React from 'react';
import { ShieldAlert, CheckCircle, XCircle, PlayCircle, Clock, AlertTriangle } from 'lucide-react';
import { Button } from '@/components/ui/button';

const STATUS_META = {
  proposed: { label: 'Proposed', color: 'bg-gray-500/10 text-gray-400', icon: Clock },
  pending_approval: {
    label: 'Pending Approval',
    color: 'bg-yellow-500/10 text-yellow-400',
    icon: Clock,
  },
  blocked: { label: 'Blocked', color: 'bg-red-500/10 text-red-400', icon: AlertTriangle },
  approved: { label: 'Approved', color: 'bg-green-500/10 text-green-400', icon: CheckCircle },
  rejected: { label: 'Rejected', color: 'bg-red-500/10 text-red-400', icon: XCircle },
  executing: { label: 'Executing', color: 'bg-blue-500/10 text-blue-400', icon: PlayCircle },
  succeeded: { label: 'Succeeded', color: 'bg-green-500/10 text-green-400', icon: CheckCircle },
  failed: { label: 'Failed', color: 'bg-red-500/10 text-red-400', icon: XCircle },
  rolled_back: {
    label: 'Rolled Back',
    color: 'bg-purple-500/10 text-purple-400',
    icon: AlertTriangle,
  },
  expired: { label: 'Expired', color: 'bg-gray-500/10 text-gray-400', icon: Clock },
};

/**
 * Compact proposal card shown inline in a conversation turn.
 * Reuses the established AI proposal status vocabulary; links to the
 * full review page for approve/reject/execute actions.
 */
export default function ProposalCard({ proposal, onReview }) {
  if (!proposal) return null;
  const meta = STATUS_META[proposal.status] || STATUS_META.proposed;
  const Icon = meta.icon;
  const steps = proposal.steps || [];

  return (
    <div className="mt-2 rounded-lg border border-indigo-200 dark:border-indigo-900 bg-indigo-50/40 dark:bg-indigo-950/20 p-3 text-xs">
      <div className="flex items-center justify-between gap-2 mb-2">
        <div className="flex items-center gap-1.5 font-semibold text-indigo-700 dark:text-indigo-300">
          <ShieldAlert className="w-3.5 h-3.5" />
          <span>Proposed action</span>
        </div>
        <span
          className={`inline-flex items-center gap-1 rounded-full px-2 py-0.5 font-medium ${meta.color}`}
        >
          <Icon className="w-3 h-3" />
          {meta.label}
        </span>
      </div>

      {proposal.rationale && (
        <p className="text-gray-600 dark:text-gray-300 mb-2">{proposal.rationale}</p>
      )}

      {proposal.risk_tier && (
        <p className="text-gray-500 dark:text-gray-400 mb-2">
          Risk: <span className="font-medium">{proposal.risk_tier}</span>
          {proposal.reversible ? ' · reversible' : ' · not reversible'}
        </p>
      )}

      {steps.length > 0 && (
        <ul className="space-y-1 mb-2">
          {steps.map((s, i) => (
            <li key={i} className="flex items-center gap-1.5 text-gray-600 dark:text-gray-300">
              <span className="font-mono text-[10px] text-gray-400">#{s.seq ?? i}</span>
              <span className="font-medium">{s.action}</span>
              {s.target_device_id && <span className="text-gray-400">→ {s.target_device_id}</span>}
            </li>
          ))}
        </ul>
      )}

      {proposal.plan_id && (
        <Button
          variant="outline"
          size="sm"
          onClick={() =>
            onReview ? onReview(proposal.plan_id) : window.location.assign('/ai-proposals')
          }
          className="h-7 text-xs"
        >
          Review on AI Proposals page
        </Button>
      )}
    </div>
  );
}
