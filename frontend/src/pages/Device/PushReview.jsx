import { Button } from '@/components/ui/button';
import { Toast } from '@/components/ui/Toast';
import api from '@/services/api';
import { lifecycleStages, formatCommandType } from '@/utils/commandLifecycle';
// Cleaned up unused imports that were causing blank page errors
import {
  AlertTriangle,
  ArrowLeft,
  CheckCircle2,
  ChevronDown,
  Clock,
  FileJson,
  Loader2,
  MessageSquare,
  Rocket,
  ShieldAlert,
  Terminal,
  XCircle,
} from 'lucide-react';
import React, { useEffect, useState, useRef } from 'react';
import { createPortal } from 'react-dom';
import { useNavigate, useParams, useLocation } from 'react-router-dom';
import { useAuth } from '@/hooks/useAuth';

// Predefined templates for common commands
const FALLBACK_COMMAND_TEMPLATES = {
  RUN_COMMAND: {
    label: 'Run Command',
    action: 'run_command',
    group: 'Run Commands',
    permission: 'root_access',
    defaultData: { command: 'uname -a', timeout_seconds: 30 },
    defaultDataByOS: {
      windows: { command: 'systeminfo' },
      macos: { command: 'sw_vers' },
    },
    description:
      'Run a command with elevated privileges using the target device\u2019s shell (PowerShell on Windows, sh on macOS/Linux).',
  },
  RUN_SCRIPT: {
    label: 'Run Script',
    action: 'run_script',
    group: 'Run Commands',
    permission: 'root_access',
    defaultData: { script: '#!/bin/sh\nid', timeout_seconds: 30 },
    defaultDataByOS: {
      windows: { script: 'Get-Process | Select-Object -First 5 Name, Id, CPU' },
    },
    description:
      'Run a script with elevated privileges using the target device\u2019s shell (PowerShell on Windows, POSIX sh on macOS/Linux).',
  },
  RUN_COMMAND_UNPRIVILEGED: {
    label: 'Run Command (Unprivileged)',
    action: 'run_command_unprivileged',
    group: 'Run Commands',
    permission: 'command_execution',
    defaultData: { command: 'ipconfig', timeout_seconds: 30 },
    defaultDataByOS: {
      windows: { command: 'ipconfig' },
      linux: { command: 'uname -a' },
      macos: { command: 'sw_vers' },
    },
    description:
      'Run a command as the unprivileged device user (no elevation, PowerShell on Windows, sh on macOS/Linux).',
  },
  APPLY_CONFIG: {
    label: 'Apply Configuration',
    action: 'update_config',
    group: 'Configuration',
    permission: 'root_access',
    defaultData: {
      volume: 50,
      brightness: 75,
    },
    description:
      'Update system settings with root privileges. Volume uses the Windows legacy audio API (may not move the modern master slider on all systems); brightness uses DDC/CI with a WMI fallback and reports failure when the panel does not support software control.',
  },
  REBOOT_SYSTEM: {
    label: 'Reboot System',
    action: 'restart',
    group: 'System',
    permission: 'root_access',
    defaultData: {},
    description: 'Reboot the system the User App runs on. The reboot begins immediately.',
  },
  RESTART_AGENT: {
    label: 'Restart Agent',
    action: 'restart_agent',
    group: 'Services & Agent',
    permission: 'root_access',
    defaultData: {},
    description:
      'Restart the agent process itself. The User App supervisor respawns it, briefly interrupting heartbeat and telemetry. Use for an online-but-misbehaving agent.',
  },
  UPDATE_APP: {
    label: 'Update User App',
    action: 'update_app',
    group: 'Services & Agent',
    permission: 'root_access',
    defaultData: {},
    description:
      'Update the HOMEPOT User App to the latest published release. The app checks the server-hosted feed, downloads, and restarts to install in one action. Briefly interrupts telemetry during the restart.',
  },
  ROLLBACK_APP: {
    label: 'Roll Back User App',
    action: 'rollback_app',
    group: 'Services & Agent',
    permission: 'root_access',
    defaultData: {},
    description:
      'Roll the HOMEPOT User App back to the previously served release. The app checks the server-hosted previous channel, downloads, and restarts to install the older version in one action. Use only when a newly installed release is broken.',
  },
  UPDATE_FIRMWARE: {
    label: 'Update Firmware',
    action: 'update_config',
    group: 'Configuration',
    permission: 'root_access',
    defaultData: {
      version: '2.4.0',
      url: 'https://homepot.cabera.com/firmware/demo-firmware-2.4.0.bin',
      checksum: 'sha256:a079d6bb4d884cc7571769ad5f6a79164324f93e894a68cfec88ae2ed6bf043e',
    },
    description:
      'Download and verify the HomePot demo firmware artifact (hosted on the demo server). The artifact is staged and discarded; nothing is flashed. Replace the URL and checksum with a vendor artifact for real updates.',
  },
  START_PROGRAM: {
    label: 'Start Program',
    action: 'start_program',
    group: 'Programs',
    permission: 'root_access',
    defaultData: {
      path: 'notepad.exe',
      args: [],
    },
    description:
      'Launch a program on the device in the background. Provide an absolute path (or a name on PATH) and optional arguments.',
  },
  STOP_PROGRAM: {
    label: 'Stop Program',
    action: 'stop_program',
    group: 'Programs',
    permission: 'root_access',
    defaultData: {
      name: 'notepad.exe',
      force: false,
    },
    description:
      'Stop a running process by name or PID. Set force to terminate immediately. Critical system processes are never stopped.',
  },
  BOOTSTRAP_WINGET: {
    label: 'Bootstrap Winget (App Installer)',
    action: 'bootstrap_winget',
    group: 'Programs',
    permission: 'root_access',
    defaultData: { timeout_seconds: 300 },
    description:
      'Ensure winget (App Installer) is installed on the Windows device. Run once per device before using Install/Update/Uninstall Program on Windows 10 builds where App Installer is missing.',
  },
  INSTALL_PROGRAM: {
    label: 'Install Program',
    action: 'install_program',
    group: 'Programs',
    permission: 'root_access',
    defaultData: { package: 'Notepad++.Notepad++', timeout_seconds: 300 },
    description: 'Install a program on the Windows device via winget (silent, machine-wide).',
  },
  UNINSTALL_PROGRAM: {
    label: 'Uninstall Program',
    action: 'uninstall_program',
    group: 'Programs',
    permission: 'root_access',
    defaultData: { package: 'Notepad++.Notepad++', timeout_seconds: 300 },
    description: 'Uninstall a program from the Windows device via winget (silent).',
  },
  LIST_INSTALLED_PROGRAMS: {
    label: 'List Installed Programs',
    action: 'list_installed_programs',
    group: 'Diagnostics',
    permission: 'command_execution',
    defaultData: {},
    description:
      'List the programs installed on the Windows device with their install locations (from the registry). Use the location to find executables for Start/Stop Program.',
  },
  UPDATE_PROGRAM: {
    label: 'Update Program',
    action: 'update_program',
    group: 'Programs',
    permission: 'root_access',
    defaultData: { package: 'Notepad++.Notepad++', timeout_seconds: 300 },
    description: 'Update a program on the Windows device via winget (silent).',
  },
  UPGRADE_ALL_PROGRAMS: {
    label: 'Upgrade All Programs',
    action: 'upgrade_all_programs',
    group: 'Programs',
    permission: 'root_access',
    defaultData: { timeout_seconds: 600 },
    description: 'Upgrade all installed programs on the Windows device via winget (silent).',
  },
  HEALTH_CHECK: {
    label: 'Health Check',
    action: 'health_check',
    group: 'Diagnostics',
    permission: 'command_execution',
    defaultData: {
      tests: ['network', 'storage', 'memory'],
    },
    description: 'Execute self-tests (network/storage/memory) and report pass/fail.',
  },
  LIST_PROCESSES: {
    label: 'List Processes',
    action: 'list_processes',
    group: 'Diagnostics',
    permission: 'process_monitoring',
    defaultData: {
      max_results: 50,
      sort_by: 'cpu',
      include_memory: true,
    },
    description: 'List the running processes on the device.',
  },
  LIST_CONNECTIONS: {
    label: 'List Network Connections',
    action: 'list_connections',
    group: 'Diagnostics',
    permission: 'network_monitoring',
    defaultData: {
      filter_state: 'ESTABLISHED',
      limit: 100,
    },
    description: 'List the device\u2019s active network connections.',
  },
  LIST_DRIVES: {
    label: 'List Drives',
    action: 'list_drives',
    group: 'Diagnostics',
    permission: 'command_execution',
    defaultData: {},
    description: 'List mounted drives/volumes and their free space.',
  },
  TAIL_SYSTEM_LOG: {
    label: 'Tail System Log',
    action: 'tail_system_log',
    group: 'Diagnostics',
    permission: 'command_execution',
    defaultData: { lines: 50 },
    description:
      'Read the most recent OS error/warning events (Windows Event Log, journalctl, or macOS unified log).',
  },
  NETWORK_TEST: {
    label: 'Network Test',
    action: 'network_test',
    group: 'Diagnostics',
    permission: 'network_monitoring',
    defaultData: { host: 'example.com', timeout_seconds: 10 },
    description: 'Probe a host\u2019s connectivity (DNS, ping, optional TCP port).',
  },
  LIST_SESSIONS: {
    label: 'List Sessions',
    action: 'list_sessions',
    group: 'Diagnostics',
    permission: 'command_execution',
    defaultData: {},
    description: 'List users currently logged into the device.',
  },
  GET_SYSTEM_INFO: {
    label: 'Get System Info',
    action: 'get_system_info',
    group: 'Diagnostics',
    permission: 'command_execution',
    defaultData: {},
    description:
      'Return a hardware/OS inventory snapshot (CPU, RAM, OS build, and on Windows serial/model/GPU).',
  },
  COLLECT_SUPPORT_BUNDLE: {
    label: 'Collect Support Bundle',
    action: 'collect_support_bundle',
    group: 'Diagnostics',
    permission: 'command_execution',
    defaultData: {},
    description:
      'Bundle hardware/OS, disk, process, and metrics snapshots into a single zip support artifact.',
  },
  SCAN_FILESYSTEM: {
    label: 'Scan Filesystem',
    action: 'scan_filesystem',
    group: 'Diagnostics',
    permission: 'root_access',
    defaultData: {
      path: '/var/homepot',
      max_depth: 3,
      include_sizes: true,
    },
    defaultDataByOS: {
      windows: { path: 'C:\\ProgramData\\Homepot' },
    },
    description: 'Scan the system filesystem for files with elevated privileges.',
  },
  SHUT_DOWN: {
    label: 'Shut Down System',
    action: 'shutdown',
    group: 'System',
    permission: 'root_access',
    defaultData: {},
    description: 'Shut down the system the User App runs on. The shutdown begins immediately.',
  },
  DISK_CLEANUP: {
    label: 'Disk Cleanup',
    action: 'disk_cleanup',
    group: 'System',
    permission: 'command_execution',
    defaultData: { max_age_days: 7 },
    description:
      'Clear old temp files and caches from the system temp directory to reclaim disk space.',
  },
  LOCK_SCREEN: {
    label: 'Lock Screen',
    action: 'lock_screen',
    group: 'System',
    permission: 'command_execution',
    defaultData: {},
    description:
      'Lock the terminal\u2019s screen (session lock). The person at the device unlocks it with their credentials.',
  },
  RESTART_SERVICE: {
    label: 'Restart Service',
    action: 'restart_service',
    group: 'Services & Agent',
    permission: 'root_access',
    defaultData: { service_name: 'Spooler' },
    defaultDataByOS: {
      linux: { service_name: 'cron' },
      macos: { service_name: 'com.apple.mDNSResponder' },
    },
    description:
      'Restart a named OS service (Windows service, systemd unit, or launchd label) with root privileges.',
  },
  SET_SERVICE_STATE: {
    label: 'Set Service State',
    action: 'set_service_state',
    group: 'Services & Agent',
    permission: 'root_access',
    defaultData: { service_name: 'Spooler', action: 'start' },
    description:
      'Enable, disable, start, or stop a named OS service (Windows service, systemd unit, or launchd label) with root privileges.',
  },
  NOTIFY_USER: {
    label: 'Notify User',
    action: 'notify_user',
    group: 'Services & Agent',
    permission: 'command_execution',
    defaultData: { title: 'HOMEPOT', message: 'Please reboot the terminal.' },
    description: 'Show a message to the person at the device (operator-to-user channel).',
  },
};

// Display order for the Compose Command dropdown. Templates without a `group`
// (e.g. a future addition, or a stale fallback) are appended under "Other".
const COMMAND_GROUP_ORDER = [
  'Diagnostics',
  'Run Commands',
  'Configuration',
  'Programs',
  'Services & Agent',
  'System',
];

// Group a templates dict by its `group` field into ordered [label, entries] pairs.
function groupedCommandTemplates(templates) {
  const groups = new Map();
  for (const group of COMMAND_GROUP_ORDER) groups.set(group, []);
  const other = [];
  for (const [key, template] of Object.entries(templates || {})) {
    const bucket = groups.get(template.group) || other;
    bucket.push([key, template]);
  }
  const ordered = COMMAND_GROUP_ORDER.map((group) => [group, groups.get(group)]).filter(
    ([, entries]) => entries.length > 0
  );
  if (other.length > 0) ordered.push(['Other', other]);
  return ordered;
}

// A scrollable, searchable command picker. Native <select> dropdowns scroll but
// become unwieldy as the command list grows; this caps the list height, adds a
// search box, and keeps the Diagnostics/Run Commands/… grouping. The list is
// rendered in a portal so it floats above the page's scroll containers instead
// of being clipped by them.
function CommandTypeSelect({ templates, value, onChange }) {
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState('');
  const triggerRef = useRef(null);
  const panelRef = useRef(null);
  const [panelStyle, setPanelStyle] = useState({
    top: 0,
    bottom: null,
    left: 0,
    width: 0,
    maxHeight: 320,
  });

  useEffect(() => {
    if (!open) return;
    function handleClick(event) {
      if (triggerRef.current?.contains(event.target) || panelRef.current?.contains(event.target)) {
        return;
      }
      setOpen(false);
    }
    function handleScroll(event) {
      // Ignore scrolls of the command list itself (otherwise the list closes
      // the moment you try to scroll it); close only when an ancestor scrolls,
      // so the fixed panel never drifts out of position.
      if (event.target instanceof Node && panelRef.current?.contains(event.target)) {
        return;
      }
      setOpen(false);
    }
    document.addEventListener('mousedown', handleClick);
    window.addEventListener('scroll', handleScroll, true);
    window.addEventListener('resize', handleScroll);
    return () => {
      document.removeEventListener('mousedown', handleClick);
      window.removeEventListener('scroll', handleScroll, true);
      window.removeEventListener('resize', handleScroll);
    };
  }, [open]);

  function toggle() {
    if (!open && triggerRef.current) {
      const rect = triggerRef.current.getBoundingClientRect();
      const spaceBelow = window.innerHeight - rect.bottom;
      const spaceAbove = rect.top;
      // Prefer opening downward, but flip upward when there is more room above
      // and not enough below, so the panel never overflows the viewport.
      const openUp = spaceBelow < 200 && spaceAbove > spaceBelow;
      const available = (openUp ? spaceAbove : spaceBelow) - 12;
      setPanelStyle({
        top: openUp ? null : rect.bottom + 4,
        bottom: openUp ? window.innerHeight - rect.top + 4 : null,
        left: rect.left,
        width: rect.width,
        maxHeight: Math.max(120, Math.min(320, available)),
      });
    }
    setOpen((prev) => !prev);
  }

  const groups = groupedCommandTemplates(templates);
  const q = query.trim().toLowerCase();
  const filtered = q
    ? groups
        .map(([group, entries]) => [
          group,
          entries.filter(
            ([key, template]) =>
              template.label.toLowerCase().includes(q) || key.toLowerCase().includes(q)
          ),
        ])
        .filter(([, entries]) => entries.length > 0)
    : groups;

  const selected = templates[value];

  const panel = (
    <div
      ref={panelRef}
      style={{
        position: 'fixed',
        top: panelStyle.top ?? undefined,
        bottom: panelStyle.bottom ?? undefined,
        left: panelStyle.left,
        width: panelStyle.width,
        zIndex: 50,
      }}
      className="rounded-lg border border-[#0e3b3f] bg-[#06181c] shadow-2xl"
    >
      <div className="p-2 border-b border-[#0e2f37]">
        <input
          autoFocus
          type="text"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="Search commands…"
          className="w-full bg-[#0a2b2f] border border-[#0e3b3f] rounded-lg px-2 py-1.5 text-sm text-slate-200 placeholder:text-slate-500 focus:outline-none focus:border-teal-500"
        />
      </div>
      <div
        className="overflow-y-auto custom-scrollbar py-1 pr-2"
        style={{ maxHeight: panelStyle.maxHeight }}
      >
        {filtered.length === 0 ? (
          <div className="px-3 py-2 text-xs text-slate-500">No commands match</div>
        ) : (
          filtered.map(([group, entries]) => (
            <div key={group}>
              <div className="px-3 pt-2 pb-1 text-[10px] uppercase tracking-wider text-slate-500">
                {group}
              </div>
              {entries.map(([key, template]) => (
                <button
                  key={key}
                  type="button"
                  onClick={() => {
                    onChange(key);
                    setOpen(false);
                    setQuery('');
                  }}
                  className={`w-full text-left px-3 py-1.5 text-sm hover:bg-[#0e2f37] ${
                    key === value ? 'text-teal-300' : 'text-slate-200'
                  }`}
                >
                  {template.label}
                </button>
              ))}
            </div>
          ))
        )}
      </div>
    </div>
  );

  return (
    <>
      <button
        ref={triggerRef}
        type="button"
        onClick={toggle}
        className="w-full flex items-center justify-between gap-2 bg-[#0a2b2f] border border-[#0e3b3f] rounded-lg px-3 py-2 text-sm text-slate-200 focus:outline-none focus:border-teal-500 focus:ring-1 focus:ring-teal-500 transition-all"
      >
        <span className="truncate">{selected?.label || 'Select a command'}</span>
        <ChevronDown
          className={`h-4 w-4 shrink-0 text-slate-500 transition-transform ${open ? 'rotate-180' : ''}`}
        />
      </button>
      {open && createPortal(panel, document.body)}
    </>
  );
}

// Map a device's os_details string to a canonical OS family, mirroring the
// backend's homepot.app.schemas.os_capabilities.os_family so command payload
// defaults can be tailored per-OS (e.g. `systeminfo` on Windows vs `uname -a`
// on Linux).
function osFamily(osDetails) {
  if (!osDetails) return null;
  const os = osDetails.toLowerCase();
  if (['windows', 'win32', 'win64'].some((k) => os.includes(k))) return 'windows';
  if (os.includes('android')) return 'android';
  if (['ios', 'ipados', 'iphone os', 'ipad'].some((k) => os.includes(k))) return 'ios';
  if (['linux', 'ubuntu', 'debian', 'fedora', 'centos', 'raspberry pi'].some((k) => os.includes(k)))
    return 'linux';
  if (['macos', 'mac os', 'darwin', 'os x', 'mac'].some((k) => os.includes(k))) return 'macos';
  return null;
}

// Resolve the default command payload for a template, applying any OS-specific
// overrides for the target device.
function resolveDefaultData(templates, templateKey, osDetails) {
  const template = (templates || FALLBACK_COMMAND_TEMPLATES)[templateKey];
  if (!template) return {};
  const base = template.defaultData ?? {};
  const override = template.defaultDataByOS?.[osFamily(osDetails)];
  return override ? { ...base, ...override } : { ...base };
}

const PERMISSION_GROUPS = {
  monitor: {
    label: 'Monitor device',
    keys: ['command_execution', 'filesystem_access', 'process_monitoring', 'network_monitoring'],
  },
  manage: {
    label: 'Manage device',
    keys: ['root_access'],
  },
};
const PERMISSION_TO_GROUP = Object.fromEntries(
  Object.entries(PERMISSION_GROUPS).flatMap(([group, def]) => def.keys.map((key) => [key, group]))
);

function initialTemplate(templates, action) {
  const tpls = templates || FALLBACK_COMMAND_TEMPLATES;
  if (tpls[action]) return action;
  // APPLY_CONFIG and UPDATE_FIRMWARE share the action "update_config"; the
  // reverse lookup collapses them (UPDATE_FIRMWARE won the insertion order),
  // which made reuse of an "Apply Configuration" command show the "Update
  // Firmware" title. Default update_config to APPLY_CONFIG; callers that know
  // the real template pass the template key directly.
  if (action === 'update_config') return 'APPLY_CONFIG';
  const actionToTemplate = Object.fromEntries(
    Object.entries(tpls).map(([key, template]) => [template.action, key])
  );
  return actionToTemplate[action] || 'HEALTH_CHECK';
}

function LifecycleTracker({ commandId, commandType, command, onViewHistory }) {
  const { status, meta, stages, finalStage } = lifecycleStages(command || {});
  const done = status === 'completed' || status === 'failed' || status === 'expired';

  const node = (label, time, doneState, icon) => (
    <div className="flex flex-col items-center gap-1">
      {icon}
      <span className="text-[10px] text-slate-400 whitespace-nowrap">{label}</span>
      <span className="text-[9px] font-mono text-slate-500">
        {time ? new Date(time).toLocaleTimeString() : '—'}
      </span>
    </div>
  );

  const connector = () => <div className="flex-1 h-px bg-slate-700 mx-2 mt-5 min-w-4" />;

  const stageIcons = {
    queued: done ? (
      <CheckCircle2 className="h-5 w-5 shrink-0 text-emerald-400" />
    ) : (
      <Loader2 className="h-5 w-5 shrink-0 text-amber-400 animate-pulse" />
    ),
    acknowledged: done ? (
      <CheckCircle2 className="h-5 w-5 shrink-0 text-emerald-400" />
    ) : (
      <Loader2 className="h-5 w-5 shrink-0 text-amber-400 animate-pulse" />
    ),
    executed: done ? (
      <CheckCircle2 className="h-5 w-5 shrink-0 text-emerald-400" />
    ) : (
      <Loader2 className="h-5 w-5 shrink-0 text-amber-400 animate-pulse" />
    ),
  };

  const finalIcon = done ? (
    finalStage.label === 'Failed' || finalStage.label === 'Expired' ? (
      <XCircle className="h-5 w-5 shrink-0 text-red-400" />
    ) : (
      <CheckCircle2 className="h-5 w-5 shrink-0 text-emerald-400" />
    )
  ) : (
    <Loader2 className="h-5 w-5 shrink-0 text-blue-400 animate-spin" />
  );

  return (
    <div className="shrink-0 bg-[#06181c] border border-[#0e2f37] rounded-xl p-4 mb-4">
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center gap-2">
          <Clock className="h-4 w-4 text-teal-400" />
          <span className="text-xs font-medium text-teal-100">
            Lifecycle — {formatCommandType(commandType)}
          </span>
          <span className="font-mono text-[10px] text-slate-500">{commandId.substring(0, 8)}</span>
        </div>
        <span
          className={`text-[10px] px-2 py-0.5 rounded-full border font-medium ${meta.color} ${meta.bg} ${meta.border}`}
        >
          {meta.label.toUpperCase()}
        </span>
      </div>

      <div className="flex items-start">
        {stages.map((stage) => (
          <span key={stage.key} className="flex items-center flex-1">
            {node(stage.label, stage.time, stage.done, stageIcons[stage.key])}
            {connector()}
          </span>
        ))}
        <span className="flex items-center flex-1">
          {node(finalStage.label, finalStage.time, finalStage.done, finalIcon)}
        </span>
      </div>

      <div className="flex items-center justify-between mt-3">
        <p className="text-[10px] text-slate-400">{meta.description}</p>
        <button
          onClick={onViewHistory}
          className="text-[10px] text-teal-400 hover:text-teal-300 font-medium"
        >
          View in Push History →
        </button>
      </div>
    </div>
  );
}

export default function PushReview() {
  const { id } = useParams();
  const navigate = useNavigate();
  const { user } = useAuth();
  const location = useLocation();
  const [sending, setSending] = useState(false);
  const [loading, setLoading] = useState(true);
  const [device, setDevice] = useState(null);
  const [toast, setToast] = useState(null);

  // Compose Command templates: prefer the backend's (single source of truth),
  // fall back to the bundled copy while loading or if the fetch fails.
  const [templates, setTemplates] = useState(FALLBACK_COMMAND_TEMPLATES);

  // State for the Command Builder
  // Initialize from location state if available
  const [selectedCommand, setSelectedCommand] = useState(
    initialTemplate(FALLBACK_COMMAND_TEMPLATES, location.state?.initialCommand)
  );
  const [commandData, setCommandData] = useState(
    location.state?.initialData
      ? typeof location.state.initialData === 'string'
        ? location.state.initialData
        : JSON.stringify(location.state.initialData, null, 2)
      : JSON.stringify(FALLBACK_COMMAND_TEMPLATES['HEALTH_CHECK'].defaultData, null, 2)
  );
  const [jsonError, setJsonError] = useState(null);
  const [trackingCommandId, setTrackingCommandId] = useState(null);
  const [trackingCommandType, setTrackingCommandType] = useState(null);
  const [trackingData, setTrackingData] = useState(null);

  // Ref to track if we are initializing from reuse
  const isReuseInit = useRef(!!location.state?.initialData);
  // Ref to track previous command to allow intentional changes
  const prevCommand = useRef(selectedCommand);

  // State for the Notification Envelope
  const [payloadConfig, setPayloadConfig] = useState({
    title: 'Health Check',
    body: '',
    priority: 'high',
    ttl: 300,
  });

  useEffect(() => {
    let active = true;
    const fetchDevice = async () => {
      try {
        const deviceData = await api.devices.getDeviceById(id);
        if (active) setDevice(deviceData);
      } catch (err) {
        console.error('Failed to load device:', err);
      } finally {
        if (active) setLoading(false);
      }
    };
    fetchDevice();
    const interval = setInterval(fetchDevice, 5000);
    return () => {
      active = false;
      clearInterval(interval);
    };
  }, [id]);

  // Update body/title when command or device changes
  useEffect(() => {
    if (device) {
      setPayloadConfig((prev) => ({
        ...prev,
        title: templates[selectedCommand]?.label || 'Custom Command',
        body: `Executing ${selectedCommand} on ${device.name}`,
      }));
    }
  }, [selectedCommand, device, templates]);

  // Handle Command Template Changes
  useEffect(() => {
    // If this is the first run and we are reusing data, DO NOT reset commandData
    if (isReuseInit.current) {
      isReuseInit.current = false; // Clear the flag so subsequent changes DO reset
      prevCommand.current = selectedCommand;
      return;
    }

    // Only reset if command type ACTUALLY changed
    if (prevCommand.current !== selectedCommand) {
      if (templates[selectedCommand]) {
        setCommandData(
          JSON.stringify(
            resolveDefaultData(templates, selectedCommand, device?.os_details),
            null,
            2
          )
        );
      } else {
        setCommandData('{}');
      }
      setJsonError(null);
      prevCommand.current = selectedCommand;
    }
  }, [selectedCommand, device?.os_details, templates]);

  // Fetch Compose Command templates from the backend (single source of truth),
  // falling back to the bundled copy on failure.
  useEffect(() => {
    let active = true;
    (async () => {
      try {
        const res = await api.ai.getComposeTemplates?.();
        const fetched = res?.templates;
        if (active && fetched && Object.keys(fetched).length > 0) {
          setTemplates(fetched);
        }
      } catch {
        // Keep fallback templates; nothing to do.
      }
    })();
    return () => {
      active = false;
    };
  }, []);

  const handleDataChange = (value) => {
    setCommandData(value);
    try {
      JSON.parse(value);
      setJsonError(null);
    } catch {
      setJsonError('Invalid JSON format');
    }
  };

  // Construct the live payload
  let parsedData = {};
  try {
    parsedData = JSON.parse(commandData);
  } catch {
    parsedData = { error: 'Invalid JSON' };
  }

  const template = templates[selectedCommand];
  // Simulators expect the extra envelope keys (command/timestamp/config_url/
  // config_version) inside `data`. Real devices treat them as unknown config
  // keys, so only send them to simulated targets; otherwise every update_config
  // result is padded with "no OS action defined" entries.
  const isSimulator = device?.is_simulated === true || device?.device_source === 'emulator';
  const requiredPermissions = [template?.permission].filter(Boolean);
  const missingPermissions = requiredPermissions.filter(
    (permission) => !device?.device_permissions?.[permission]
  );

  // Owner-facing groups required / missing for this command (ties the
  // Dashboard's request/approval to the User App's two toggles).
  const requiredGroups = [...new Set(requiredPermissions.map((p) => PERMISSION_TO_GROUP[p]))];
  const missingGroups = requiredGroups.filter((group) =>
    PERMISSION_GROUPS[group].keys.some((key) => !device?.device_permissions?.[key])
  );
  const groupLabel = (group) => PERMISSION_GROUPS[group].label;

  const payloadPreview = {
    title: payloadConfig.title,
    body: payloadConfig.body,
    data: {
      ...(isSimulator ? { command: selectedCommand, timestamp: new Date().toISOString() } : {}),
      ...parsedData,
    },
    priority: payloadConfig.priority,
    ttl_seconds: payloadConfig.ttl,
    collapse_key: selectedCommand.toLowerCase(),
  };

  // Build the payload once so the preview below is exactly what handleSend
  // queues: the envelope, simulator-only fields, and the action/verb that
  // selects the agent's Python branch (all templates with empty parameters
  // still need this — e.g. SHUT_DOWN -> action "shutdown").
  const finalPayload = {
    ...payloadPreview,
    action: template.action,
    data: {
      ...payloadPreview.data,
      ...(isSimulator
        ? {
            config_url: payloadPreview.data.url || 'https://config.homepot.io/v1/config.json',
            config_version: payloadPreview.data.version || '1.0.1',
          }
        : {}),
    },
  };

  const handleSend = async () => {
    if (jsonError) return;
    setSending(true);

    try {
      const action = template.action;
      const response = await api.devices.triggerAction(id, action, finalPayload, user?.email);
      const commandId = response.command_id;
      setTrackingCommandId(commandId);
      setTrackingCommandType(action);
      setTrackingData(null);
    } catch (err) {
      console.error('Failed to send push:', err);
      setToast({
        message: `Failed to queue command: ${err.message || 'Unknown error'}`,
        type: 'error',
      });
    } finally {
      setSending(false);
    }
  };

  // Poll the command lifecycle after queueing, then hand off to the history page
  useEffect(() => {
    if (!trackingCommandId) return;
    let active = true;
    let attempts = 0;
    const interval = setInterval(async () => {
      if (!active) return;
      attempts += 1;
      try {
        const history = await api.devices.getCommands(id, 10);
        const cmd = history.find((c) => c.command_id === trackingCommandId);
        if (cmd) {
          setTrackingData(cmd);
          const done =
            cmd.status === 'completed' || cmd.status === 'failed' || cmd.status === 'expired';
          if (done) {
            clearInterval(interval);
            setTimeout(() => {
              if (active) navigate(`/device/${id}/history`);
            }, 1500);
          }
        }
      } catch (pollErr) {
        console.debug('Lifecycle poll skipped', pollErr);
      }
      if (attempts >= 30) clearInterval(interval);
    }, 2000);
    return () => {
      active = false;
      clearInterval(interval);
    };
  }, [trackingCommandId, id, navigate]);

  const handleRequestAccess = async () => {
    setSending(true);
    try {
      for (const permission of missingPermissions) {
        await api.devices.requestPermission(id, permission);
      }
      setToast({ message: 'Access request sent to the device owner.', type: 'success' });
    } catch (err) {
      setToast({
        message: err.response?.data?.detail?.message || err.message || 'Access request failed',
        type: 'error',
      });
    } finally {
      setSending(false);
    }
  };

  if (loading)
    return <div className="h-full flex items-center justify-center text-slate-400">Loading...</div>;

  return (
    <div className="h-full bg-gradient-to-b from-[#041014] to-[#03121a] text-slate-200 p-2 font-sans flex flex-col overflow-hidden">
      {toast && <Toast message={toast.message} type={toast.type} onClose={() => setToast(null)} />}
      <div className="max-w-content mx-auto w-full h-full flex flex-col">
        {/* Header */}
        <div className="shrink-0 flex items-center justify-between mb-4">
          <div className="flex items-center gap-4">
            <Button
              variant="ghost"
              onClick={() => navigate(`/device/${id}/history`)}
              className="pl-0 hover:pl-1 transition-all text-gray-400 hover:text-white hover:bg-transparent"
            >
              <ArrowLeft className="h-4 w-4 mr-2" />
              Back to Push History
            </Button>
            <div>
              <h1 className="text-xl font-semibold tracking-tight">Compose Command</h1>
              <div className="text-xs text-slate-400">
                Target: <span className="text-teal-400">{device?.name}</span> ({id})
              </div>
            </div>
          </div>
          <Button
            onClick={missingGroups.length ? handleRequestAccess : handleSend}
            disabled={sending || !!jsonError}
            className={`px-4 h-9 ${jsonError ? 'bg-slate-700 cursor-not-allowed' : 'bg-teal-600 hover:bg-teal-500 text-white'}`}
          >
            {sending ? (
              'Sending...'
            ) : (
              <>
                {missingGroups.length ? (
                  <>
                    <ShieldAlert className="h-4 w-4 mr-2" />
                    Request Access
                  </>
                ) : (
                  <>
                    <Rocket className="h-4 w-4 mr-2" />
                    Queue Command
                  </>
                )}
              </>
            )}
          </Button>
        </div>

        {/* Live Command Lifecycle Tracker */}
        {trackingCommandId && (
          <LifecycleTracker
            commandId={trackingCommandId}
            commandType={trackingCommandType}
            command={trackingData}
            onViewHistory={() => navigate(`/device/${id}/history`)}
          />
        )}

        <div className="grid grid-cols-1 lg:grid-cols-2 gap-4 flex-1 min-h-0 overflow-hidden">
          {/* Left Column: Command Builder */}
          <div className="h-full overflow-y-auto pr-1">
            <div className="bg-[#06181c] border border-[#0e2f37] rounded-xl p-4 h-full flex flex-col">
              <div className="flex items-center gap-2 mb-4 shrink-0">
                <Terminal className="h-5 w-5 text-teal-400" />
                <h2 className="text-md font-medium text-teal-100">Command Configuration</h2>
              </div>

              <div className="space-y-4 flex-1">
                {/* Command Selector */}
                <div>
                  <label className="block text-xs text-slate-400 mb-1 uppercase tracking-wider">
                    Command Type
                  </label>
                  <div className="grid grid-cols-1 gap-1">
                    <CommandTypeSelect
                      templates={templates}
                      value={selectedCommand}
                      onChange={setSelectedCommand}
                    />
                    <p className="text-[10px] text-slate-500 mt-1">
                      {templates[selectedCommand]?.description || 'Custom command'}
                    </p>
                  </div>
                </div>

                <div
                  className={`border rounded-lg px-3 py-2 text-xs ${
                    missingGroups.length
                      ? 'border-amber-700/60 bg-amber-950/30 text-amber-300'
                      : 'border-emerald-700/50 bg-emerald-950/20 text-emerald-300'
                  }`}
                >
                  Required: {requiredGroups.map(groupLabel).join(' + ')}
                  {missingGroups.length > 0 &&
                    ` — awaiting device-owner approval for ${missingGroups.map(groupLabel).join(' + ')}`}
                </div>

                {/* JSON Data Editor */}
                <div className="space-y-1">
                  <div className="flex items-center justify-between">
                    <label className="block text-xs text-slate-400 uppercase tracking-wider">
                      Command Parameters (JSON)
                    </label>
                    {jsonError && (
                      <span className="text-xs text-red-400 flex items-center gap-1">
                        <AlertTriangle className="h-3 w-3" /> Invalid JSON
                      </span>
                    )}
                  </div>
                  <div className="relative">
                    <textarea
                      value={commandData}
                      onChange={(e) => handleDataChange(e.target.value)}
                      className={`w-full bg-[#020817] border ${jsonError ? 'border-red-500/50' : 'border-[#0e3b3f]'} rounded-lg px-3 py-2 text-xs font-mono text-blue-300 focus:outline-none focus:border-teal-500 transition-all h-48 resize-none leading-relaxed`}
                      spellCheck="false"
                    />
                  </div>
                </div>

                {/* Notification Envelope Settings */}
                <div className="pt-3 border-t border-[#0e2f37] space-y-3">
                  <h3 className="text-xs font-medium text-slate-500 uppercase tracking-wider flex items-center gap-2">
                    <MessageSquare className="h-3 w-3" /> Notification Envelope
                  </h3>
                  <div className="grid grid-cols-2 gap-3">
                    <div className="col-span-2">
                      <label className="block text-[10px] text-slate-400 mb-1">Title</label>
                      <input
                        type="text"
                        value={payloadConfig.title}
                        onChange={(e) =>
                          setPayloadConfig((prev) => ({ ...prev, title: e.target.value }))
                        }
                        className="w-full bg-[#0a2b2f] border border-[#0e3b3f] rounded-lg px-2 py-1.5 text-sm text-slate-200 focus:outline-none focus:border-teal-500"
                      />
                    </div>
                    <div>
                      <label className="block text-[10px] text-slate-400 mb-1">Priority</label>
                      <select
                        value={payloadConfig.priority}
                        onChange={(e) =>
                          setPayloadConfig((prev) => ({ ...prev, priority: e.target.value }))
                        }
                        className="w-full bg-[#0a2b2f] border border-[#0e3b3f] rounded-lg px-2 py-1.5 text-sm text-slate-200 focus:outline-none focus:border-teal-500"
                      >
                        <option value="high">High (Immediate)</option>
                        <option value="normal">Normal</option>
                      </select>
                    </div>
                    <div>
                      <label className="block text-[10px] text-slate-400 mb-1">TTL (Seconds)</label>
                      <input
                        type="number"
                        value={payloadConfig.ttl}
                        onChange={(e) =>
                          setPayloadConfig((prev) => ({ ...prev, ttl: parseInt(e.target.value) }))
                        }
                        className="w-full bg-[#0a2b2f] border border-[#0e3b3f] rounded-lg px-2 py-1.5 text-sm text-slate-200 focus:outline-none focus:border-teal-500"
                      />
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </div>

          {/* Right Column: JSON Payload Preview */}
          <div className="h-full min-h-0">
            <div className="bg-[#020817] border border-[#1e293b] rounded-xl overflow-hidden flex flex-col h-full">
              <div className="bg-[#0f172a] px-4 py-3 border-b border-[#1e293b] flex items-center justify-between shrink-0">
                <div className="flex items-center gap-2">
                  <FileJson className="h-4 w-4 text-blue-400" />
                  <span className="text-sm font-medium text-slate-300">Final Payload Preview</span>
                </div>
                <div className="flex items-center gap-2">
                  <span className="text-xs text-slate-500">Live</span>
                </div>
              </div>

              <div className="p-4 overflow-auto flex-1 min-h-0">
                <pre className="font-mono text-xs text-blue-300 leading-relaxed">
                  {JSON.stringify(
                    { command_type: template.action, payload: finalPayload },
                    null,
                    2
                  )}
                </pre>
              </div>

              <div className="bg-[#0f172a]/50 px-4 py-3 border-t border-[#1e293b] shrink-0">
                <p className="text-xs text-slate-500">
                  This request is queued for the device. The agent switches on{' '}
                  <code>command_type</code> and returns a JSON result.
                </p>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
