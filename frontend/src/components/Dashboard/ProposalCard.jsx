import React from 'react';
import { ShieldAlert, ExternalLink } from 'lucide-react';

/**
 * Flat AI-proposal affordance shown inline in a conversation turn.
 *
 * When a proposal exists this renders a single "Review AI Proposal" link that
 * deep-links to the proposal on the AI Proposals page; when no proposal was
 * created it renders a muted "No AI Proposal" label (not clickable). The full
 * review workflow lives on the AI Proposals page.
 */
export default function ProposalCard({ proposal, onReview }) {
  const hasProposal = proposal != null;

  if (!hasProposal) {
    return (
      <div className="ai-proposal-flat">
        <span className="ai-proposal-none">No AI Proposal</span>
      </div>
    );
  }

  const review = () => {
    if (onReview) {
      onReview(proposal.plan_id);
      return;
    }
    window.location.assign(
      proposal.plan_id ? `/ai-proposals?plan=${proposal.plan_id}` : '/ai-proposals'
    );
  };

  return (
    <div className="ai-proposal-flat">
      <button type="button" className="ai-proposal-link" onClick={review}>
        <ShieldAlert className="w-3.5 h-3.5" aria-hidden="true" />
        Review AI Proposal
        <ExternalLink className="ai-proposal-link-arrow w-3 h-3" aria-hidden="true" />
      </button>
    </div>
  );
}
