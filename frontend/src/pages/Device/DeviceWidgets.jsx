import { Loader2, Terminal, X, AlertTriangle, AlertCircle, CheckCircle2 } from 'lucide-react';
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
  if (!alerts || alerts.length === 0) {
    return (
      <Card className="lg:col-span-4">
        <h3 className="text-sm text-slate-300 font-medium mb-3">ACTIVE ALERTS</h3>
        <div className="border-t border-[#1f2735] mb-2"></div>
        <div className="flex items-center gap-2 text-emerald-400 text-sm p-2 bg-emerald-500/5 rounded border border-emerald-500/20">
          <CheckCircle2 className="w-4 h-4" />
          <span>No active alerts</span>
        </div>
      </Card>
    );
  }

  return (
    <Card className="lg:col-span-4">
      <h3 className="text-sm text-slate-300 font-medium mb-3">ACTIVE ALERTS</h3>
      <div className="border-t border-[#1f2735] mb-2"></div>
      <div className="space-y-2">
        {alerts.map((alert, idx) => {
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
                <AlertCircle className="w-4 h-4 text-red-500 mt-0.5 shrink-0" />
              ) : (
                <AlertTriangle className="w-4 h-4 text-orange-400 mt-0.5 shrink-0" />
              )}
              <div className="flex-1 min-w-0">
                <div
                  className={`text-sm font-medium ${isCritical ? 'text-red-400' : 'text-orange-300'}`}
                >
                  {alert.message}
                </div>
                <div className="text-xs text-slate-500 mt-1">
                  {alert.timestamp ? new Date(alert.timestamp).toLocaleString() : 'Just now'}
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

export const CommandHistoryWidget = ({ commandHistory }) => (
  <Card className="lg:col-span-4 text-left">
    <h3 className="text-sm text-slate-300 font-medium mb-3">COMMAND HISTORY</h3>
    <div className="border-t border-[#1f2735] mb-2"></div>
    <div className="space-y-3 text-sm">
      {commandHistory.map((a, i) => (
        <div key={i} className="flex flex-col">
          <div className="text-slate-200">{a.title}</div>
          <div className="text-xs text-slate-400">{a.date}</div>
        </div>
      ))}
    </div>
  </Card>
);

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

export const AuditWidget = ({ audit }) => (
  <Card>
    <h3 className="text-sm text-slate-300 font-medium mb-3">AUDIT</h3>
    <div className="border-t border-[#1f2735] mb-2"></div>
    <div className="space-y-3 text-sm">
      {audit.map((a, i) => (
        <div key={i} className="flex flex-col">
          <div className="text-slate-200">{a.title}</div>
          <div className="text-xs text-slate-400">{a.date}</div>
        </div>
      ))}
    </div>
  </Card>
);

export const LogsWidget = ({ logs }) => (
  <Card>
    <h3 className="text-sm text-slate-300 font-medium mb-3">LOGS</h3>
    <div className="border-t border-[#1f2735] mb-2"></div>
    <div className="space-y-3 text-sm">
      {logs.map((l, i) => (
        <div key={i} className="flex flex-col">
          <div className="text-slate-200">{l.message}</div>
          <div className="text-xs text-slate-400">{l.timestamp}</div>
        </div>
      ))}
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

export const DeviceActionsWidget = ({ actions, onActionClick, loadingAction }) => (
  <Card>
    <h3 className="text-sm text-slate-300 font-medium mb-3">DEVICE ACTIONS</h3>
    <div className="border-t border-[#1f2735] mb-2"></div>
    <div className="grid grid-cols-2 gap-2">
      {actions.map((action) => (
        <button
          key={action.key}
          onClick={() => onActionClick(action.key)}
          disabled={!!loadingAction}
          className={`px-3 py-2 rounded bg-[#0b3b3f] text-teal-200 text-xs hover:bg-[#0e4b50] transition-colors text-left flex items-center justify-between ${
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
