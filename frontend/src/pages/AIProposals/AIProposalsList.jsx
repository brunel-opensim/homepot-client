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
  PlayCircle,
  Activity,
} from 'lucide-react';
import api, { apiHelpers } from '@/services/api';
import { Button } from '@/components/ui/button';
import { Card } from '@/components/ui/card';
import { Toast } from '@/components/ui/Toast';
import AIStatusBadge from './AIStatusBadge';
import AIReliabilityPanel from './AIReliabilityPanel';

const STATUS_FILTERS = [
  { value: 'pending_approval', label: 'Pending Approval' },
  { value: '', label: 'All Statuses' },
  { value: 'approved', label: 'Approved' },
  { value: 'executing', label: 'Executing' },
  { value: 'succeeded', label: 'Succeeded' },
  { value: 'failed', label: 'Failed' },
  { value: 'rolled_back', label: 'Rolled Back' },
  { value: 'rejected', label: 'Rejected' },
  { value: 'blocked', label: 'Blocked' },
];

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

  const handleApproveStep = async (planId, step) => {
    if (
      !window.confirm(
        `Approve step ${step.seq + 1} (${step.action} → ${step.target_device_id})? ` +
          'Later steps still need their own approval.'
      )
    ) {
      return;
    }

    try {
      setBusyPlan(planId);
      await api.aiProposals.approveStep(planId, step.step_id);
      setToast({ type: 'success', message: `Step ${step.seq + 1} approved.` });
      fetchPlans();
    } catch (err) {
      console.error('Failed to approve step:', err);
      setToast({ type: 'error', message: apiHelpers.formatError(err) });
    } finally {
      setBusyPlan(null);
    }
  };

  const handleExecute = async (planId) => {
    if (
      !window.confirm(
        'Execute this approved plan now? Device commands will be queued and run on the devices.'
      )
    ) {
      return;
    }

    try {
      setBusyPlan(planId);
      const result = await api.aiProposals.execute(planId);
      if (result.status === 'blocked') {
        const reasons = (result.policy?.reasons || []).join(' ');
        setToast({
          type: 'error',
          message: `Execution blocked by policy. ${reasons}`.trim(),
        });
      } else {
        setToast({
          type: 'success',
          message: 'Execution started; devices will report back shortly.',
        });
      }
      fetchPlans();
    } catch (err) {
      console.error('Failed to execute plan:', err);
      setToast({ type: 'error', message: apiHelpers.formatError(err) });
    } finally {
      setBusyPlan(null);
    }
  };

  const handleExecuteAndWait = async (planId) => {
    if (
      !window.confirm(
        'Execute this approved plan and wait for the result? Device commands will be queued.'
      )
    ) {
      return;
    }

    try {
      setBusyPlan(planId);
      const result = await api.aiProposals.executeAndWait(planId, 60);
      if (result.completed) {
        const status = result.plan?.status;
        setToast({
          type: status === 'succeeded' ? 'success' : 'error',
          message: `Delegated task ${status || 'finished'} in ${result.elapsed_seconds}s.`,
        });
      } else {
        setToast({
          type: 'error',
          message: `Timed out after ${result.elapsed_seconds}s; plan still ${result.plan?.status}.`,
        });
      }
      fetchPlans();
    } catch (err) {
      console.error('Failed to execute-and-wait:', err);
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

          <div className="flex flex-wrap items-center gap-2">
            <div className="flex flex-wrap gap-1.5">
              {STATUS_FILTERS.map((option) => (
                <button
                  key={option.value || 'all'}
                  type="button"
                  onClick={() => setStatusFilter(option.value)}
                  className={`px-3 py-1.5 rounded-md text-xs font-medium transition-colors border ${
                    statusFilter === option.value
                      ? 'bg-indigo-600 text-white border-indigo-500'
                      : 'bg-[#1a1f2e] text-gray-300 border-gray-700 hover:bg-gray-700/60 hover:text-white'
                  }`}
                >
                  {option.label}
                </button>
              ))}
            </div>
            <span className="text-sm text-gray-500">{plans.length} plan(s)</span>
            {statusFilter === 'pending_approval' && (
              <span className="text-sm text-yellow-400">
                {pendingApprovalCount(plans)} awaiting your review
              </span>
            )}
          </div>
        </div>

        {/* Phase E: reliability + cross-session task aggregation overview */}
        <div className="shrink-0 mb-4">
          <AIReliabilityPanel />
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
                  onExecute={() => handleExecute(plan.plan_id)}
                  onExecuteAndWait={() => handleExecuteAndWait(plan.plan_id)}
                  onApproveStep={(step) => handleApproveStep(plan.plan_id, step)}
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

function PlanCard({ plan, busy, onApprove, onReject, onExecute, onExecuteAndWait, onApproveStep }) {
  const [dryRunResult, setDryRunResult] = useState(null);
  const [dryRunning, setDryRunning] = useState(false);
  const reviewable = plan.status === 'pending_approval';
  const executable = plan.status === 'approved';

  const handleDryRun = async () => {
    setDryRunning(true);
    try {
      const result = await api.aiProposals.dryRun(plan.plan_id);
      setDryRunResult(result);
    } catch (err) {
      console.error('Dry run failed:', err);
    } finally {
      setDryRunning(false);
    }
  };
  const targets = [...new Set((plan.steps || []).map((step) => step.target_device_id))].filter(
    Boolean
  );

  return (
    <Card className="p-4 bg-card border-border">
      <div className="flex flex-col md:flex-row md:items-start justify-between gap-4">
        <div className="flex-1 min-w-0 space-y-3">
          <div className="flex flex-wrap items-center gap-2">
            <AIStatusBadge status={plan.status} />
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
                className="flex flex-wrap items-center gap-2 text-xs text-gray-400"
              >
                <Cpu className="h-3.5 w-3.5 text-indigo-400 shrink-0" />
                <span className="font-mono text-gray-200">{step.action}</span>
                <span className="text-gray-500">→</span>
                <span className="font-mono text-gray-300 truncate">{step.target_device_id}</span>
                {step.status !== 'pending' && <AIStatusBadge status={step.status} />}
                {step.status === 'awaiting_approval' && (
                  <Button
                    size="sm"
                    onClick={() => onApproveStep(step)}
                    disabled={busy}
                    className="h-6 px-2 text-xs bg-teal-600 text-white hover:bg-teal-700"
                  >
                    <CheckCircle className="h-3 w-3 mr-1" />
                    Approve step
                  </Button>
                )}
              </div>
            ))}
          </div>

          {dryRunResult && (
            <div className="mt-2 rounded-md border border-border bg-[#0b0e13] p-3 text-xs space-y-1">
              <div className="flex items-center gap-2">
                <span className="text-gray-400">Dry run:</span>
                <span className={dryRunResult.policy?.allowed ? 'text-green-400' : 'text-red-400'}>
                  {dryRunResult.policy?.allowed ? 'policy OK' : 'policy blocked'}
                </span>
              </div>
              {(dryRunResult.steps || []).map((step, idx) => (
                <div key={idx} className="flex flex-wrap gap-2 text-gray-300">
                  <span className="font-mono">{step.action}</span>
                  <span className="text-gray-500">→</span>
                  <span className="font-mono text-gray-400">{step.target_device_id}</span>
                  <span className={step.policy_allowed ? 'text-green-400' : 'text-red-400'}>
                    {step.policy_allowed ? 'allowed' : 'blocked'}
                  </span>
                  {step.predicted_change && (
                    <span className="text-gray-500">{JSON.stringify(step.predicted_change)}</span>
                  )}
                </div>
              ))}
            </div>
          )}

          {plan.outcome && <OutcomeLine outcome={plan.outcome} />}

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

        <div className="flex md:flex-col gap-2 shrink-0">
          {reviewable && (
            <>
              <Button
                size="sm"
                onClick={onApprove}
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
            </>
          )}
          {executable && (
            <Button
              size="sm"
              onClick={onExecute}
              disabled={busy}
              className="bg-indigo-600 text-white hover:bg-indigo-700"
            >
              <PlayCircle className="h-4 w-4 mr-1" />
              Execute
            </Button>
          )}
          {executable && (
            <Button
              size="sm"
              onClick={onExecuteAndWait}
              disabled={busy}
              className="bg-emerald-600 text-white hover:bg-emerald-700"
            >
              <PlayCircle className="h-4 w-4 mr-1" />
              Execute &amp; wait
            </Button>
          )}
          <Button
            variant="ghost"
            size="sm"
            onClick={handleDryRun}
            disabled={busy || dryRunning}
            className="text-gray-300 hover:text-white hover:bg-gray-700/40"
          >
            {dryRunning ? (
              <Loader2 className="h-4 w-4 mr-1 animate-spin" />
            ) : (
              <Activity className="h-4 w-4 mr-1" />
            )}
            Dry run
          </Button>
        </div>
      </div>
    </Card>
  );
}

function OutcomeLine({ outcome }) {
  if (outcome.rolled_back) {
    return (
      <p className="text-xs text-purple-400">
        Rolled back{outcome.rollback_success === false ? ' (rollback failed)' : ' successfully'}.
      </p>
    );
  }
  if (outcome.verified) {
    return <p className="text-xs text-green-400">Verified against the device.</p>;
  }
  if (outcome.error) {
    return <p className="text-xs text-red-400">Failed: {outcome.error}</p>;
  }
  return null;
}
