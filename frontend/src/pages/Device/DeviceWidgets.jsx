import {
  Loader2,
  Terminal,
  X,
  AlertTriangle,
  AlertCircle,
  CheckCircle2,
  Shield,
  FileText,
  Activity,
  Power,
  RefreshCcw,
  Settings,
} from 'lucide-react';
import React from 'react';

/* === Reusable UI Components === */
export function Card({ children, className = '' }) {
  return (
    <div
      className={`border border-[#0e2f37] rounded-2xl p-4 shadow-[inset_0_1px_0_rgba(255,255,255,0.02)] ${className}`}
    >
      {children}
    </div>
  );
}

export function LargeCard({ children, className = '' }) {
  return (
    <div
      className={`border border-[#103237] rounded-2xl p-4 shadow-[0_8px_30px_rgba(2,136,153,0.06)] ${className}`}
    >
      {children}
    </div>
  );
}

export function ActionButton({ children, onClick, className }) {
  return (
    <button
      onClick={onClick}
      className={`px-4 py-2 rounded-md text-sm font-medium border backdrop-blur-sm border-[#0b3b3f] text-teal-200 hover:brightness-105 ${className || ''}`}
    >
      {children}
    </button>
  );
}

export function StatBlock({ title, value, subtitle, data = [] }) {
  return (
    <div className="border border-[#0d2b2f] rounded-lg p-3 flex flex-col gap-2 text-left">
      <div className="w-full h-10">
        <Sparkline data={data} height={40} animated />
      </div>
      <div className="mt-2">
        <div className="text-xs text-slate-400">{title}</div>
        <div className="text-sm font-semibold tracking-tight">{value}</div>
        <div className="text-xs text-slate-400">{subtitle}</div>
      </div>
    </div>
  );
}

export function Sparkline({ data = [4, 6, 5, 7, 6, 8, 9], height = 40, animated = false }) {
  const width = 144;
  const max = Math.max(...data) || 1;
  const min = Math.min(...data) || 0;
  const points = data
    .map((d, i) => {
      const x = (i / (data.length - 1 || 1)) * width;
      const y = height - ((d - min) / (max - min || 1)) * height;
      return `${x},${y}`;
    })
    .join(' ');

  const pathD = `M${points.split(' ').join(' L ')}`;

  return (
    <svg
      viewBox={`0 0 ${width} ${height}`}
      className={`w-full h-full ${animated ? 'animate-pulse' : ''}`}
      preserveAspectRatio="none"
    >
      <defs>
        <linearGradient id="gStroke" x1="0" x2="1">
          <stop offset="0%" stopColor="#34d399" />
          <stop offset="100%" stopColor="#06b6d4" />
        </linearGradient>
      </defs>

      <path
        d={pathD}
        fill="none"
        stroke="url(#gStroke)"
        strokeWidth={2.2}
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
}

/* === Feature Widgets === */

export const AlertsWidget = ({ alerts = [] }) => {
  // Limit to 5 alerts as per requirement to avoid clutter and staleness
  const displayedAlerts = alerts.slice(0, 5);

  if (!alerts || alerts.length === 0) {
    return (
      <Card>
        <h3 className="text-sm text-slate-300 font-medium mb-3">AI ALERTS</h3>
        <div className="border-t border-[#1f2735] mb-2"></div>
        <div className="flex items-center gap-2 text-emerald-400 text-sm p-4 bg-emerald-500/5 rounded border border-emerald-500/20 justify-center">
          <CheckCircle2 className="w-4 h-4" />
          <span>No active anomalies detected</span>
        </div>
      </Card>
    );
  }

  return (
    <Card>
      <div className="flex items-center justify-between mb-3">
        <h3 className="text-sm text-slate-300 font-medium">AI ALERTS</h3>
        <span className="text-[10px] text-slate-500 font-mono">
          LATEST {displayedAlerts.length} ISSUES
        </span>
      </div>
      <div className="border-t border-[#1f2735] mb-2"></div>
      <div className="space-y-2 max-h-[300px] overflow-y-auto custom-scrollbar pr-2">
        {displayedAlerts.map((alert, idx) => {
          const isCritical = alert.severity === 'critical';
          return (
            <div
              key={idx}
              className={`flex items-start gap-3 p-3 rounded border ${
                isCritical
                  ? 'bg-red-500/10 border-red-500/30'
                  : 'bg-orange-500/10 border-orange-500/30'
              }`}
            >
              {isCritical ? (
                <AlertCircle className="w-5 h-5 text-red-500 mt-0.5 shrink-0" />
              ) : (
                <AlertTriangle className="w-5 h-5 text-orange-400 mt-0.5 shrink-0" />
              )}
              <div className="flex-1 min-w-0">
                <div
                  className={`text-sm font-medium ${isCritical ? 'text-red-400' : 'text-orange-300'}`}
                >
                  {alert.id !== undefined && alert.id !== null && (
                    <span className="inline-block mr-2 px-1.5 py-0.5 text-[10px] border border-current rounded font-mono bg-black/20">
                      #{alert.id}
                    </span>
                  )}
                  {alert.message}
                </div>
                <div className="flex items-center gap-2 mt-1">
                  <div className="text-xs text-slate-500">
                    {alert.timestamp ? new Date(alert.timestamp).toLocaleTimeString() : 'Just now'}
                  </div>
                  <div className="text-[10px] text-slate-600 bg-slate-900/50 px-1 rounded uppercase tracking-wider font-mono">
                    {alert.source || 'SYSTEM'}
                  </div>
                </div>
              </div>
            </div>
          );
        })}
      </div>
    </Card>
  );
};

export const HealthWidget = ({ stats, sparkData }) => (
  <LargeCard className="md:col-span-2">
    <h3 className="text-sm text-slate-300 font-medium mb-4">HEALTH & STATUS</h3>
    <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
      {['cpu', 'memory', 'disk'].map((key) => (
        <div key={key} className="flex flex-col gap-1">
          <StatBlock
            data={sparkData.small}
            title={stats[key].label}
            value={stats[key].value}
            subtitle={stats[key].subtitle}
          />
        </div>
      ))}
    </div>
  </LargeCard>
);

export const SettingsWidget = ({ commandInput, setCommandInput, handleCommandSubmit }) => (
  <Card className="text-left">
    <h3 className="text-sm text-slate-300 font-medium">SETTINGS</h3>
    <div className="border-t border-[#1f2735] mt-2"></div>
    <div className="mt-3">
      <input
        className="w-full bg-[#051a1d] border border-[#0e2f37] rounded px-3 py-2 text-sm outline-none placeholder:text-slate-500"
        placeholder="Enter command"
        value={commandInput}
        onChange={(e) => setCommandInput(e.target.value)}
        onKeyDown={(e) => e.key === 'Enter' && handleCommandSubmit()}
      />
      <div className="mt-3 text-sm text-slate-200">restart POS</div>
      <div className="mt-1 text-xs text-slate-400">restart POS</div>
    </div>
  </Card>
);

export const JobHistoryWidget = ({ jobs }) => {
  if (!jobs || jobs.length === 0) {
    return (
      <Card>
        <h3 className="text-sm text-slate-300 font-medium mb-3">JOB HISTORY</h3>
        <div className="border-t border-[#1f2735] mb-2"></div>
        <div className="text-slate-500 text-xs italic text-center py-4">
          No jobs executed recently
        </div>
      </Card>
    );
  }

  return (
    <Card className="text-left">
      <div className="flex items-center justify-between mb-3">
        <h3 className="text-sm text-slate-300 font-medium">JOB HISTORY</h3>
        <span className="text-[10px] text-slate-500 font-mono">LATEST {jobs.length} TASKS</span>
      </div>
      <div className="border-t border-[#1f2735] mb-2"></div>
      <div className="space-y-3 text-sm max-h-[300px] overflow-y-auto custom-scrollbar pr-2">
        {jobs.map((job, i) => {
          let statusColor = 'text-slate-400';
          let StatusIcon = Activity;

          if (job.status === 'completed' || job.status === 'success') {
            statusColor = 'text-emerald-400';
            StatusIcon = CheckCircle2;
          } else if (job.status === 'failed' || job.status === 'error') {
            statusColor = 'text-red-400';
            StatusIcon = AlertCircle;
          } else if (job.status === 'pending' || job.status === 'running') {
            statusColor = 'text-blue-400';
            StatusIcon = Loader2;
          }

          return (
            <div
              key={i}
              className="flex items-center justify-between p-2 rounded bg-[#0b2024]/50 border border-[#1f2735]/50"
            >
              <div className="flex items-center gap-3">
                <StatusIcon
                  className={`w-4 h-4 ${statusColor} ${job.status === 'running' ? 'animate-spin' : ''}`}
                />
                <div className="flex flex-col">
                  <span className="text-slate-200 font-medium">{job.action || 'Unknown Task'}</span>
                  <span className="text-xs text-slate-500">
                    ID: {job.job_id?.substring(0, 8) || 'N/A'}
                  </span>
                </div>
              </div>
              <div className="flex flex-col items-end">
                <span className={`text-xs uppercase font-bold ${statusColor}`}>{job.status}</span>
                <span className="text-xs text-slate-500">
                  {job.created_at ? new Date(job.created_at).toLocaleString() : ''}
                </span>
              </div>
            </div>
          );
        })}
      </div>
    </Card>
  );
};

export const ConnectionsWidget = ({ connections, sparkData }) => (
  <Card>
    <h3 className="text-sm text-slate-300 font-medium">CONNECTIONS</h3>
    <div className="border-t border-[#1f2735] mt-2"></div>
    <ul className="mt-4 space-y-3 text-sm">
      {connections.map((c) => (
        <li key={c.name} className="flex items-center justify-between">
          <span className="font-medium">{c.name}</span>
          <div
            className={`w-3 h-3 rounded-full ${
              c.status === 'online' ? 'bg-emerald-400 shadow-[0_0_8px_rgba(34,197,94,0.12)]' : ''
            }`}
          />
        </li>
      ))}
    </ul>
    <div className="border-t border-[#1f2735] mt-4"></div>
    <div className="mt-4">
      <div className="text-xs text-slate-400 mb-2">Network</div>
      <div className="w-full h-12">
        <Sparkline data={sparkData.medium} height={48} animated />
      </div>
    </div>
  </Card>
);

export const CommandInputWidget = ({ cmdInput, handleCmdInputChange, handleSendCommand }) => (
  <Card>
    <h3 className="text-sm text-slate-300 font-medium mb-3">COMMAND</h3>
    <div className="border-t border-[#1f2735] mb-2"></div>
    <div className="flex flex-col gap-3">
      <div className="relative">
        <input
          className="w-full bg-[#051a1d] border border-[#0e2f37] rounded px-3 py-2 text-sm outline-none placeholder:text-slate-500 pr-10"
          placeholder="Enter command"
          value={cmdInput}
          onChange={handleCmdInputChange}
          onKeyDown={(e) => e.key === 'Enter' && handleSendCommand()}
        />
        <button
          onClick={handleSendCommand}
          className="absolute right-1 top-1/2 -translate-y-1/2 px-2 py-1 rounded text-teal-300 text-sm hover:bg-teal-500/30"
        >
          &gt;
        </button>
      </div>
      <div className="text-sm text-slate-200 mt-2">restart POS</div>
      <div className="border-t border-[#1f2735] mb-2"></div>
      <div className="text-xs text-slate-400">Logs</div>
      <div className="text-sm text-slate-200 mt-3">restart POS</div>
      <div className="text-xs text-slate-400">Logs</div>
    </div>
  </Card>
);

export const AuditWidget = ({ audit }) => {
  if (!audit || audit.length === 0) {
    return (
      <Card>
        <h3 className="text-sm text-slate-300 font-medium mb-3">AUDIT TRAIL</h3>
        <div className="border-t border-[#1f2735] mb-2"></div>
        <div className="text-slate-500 text-xs italic text-center py-4">No audit records found</div>
      </Card>
    );
  }

  return (
    <Card>
      <div className="flex items-center justify-between mb-3">
        <h3 className="text-sm text-slate-300 font-medium">AUDIT TRAIL</h3>
        <span className="text-[10px] text-slate-500 font-mono">LATEST {audit.length} EVENTS</span>
      </div>
      <div className="border-t border-[#1f2735] mb-2"></div>
      <div className="space-y-4 text-sm max-h-[300px] overflow-y-auto custom-scrollbar pr-2">
        {audit.map((a, i) => {
          let Icon = FileText;
          let color = 'text-slate-400';

          if (a.event_type?.includes('error')) {
            Icon = AlertTriangle;
            color = 'text-red-400';
          } else if (a.event_type?.includes('startup')) {
            Icon = Power;
            color = 'text-green-400';
          } else if (a.event_type?.includes('update')) {
            Icon = RefreshCcw;
            color = 'text-blue-400';
          } else if (a.event_type?.includes('user')) {
            Icon = Shield;
            color = 'text-indigo-400';
          } else if (a.event_type?.includes('config')) {
            Icon = Settings;
            color = 'text-purple-400';
          }

          return (
            <div key={i} className="flex gap-3 relative">
              {/* Timeline line */}
              {i !== audit.length - 1 && (
                <div className="absolute left-[9px] top-6 bottom-[-20px] w-px bg-[#1f2735]" />
              )}

              <div className={`mt-0.5 shrink-0 ${color}`}>
                <Icon className="w-4 h-4" />
              </div>
              <div className="flex-1 min-w-0">
                <div className="text-slate-200 font-medium">{a.description || a.title}</div>
                <div className="flex gap-2 text-xs text-slate-500 mt-0.5">
                  <span>{a.created_at ? new Date(a.created_at).toLocaleString() : a.date}</span>
                  {a.event_type && <span className="opacity-50">• {a.event_type}</span>}
                </div>
              </div>
            </div>
          );
        })}
      </div>
    </Card>
  );
};

export const LogsWidget = ({ logs }) => (
  <Card>
    <div className="flex items-center justify-between mb-3">
      <h3 className="text-sm text-slate-300 font-medium">LIVE LOGS</h3>
      <span className="text-[10px] text-slate-500 font-mono">LATEST {logs.length} EVENTS</span>
    </div>
    <div className="border-t border-[#1f2735] mb-2"></div>
    <div className="space-y-3 text-sm max-h-[300px] overflow-y-auto custom-scrollbar">
      {logs.map((l, i) => {
        const isError = l.severity === 'error' || l.severity === 'critical';
        const isWarning = l.severity === 'warning';

        return (
          <div key={i} className="flex flex-col gap-1 border-b border-[#1f2735] pb-2 last:border-0">
            <div className="flex items-center gap-2">
              <span
                className={`text-[10px] uppercase font-bold px-1.5 py-0.5 rounded border ${
                  isError
                    ? 'bg-red-500/20 text-red-400 border-red-500/30'
                    : isWarning
                      ? 'bg-orange-500/20 text-orange-400 border-orange-500/30'
                      : 'bg-blue-500/20 text-blue-400 border-blue-500/30'
                }`}
              >
                {l.severity || 'INFO'}
              </span>
              <span className="text-xs text-slate-500 font-mono">
                {l.timestamp ? new Date(l.timestamp).toLocaleTimeString() : ''}
              </span>
            </div>
            <div className="text-slate-300 font-mono text-xs break-all">
              {l.error_message || l.message}
            </div>
          </div>
        );
      })}
      {logs.length === 0 && (
        <div className="text-slate-500 text-xs italic text-center py-4">Waiting for logs...</div>
      )}
    </div>
  </Card>
);

export const MonitoringWidget = () => (
  <Card>
    <h3 className="text-sm text-slate-300 font-medium">MONITORING</h3>
    <div className="border-t border-[#1f2735] mt-2"></div>
    <div className="mt-3 text-sm text-slate-200">Uptime</div>
    <div className="mt-2">
      <Sparkline data={[8, 10, 12, 10, 14, 16, 18]} height={48} animated />
    </div>
    <div className="border-t border-[#1f2735] mt-2"></div>
    <div className="mt-3 text-sm text-slate-200">Alerts</div>
    <div className="mt-2">
      <Sparkline data={[4, 6, 5, 6, 7, 6, 8]} height={48} animated />
    </div>
  </Card>
);

export const DeviceInfoWidget = ({ device }) => (
  <Card>
    <h3 className="text-sm text-slate-300 font-medium mb-3">DEVICE INFO</h3>
    <div className="border-t border-[#1f2735] mb-3"></div>
    <div className="space-y-3 text-sm">
      <div className="flex justify-between items-center">
        <span className="text-slate-400">Status</span>
        <span
          className={`px-2 py-0.5 rounded text-xs font-medium uppercase ${
            device?.status === 'online'
              ? 'bg-emerald-500/10 text-emerald-400 border border-emerald-500/20'
              : device?.status === 'offline'
                ? 'bg-red-500/10 text-red-400 border border-red-500/20'
                : 'bg-slate-700 text-slate-300'
          }`}
        >
          {device?.status || 'UNKNOWN'}
        </span>
      </div>
      <div className="flex justify-between">
        <span className="text-slate-400">IP Address</span>
        <span className="text-slate-200 font-mono">{device?.ip_address || 'N/A'}</span>
      </div>
      <div className="flex justify-between">
        <span className="text-slate-400">MAC Address</span>
        <span className="text-slate-200 font-mono">{device?.mac_address || 'N/A'}</span>
      </div>
      <div className="flex justify-between">
        <span className="text-slate-400">Firmware</span>
        <span className="text-slate-200">{device?.firmware_version || 'N/A'}</span>
      </div>
      <div className="flex justify-between">
        <span className="text-slate-400">Type</span>
        <span className="text-slate-200 uppercase">
          {device?.device_type?.replace(/_/g, ' ') || 'N/A'}
        </span>
      </div>
      <div className="flex justify-between">
        <span className="text-slate-400">Site</span>
        <span className="text-teal-400">{device?.site_name || device?.site_id || 'N/A'}</span>
      </div>
      <div className="flex justify-between">
        <span className="text-slate-400">Last Seen</span>
        <span className="text-slate-200 text-xs mt-0.5">
          {device?.last_seen ? new Date(device.last_seen).toLocaleString() : 'Never'}
        </span>
      </div>
    </div>
  </Card>
);

export const DeviceActionsWidget = ({ actions, onActionClick, loadingAction }) => (
  <Card>
    <h3 className="text-sm text-slate-300 font-medium mb-3">DEVICE ACTIONS</h3>
    <div className="border-t border-[#1f2735] mb-2"></div>
    <div className="grid grid-cols-1 gap-2">
      {actions.map((action) => (
        <button
          key={action.key}
          onClick={() => onActionClick(action.key)}
          disabled={!!loadingAction}
          className={`px-3 py-2 rounded bg-[#0b3b3f] text-teal-200 text-xs hover:bg-[#0e4b50] transition-colors text-left flex items-center justify-between whitespace-nowrap ${
            loadingAction && loadingAction !== action.key ? 'opacity-50 cursor-not-allowed' : ''
          }`}
        >
          <span>{action.label}</span>
          {loadingAction === action.key && <Loader2 className="h-3 w-3 animate-spin" />}
        </button>
      ))}
    </div>
  </Card>
);

export const DirectConnectWidget = ({
  isOpen,
  onClose,
  terminalOutput,
  terminalInput,
  setTerminalInput,
  handleTerminalSubmit,
  terminalEndRef,
  deviceName,
}) => {
  if (!isOpen) return null;

  return (
    <div className="bg-[#020817] border border-[#1e293b] rounded-xl overflow-hidden shadow-2xl animate-in fade-in slide-in-from-top-4 duration-300">
      <div className="bg-[#0f172a] px-4 py-2 border-b border-[#1e293b] flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Terminal className="h-4 w-4 text-teal-400" />
          <span className="text-xs font-medium text-slate-300">Remote Shell - {deviceName}</span>
        </div>
        <div className="flex items-center gap-2">
          <button onClick={onClose} className="text-slate-500 hover:text-white">
            <X className="h-4 w-4" />
          </button>
        </div>
      </div>
      <div
        className="p-4 h-64 overflow-y-auto font-mono text-xs space-y-1"
        onClick={() => document.getElementById('terminal-input')?.focus()}
      >
        {terminalOutput.map((line, i) => (
          <div
            key={i}
            className={`${
              line.type === 'error'
                ? 'text-red-400'
                : line.type === 'success'
                  ? 'text-green-400'
                  : line.type === 'input'
                    ? 'text-slate-300'
                    : 'text-blue-300'
            }`}
          >
            {line.text}
          </div>
        ))}
        <div ref={terminalEndRef} />
      </div>
      <form
        onSubmit={handleTerminalSubmit}
        className="border-t border-[#1e293b] bg-[#0f172a] p-2 flex items-center gap-2"
      >
        <span className="text-teal-500 font-mono text-sm whitespace-nowrap">
          {`root@${deviceName?.toLowerCase().replace(/\s+/g, '-') || 'device'}:~#`}
        </span>
        <input
          id="terminal-input"
          type="text"
          value={terminalInput}
          onChange={(e) => setTerminalInput(e.target.value)}
          className="flex-1 bg-transparent border-none focus:ring-0 text-slate-200 font-mono text-sm placeholder-slate-600"
          placeholder="Enter command..."
          autoComplete="off"
          autoFocus
        />
      </form>
    </div>
  );
};
