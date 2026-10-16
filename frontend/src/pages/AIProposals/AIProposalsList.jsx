import React, { useState, useEffect, useCallback } from 'react';
import {
  Loader2,
  Sparkles,
  CheckCircle,
  XCircle,
  ShieldAlert,
  RefreshCw,
  Clock,
  Cpu,
} from 'lucide-react';
import api, { apiHelpers } from '@/services/api';
import { Button } from '@/components/ui/button';
import { Card } from '@/components/ui/card';
import { Toast } from '@/components/ui/Toast';

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
};

const STATUS_FILTERS = [
  { value: 'pending_approval', label: 'Pending Approval' },
  { value: '', label: 'All Statuses' },
  { value: 'approved', label: 'Approved' },
  { value: 'rejected', label: 'Rejected' },
  { value: 'blocked', label: 'Blocked' },
];

function StatusBadge({ status }) {
  const meta = STATUS_META[status] || STATUS_META.proposed;
  return (
    <span
      className={`inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium ${meta.color}`}
    >
      {meta.label}
    </span>
  );
}

export default function AIProposalsList() {
  const [plans, setPlans] = useState([]);
  const [statusFilter, setStatusFilter] = useState('pending_approval');
  const [loading, setLoading] = useState(true);
  const [busyPlan, setBusyPlan] = useState(null);
  const [toast, setToast] = useState(null);

  const fetchPlans = useCallback(async () => {
    try {
      setLoading(true);
      const data = await api.aiProposals.list(statusFilter || null, 100, 0);
      setPlans(data.plans || []);
    } catch (err) {
      console.error('Failed to load AI action plans:', err);
      setToast({ type: 'error', message: apiHelpers.formatError(err) });
    } finally {
      setLoading(false);
    }
  }, [statusFilter]);

  useEffect(() => {
    fetchPlans();
  }, [fetchPlans]);

  const handleDecide = async (planId, decision) => {
    let reason = null;
    if (decision === 'reject') {
      reason = window.prompt('Reason for rejection (optional):') || null;
    } else if (!window.confirm('Approve this AI action plan? This records your decision.')) {
      return;
    }

    try {
      setBusyPlan(planId);
      await api.aiProposals[decision](planId, reason);
      setToast({
        type: 'success',
        message: `Proposal ${decision === 'approve' ? 'approved' : 'rejected'}.`,
      });
      fetchPlans();
    } catch (err) {
      console.error(`Failed to ${decision} plan:`, err);
      setToast({ type: 'error', message: apiHelpers.formatError(err) });
    } finally {
      setBusyPlan(null);
    }
  };

  return (
    <div className="h-full flex flex-col overflow-hidden bg-[#0b0e13] p-2">
      {toast && (
        <Toast
          title={toast.type === 'error' ? 'Error' : 'Done'}
          message={toast.message}
          type={toast.type}
          onClose={() => setToast(null)}
        />
      )}

      <div className="container mx-auto max-w-7xl h-full flex flex-col">
        <div className="shrink-0 mb-4 space-y-4">
          <div className="flex flex-col md:flex-row justify-between items-start md:items-center gap-4">
            <div>
              <h1 className="text-3xl font-bold tracking-tight mb-1 text-white flex items-center gap-2">
                <Sparkles className="h-7 w-7 text-indigo-400" />
                AI Action Proposals
              </h1>
              <p className="text-gray-400 text-sm">
                Review AI-proposed device actions. Approving records a decision — nothing is
                executed automatically.
              </p>
            </div>
            <Button
              variant="ghost"
              onClick={fetchPlans}
              disabled={loading}
              className="text-gray-400 hover:text-white"
            >
              <RefreshCw className={`h-4 w-4 mr-2 ${loading ? 'animate-spin' : ''}`} />
              Refresh
            </Button>
          </div>

          <div className="flex flex-wrap items-center gap-3">
            <select
              value={statusFilter}
              onChange={(e) => setStatusFilter(e.target.value)}
              className="h-9 rounded-md border border-gray-700 bg-[#1a1f2e] text-gray-300 px-3 py-1 text-sm focus:outline-none focus:ring-1 focus:ring-ring"
            >
              {STATUS_FILTERS.map((option) => (
                <option key={option.value} value={option.value}>
                  {option.label}
                </option>
              ))}
            </select>
            <span className="text-sm text-gray-500">{plans.length} plan(s)</span>
            {statusFilter === 'pending_approval' && (
              <span className="text-sm text-yellow-400">
                {pendingApprovalCount(plans)} awaiting your review
              </span>
            )}
          </div>
        </div>

        <div className="flex-1 min-h-0 overflow-y-auto">
          {loading ? (
            <div className="flex justify-center items-center h-64">
              <Loader2 className="h-8 w-8 animate-spin text-primary" />
            </div>
          ) : plans.length === 0 ? (
            <Card className="p-8 text-center text-gray-400 border-dashed border-border bg-card">
              <Sparkles className="h-8 w-8 mx-auto mb-3 opacity-50" />
              <p className="mb-1">No AI action proposals to review</p>
              <p className="text-sm text-gray-500">
                Proposals appear here once the AI suggests a device action and the trust gate makes
                it actionable.
              </p>
            </Card>
          ) : (
            <div className="space-y-3">
              {plans.map((plan) => (
                <PlanCard
                  key={plan.plan_id}
                  plan={plan}
                  busy={busyPlan === plan.plan_id}
                  onApprove={() => handleDecide(plan.plan_id, 'approve')}
                  onReject={() => handleDecide(plan.plan_id, 'reject')}
                />
              ))}
            </div>
          )}
        </div>
      </div>

      {toast && <Toast {...toast} onClose={() => setToast(null)} />}
    </div>
  );
}

function pendingApprovalCount(plans) {
  return plans.filter((plan) => plan.status === 'pending_approval').length;
}

function PlanCard({ plan, busy, onApprove, onReject }) {
  const reviewable = plan.status === 'pending_approval';
  const targets = [...new Set((plan.steps || []).map((step) => step.target_device_id))].filter(
    Boolean
  );

  return (
    <Card className="p-4 bg-card border-border">
      <div className="flex flex-col md:flex-row md:items-start justify-between gap-4">
        <div className="flex-1 min-w-0 space-y-3">
          <div className="flex flex-wrap items-center gap-2">
            <StatusBadge status={plan.status} />
            <span className="inline-flex items-center gap-1 text-xs text-gray-400">
              <ShieldAlert className="h-3.5 w-3.5" />
              {plan.risk_tier}
            </span>
            {plan.reversible && <span className="text-xs text-gray-500">reversible</span>}
            <span className="inline-flex items-center gap-1 text-xs text-gray-500">
              <Clock className="h-3.5 w-3.5" />
              {plan.created_at ? new Date(plan.created_at).toLocaleString() : '-'}
            </span>
          </div>

          <p className="text-sm text-gray-200">{plan.rationale || 'No rationale provided.'}</p>

          <div className="space-y-1.5">
            {(plan.steps || []).map((step) => (
              <div
                key={`${plan.plan_id}-${step.seq}`}
                className="flex items-center gap-2 text-xs text-gray-400"
              >
                <Cpu className="h-3.5 w-3.5 text-indigo-400 shrink-0" />
                <span className="font-mono text-gray-200">{step.action}</span>
                <span className="text-gray-500">→</span>
                <span className="font-mono text-gray-300 truncate">{step.target_device_id}</span>
              </div>
            ))}
          </div>

          <div className="flex flex-wrap gap-x-4 gap-y-1 text-xs text-gray-500">
            <span className="font-mono">{plan.plan_id}</span>
            {targets.length > 0 && <span>devices: {targets.join(', ')}</span>}
            {typeof plan.trust?.score === 'number' && (
              <span>
                trust {Math.round(plan.trust.score * 100)}% ({plan.trust.mode})
              </span>
            )}
          </div>
        </div>

        {reviewable && (
          <div className="flex md:flex-col gap-2 shrink-0">
            <Button
              size="sm"
              onClick={() => onApprove(plan.plan_id)}
              disabled={busy}
              className="bg-teal-600 text-white hover:bg-teal-700"
            >
              <CheckCircle className="h-4 w-4 mr-1" />
              Approve
            </Button>
            <Button
              variant="ghost"
              size="sm"
              onClick={onReject}
              disabled={busy}
              className="text-red-400 hover:text-red-300 hover:bg-red-500/10"
            >
              <XCircle className="h-4 w-4 mr-1" />
              Reject
            </Button>
          </div>
        )}
      </div>
    </Card>
  );
}
