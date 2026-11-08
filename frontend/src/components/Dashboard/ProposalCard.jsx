import React from 'react';
import {
  ShieldAlert,
  CheckCircle,
  XCircle,
  PlayCircle,
  Clock,
  AlertTriangle,
  ChevronDown,
  ExternalLink,
} from 'lucide-react';

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
 *
 * Always rendered for assistant turns so the "AI Proposal (if any)" section is
 * consistently visible after the response metadata. When no proposal exists the
 * body states that plainly; otherwise it reveals status, rationale, steps,
 * risk, and a clickable "Review on AI Proposals page" link.
 */
export default function ProposalCard({ proposal, onReview }) {
  const hasProposal = proposal != null;
  const meta = hasProposal ? STATUS_META[proposal.status] || STATUS_META.proposed : null;
  const Icon = meta?.icon;
  const steps = hasProposal ? proposal.steps || [] : [];

  const review =
    hasProposal && proposal.plan_id
      ? () =>
          onReview
            ? onReview(proposal.plan_id)
            : window.location.assign(`/ai-proposals?plan=${proposal.plan_id}`)
      : null;

  return (
    <details className="ai-proposal-details">
      <summary className="ai-proposal-summary">
        <span className="ai-proposal-summary-icon">
          <ShieldAlert className="w-3.5 h-3.5" aria-hidden="true" />
        </span>
        <span className="ai-proposal-summary-text">AI Proposal (if any)</span>
        {review && (
          <button
            type="button"
            className="ai-proposal-summary-link"
            onClick={(e) => {
              e.preventDefault();
              e.stopPropagation();
              review();
            }}
          >
            <ExternalLink className="w-3 h-3" aria-hidden="true" />
            Review on AI Proposals page
          </button>
        )}
        <ChevronDown className="ai-proposal-summary-chevron w-3.5 h-3.5" aria-hidden="true" />
      </summary>
      <div className="ai-proposal-body">
        {!hasProposal ? (
          <p className="ai-proposal-empty">No proposal was created for this query.</p>
        ) : (
          <>
            <div className="ai-proposal-head">
              <span
                className={`inline-flex items-center gap-1 rounded-full px-2 py-0.5 font-medium ${meta.color}`}
              >
                <Icon className="w-3 h-3" />
                {meta.label}
              </span>
            </div>

            {proposal.rationale && <p className="ai-proposal-rationale">{proposal.rationale}</p>}

            {proposal.risk_tier && (
              <p className="ai-proposal-risk">
                Risk: <span className="font-medium">{proposal.risk_tier}</span>
                {proposal.reversible ? ' · reversible' : ' · not reversible'}
              </p>
            )}

            {steps.length > 0 && (
              <ul className="ai-proposal-steps">
                {steps.map((s, i) => (
                  <li key={i}>
                    <span className="font-mono text-[10px] text-gray-400">#{s.seq ?? i}</span>{' '}
                    <span className="font-medium">{s.action}</span>
                    {s.target_device_id && (
                      <span className="text-gray-400"> → {s.target_device_id}</span>
                    )}
                  </li>
                ))}
              </ul>
            )}
          </>
        )}
      </div>
    </details>
  );
}
