import React, { useState, useEffect, useCallback, useRef } from 'react';
import { Link } from 'react-router-dom';
import { Loader2, RefreshCw, Sparkles, Activity, ListChecks } from 'lucide-react';
import api, { apiHelpers } from '@/services/api';
import { Button } from '@/components/ui/button';
import { Card } from '@/components/ui/card';
import AIStatusBadge from './AIStatusBadge';

const STATUS_ORDER = [
  'pending_approval',
  'approved',
  'executing',
  'succeeded',
  'failed',
  'rolled_back',
  'rejected',
  'blocked',
  'expired',
  'proposed',
];

function pct(value) {
  if (typeof value !== 'number' || Number.isNaN(value)) {
    return '0%';
  }
  return `${Math.round(value * 100)}%`;
}

export default function AIReliabilityPanel({ statusFilter, onStatusFilterChange }) {
  const [summary, setSummary] = useState(null);
  const [reliability, setReliability] = useState(null);
  const [autonomy, setAutonomy] = useState(null);
  const [calibration, setCalibration] = useState(null);
  const [selectedOs, setSelectedOs] = useState(''); // '' = all (fleet-wide)
  const [loading, setLoading] = useState(true);
  const [errors, setErrors] = useState({});
  const fetchingRef = useRef(false);
  const initialLoadRef = useRef(true);

  const fetchAll = useCallback(async () => {
    if (fetchingRef.current) return;
    fetchingRef.current = true;
    try {
      if (initialLoadRef.current) setLoading(true);
      const [summaryData, reliabilityData, autonomyData] = await Promise.allSettled([
        api.ai.getPlanSummary(30, null),
        api.ai.getReliability(30, null, selectedOs || null),
        api.ai.getAutonomy(selectedOs || null),
      ]);

      const nextErrors = {};

      if (summaryData.status === 'fulfilled') {
        setSummary(summaryData.value);
      } else {
        nextErrors.summary = apiHelpers.formatError(summaryData.reason);
      }

      if (reliabilityData.status === 'fulfilled') {
        // The backend reports internal failures as HTTP 200 with
        // { status: 'error', message } rather than a rejected request.
        if (reliabilityData.value?.status === 'error') {
          nextErrors.reliability =
            reliabilityData.value?.message || 'Reliability metrics unavailable.';
        } else {
          setReliability(reliabilityData.value);
        }
      } else {
        nextErrors.reliability = apiHelpers.formatError(reliabilityData.reason);
      }

      if (autonomyData.status === 'fulfilled') {
        setAutonomy(autonomyData.value);
      } else {
        nextErrors.autonomy = apiHelpers.formatError(autonomyData.reason);
      }

      if (typeof api.ai.getCalibration === 'function') {
        try {
          const calibrationData = await api.ai.getCalibration(30, selectedOs || null);
          if (calibrationData?.status !== 'error') {
            setCalibration(calibrationData);
          }
        } catch (err) {
          nextErrors.calibration = apiHelpers.formatError(err);
        }
      }

      setErrors(nextErrors);
    } finally {
      setLoading(false);
      fetchingRef.current = false;
      initialLoadRef.current = false;
    }
  }, [selectedOs]);

  useEffect(() => {
    fetchAll();
  }, [fetchAll]);

  const refresh = () => {
    fetchAll();
  };

  const byStatus = summary?.by_status || {};
  const statusEntries = Object.entries(byStatus)
    .filter(([status]) => STATUS_ORDER.includes(status))
    .sort((a, b) => STATUS_ORDER.indexOf(a[0]) - STATUS_ORDER.indexOf(b[0]));

  const actionEntries = Object.entries(reliability?.action_types || {});

  // Filter recent plans by the selected status (from the clickable badges).
  const recentPlans = (summary?.recent || []).filter((plan) =>
    statusFilter ? plan.status === statusFilter : true
  );

  if (loading) {
    return (
      <Card className="p-6 bg-card border-border">
        <div className="flex justify-center items-center h-32">
          <Loader2 className="h-8 w-8 animate-spin text-primary" />
        </div>
      </Card>
    );
  }

  return (
    <Card className="p-4 bg-card border-border overflow-hidden">
      <div className="flex items-start justify-between gap-4">
        <div className="flex-1 min-w-0">
          <h2 className="text-lg font-semibold text-white flex items-center gap-2">
            <Activity className="h-5 w-5 text-indigo-400" />
            AI Reliability &amp; Task Delegation
          </h2>
          <p className="text-sm text-gray-400 mt-1">
            Aggregated AI action outcomes over the last 30 days, plus the current autonomy posture.
          </p>
        </div>
        <div className="flex items-center gap-2 shrink-0">
          <label className="text-xs text-gray-500">OS:</label>
          <select
            value={selectedOs}
            onChange={(e) => setSelectedOs(e.target.value)}
            className="text-xs bg-gray-800 border border-gray-700 rounded px-2 py-1 text-gray-300"
          >
            <option value="">All OS</option>
            <option value="windows">Windows</option>
            <option value="linux">Linux</option>
            <option value="macos">macOS</option>
            <option value="android">Android</option>
            <option value="ios">iOS</option>
          </select>
        </div>
        <Button
          variant="ghost"
          size="sm"
          onClick={refresh}
          disabled={loading}
          className="text-gray-400 hover:text-white"
        >
          <RefreshCw className={`h-4 w-4 mr-2 ${loading ? 'animate-spin' : ''}`} />
          Refresh
        </Button>
      </div>

      {Object.keys(errors).length > 0 && (
        <div className="mt-3 text-sm text-yellow-400">
          <p>Some AI metrics could not be loaded:</p>
          <ul className="list-disc list-inside">
            {Object.entries(errors).map(([section, message]) => (
              <li key={section}>
                {section}: {message}
              </li>
            ))}
          </ul>
        </div>
      )}

      {summary && (
        <>
          <div className="mt-4 grid grid-cols-1 md:grid-cols-3 gap-4">
            <div className="rounded-lg border border-border bg-[#0b0e13] p-3">
              <p className="text-xs text-gray-500 uppercase tracking-wide">Delegated tasks</p>
              <p className="text-2xl font-bold text-white mt-1">{summary.total ?? 0}</p>
              <p className="text-xs text-gray-500 mt-1">last {summary.period_days ?? 30} days</p>
            </div>
            <div className="rounded-lg border border-border bg-[#0b0e13] p-3 md:col-span-2">
              <p className="text-xs text-gray-500 uppercase tracking-wide mb-2">Tasks by status</p>
              <div className="flex flex-wrap gap-2">
                {statusEntries.length === 0 && (
                  <span className="text-sm text-gray-500">No delegated tasks in this window.</span>
                )}
                {statusEntries.map(([status, count]) => (
                  <button
                    key={status}
                    type="button"
                    onClick={() =>
                      onStatusFilterChange &&
                      onStatusFilterChange(statusFilter === status ? '' : status)
                    }
                    className={`inline-flex items-center gap-1 rounded-full px-2.5 py-1 text-xs font-medium border transition-colors ${
                      statusFilter === status
                        ? 'bg-indigo-600 text-white border-indigo-500'
                        : 'bg-gray-800 text-gray-300 border-gray-700 hover:bg-gray-700/60 hover:text-white'
                    }`}
                  >
                    <AIStatusBadge status={status} />
                    <span className="font-mono text-white">{count}</span>
                  </button>
                ))}
              </div>
            </div>
          </div>

          {recentPlans.length > 0 && (
            <div className="mt-4">
              <p className="text-xs text-gray-500 uppercase tracking-wide mb-2 flex items-center gap-1">
                <ListChecks className="h-3.5 w-3.5" />
                Recent delegated tasks
                {statusFilter && (
                  <span className="text-indigo-300 font-normal normal-case">— {statusFilter}</span>
                )}
              </p>
              <div className="space-y-2 max-h-[240px] overflow-y-auto pr-1">
                {recentPlans.map((plan) => {
                  const targetDevice = plan.target_device_id;
                  const row = (
                    <div className="flex flex-wrap items-center gap-2 text-sm rounded-md border border-border bg-[#0b0e13] px-3 py-2 hover:border-indigo-500/40 transition-colors">
                      <AIStatusBadge status={plan.status} />
                      <span className="font-mono text-xs text-gray-300">{plan.plan_id}</span>
                      <span className="text-xs text-gray-500">{plan.step_count} step(s)</span>
                      <span className="text-xs text-gray-400">
                        by {plan.created_by || 'unknown'}
                      </span>
                      <span className="text-xs text-gray-500">
                        {plan.created_at ? new Date(plan.created_at).toLocaleString() : '-'}
                      </span>
                      {targetDevice && (
                        <span className="text-xs text-indigo-300">→ push history</span>
                      )}
                    </div>
                  );
                  return targetDevice ? (
                    <Link
                      key={plan.plan_id}
                      to={`/device/${targetDevice}/history`}
                      className="block"
                    >
                      {row}
                    </Link>
                  ) : (
                    <div key={plan.plan_id}>{row}</div>
                  );
                })}
              </div>
            </div>
          )}
        </>
      )}

      {reliability && (
        <div className="mt-4">
          <p className="text-xs text-gray-500 uppercase tracking-wide mb-2 flex items-center gap-1">
            <Sparkles className="h-3.5 w-3.5" />
            Reliability by action type
          </p>
          {actionEntries.length === 0 ? (
            <p className="text-sm text-gray-500">No action outcomes recorded yet.</p>
          ) : (
            <div className="space-y-2 max-h-[180px] min-h-0 overflow-y-auto pr-1">
              {actionEntries.map(([action, entry]) => (
                <div
                  key={action}
                  className="rounded-md border border-border bg-[#0b0e13] px-3 py-2"
                >
                  <div className="flex flex-wrap items-center justify-between gap-2">
                    <span className="font-mono text-sm text-gray-100">{action}</span>
                    <span className="text-xs text-gray-500">
                      {entry.counts?.proposed ?? 0} proposed ·{' '}
                      {pct(entry.rates?.proposal_acceptance)} accepted
                    </span>
                  </div>
                  <div className="mt-2 grid grid-cols-2 md:grid-cols-4 gap-2 text-xs">
                    <div>
                      <span className="text-gray-500">execution success </span>
                      <span className="text-gray-200">{pct(entry.rates?.execution_success)}</span>
                    </div>
                    <div>
                      <span className="text-gray-500">verified improvement </span>
                      <span className="text-gray-200">
                        {pct(entry.rates?.verified_improvement)}
                      </span>
                    </div>
                    <div>
                      <span className="text-gray-500">rollback rate </span>
                      <span className="text-gray-200">{pct(entry.rates?.rollback_rate)}</span>
                    </div>
                    <div>
                      <span className="text-gray-500">failed </span>
                      <span className="text-gray-200">{entry.counts?.failed ?? 0}</span>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {calibration?.bands && (
        <div className="mt-4">
          <div className="flex items-center justify-between mb-2">
            <p className="text-xs text-gray-500 uppercase tracking-wide">
              Confidence calibration (trust vs. observed success)
            </p>
          </div>
          <div className="space-y-1 text-xs text-gray-300">
            {Object.entries(calibration.bands).map(([band, entry]) => (
              <div key={band} className="flex flex-wrap items-center gap-2">
                <span className="font-mono w-36 whitespace-nowrap">{entry.label || band}</span>
                <span>{entry.plans} plan(s)</span>
                <span>trust {pct(entry.avg_trust_score)}</span>
                <span>observed {pct(entry.observed_success_rate)}</span>
                <span>gap {pct(entry.calibration_gap)}</span>
              </div>
            ))}
          </div>
          {calibration.by_os && Object.keys(calibration.by_os).length > 1 && (
            <div className="mt-3 space-y-2">
              <p className="text-xs text-gray-500 uppercase tracking-wide">Per-OS breakdown</p>
              {Object.entries(calibration.by_os).map(([osf, osBands]) => (
                <div key={osf} className="text-xs text-gray-400">
                  <span className="font-mono text-gray-300">{osf}</span>
                  {Object.entries(osBands).map(([band, entry]) =>
                    entry.plans > 0 ? (
                      <span key={band} className="ml-2">
                        {entry.label || band}: {entry.plans} plan(s), gap{' '}
                        {pct(entry.calibration_gap)}
                      </span>
                    ) : null
                  )}
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {autonomy && Object.keys(autonomy).length > 0 && (
        <div className="mt-4">
          <p className="text-xs text-gray-500 uppercase tracking-wide mb-2">Autonomy levels</p>
          <div className="flex flex-wrap gap-2">
            {Object.entries(autonomy).map(([action, level]) => (
              <span
                key={action}
                className="rounded-full px-3 py-1 text-xs font-medium bg-indigo-500/10 text-indigo-300 border border-indigo-500/30"
              >
                {action}: level {level?.level ?? 'n/a'} ({level?.sample_count ?? 0} samples)
              </span>
            ))}
          </div>
          {selectedOs === '' &&
            Object.values(autonomy).some((l) => l?.by_os && Object.keys(l.by_os).length > 0) && (
              <div className="mt-2 space-y-1">
                <p className="text-xs text-gray-500 uppercase tracking-wide">Per-OS autonomy</p>
                {Object.entries(autonomy).map(([action, level]) =>
                  level?.by_os && Object.keys(level.by_os).length > 0 ? (
                    <div key={action} className="text-xs text-gray-400">
                      <span className="font-mono text-gray-300">{action}</span>
                      {Object.entries(level.by_os).map(([osf, osLevel]) => (
                        <span key={osf} className="ml-2">
                          {osf}: L{osLevel.level} ({osLevel.sample_count} runs)
                        </span>
                      ))}
                    </div>
                  ) : null
                )}
              </div>
            )}
        </div>
      )}
    </Card>
  );
}
