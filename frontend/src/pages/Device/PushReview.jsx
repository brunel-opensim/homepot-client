import { Button } from '@/components/ui/button';
import { Toast } from '@/components/ui/Toast';
import api from '@/services/api';
import { lifecycleStages, formatCommandType } from '@/utils/commandLifecycle';
// Cleaned up unused imports that were causing blank page errors
import {
  AlertTriangle,
  ArrowLeft,
  CheckCircle2,
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
import { useNavigate, useParams, useLocation } from 'react-router-dom';

// Predefined templates for common commands
const COMMAND_TEMPLATES = {
  RUN_COMMAND: {
    label: 'Run Command',
    action: 'run_command',
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
    permission: 'root_access',
    defaultData: { script: '#!/bin/sh\nid', timeout_seconds: 30 },
    defaultDataByOS: {
      windows: { script: 'Get-Process | Select-Object -First 5 Name, Id, CPU' },
    },
    description:
      'Run a script with elevated privileges using the target device\u2019s shell (PowerShell on Windows, POSIX sh on macOS/Linux).',
  },
  APPLY_CONFIG: {
    label: 'Apply Configuration',
    action: 'update_config',
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
    permission: 'root_access',
    defaultData: {},
    description: 'Reboot the system the User App runs on. The reboot begins immediately.',
  },
  UPDATE_FIRMWARE: {
    label: 'Update Firmware',
    action: 'update_config',
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
    permission: 'root_access',
    defaultData: {
      path: 'C:\\Program Files\\App\\app.exe',
      args: [],
    },
    description:
      'Launch a program on the device in the background. Provide an absolute path (or a name on PATH) and optional arguments.',
  },
  STOP_PROGRAM: {
    label: 'Stop Program',
    action: 'stop_program',
    permission: 'root_access',
    defaultData: {
      name: 'app.exe',
      force: false,
    },
    description:
      'Stop a running process by name or PID. Set force to terminate immediately. Critical system processes are never stopped.',
  },
  INSTALL_PROGRAM: {
    label: 'Install Program',
    action: 'install_program',
    permission: 'root_access',
    defaultData: { package: 'Notepad++.Notepad++', timeout_seconds: 300 },
    description: 'Install a program on the Windows device via winget (silent, machine-wide).',
  },
  UNINSTALL_PROGRAM: {
    label: 'Uninstall Program',
    action: 'uninstall_program',
    permission: 'root_access',
    defaultData: { package: 'Notepad++.Notepad++', timeout_seconds: 300 },
    description: 'Uninstall a program from the Windows device via winget (silent).',
  },
  LIST_INSTALLED_PROGRAMS: {
    label: 'List Installed Programs',
    action: 'list_installed_programs',
    permission: 'command_execution',
    defaultData: {},
    description: 'List the programs installed on the Windows device via winget.',
  },
  UPDATE_PROGRAM: {
    label: 'Update Program',
    action: 'update_program',
    permission: 'root_access',
    defaultData: { package: 'Notepad++.Notepad++', timeout_seconds: 300 },
    description: 'Update a program on the Windows device via winget (silent).',
  },
  UPGRADE_ALL_PROGRAMS: {
    label: 'Upgrade All Programs',
    action: 'upgrade_all_programs',
    permission: 'root_access',
    defaultData: { timeout_seconds: 600 },
    description: 'Upgrade all installed programs on the Windows device via winget (silent).',
  },
  RUN_DIAGNOSTICS: {
    label: 'Run Diagnostics',
    action: 'health_check',
    permission: 'command_execution',
    defaultData: {
      tests: ['network', 'storage', 'memory'],
    },
    description: 'Execute self-tests (network/storage/memory) and report pass/fail.',
  },
  LIST_PROCESSES: {
    label: 'List Processes',
    action: 'list_processes',
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
    permission: 'network_monitoring',
    defaultData: {
      filter_state: 'ESTABLISHED',
      limit: 100,
    },
    description: 'List the device\u2019s active network connections.',
  },
  SCAN_FILESYSTEM: {
    label: 'Scan Filesystem',
    action: 'scan_filesystem',
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
    permission: 'root_access',
    defaultData: {},
    description: 'Shut down the system the User App runs on. The shutdown begins immediately.',
  },
};

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
function resolveDefaultData(templateKey, osDetails) {
  const template = COMMAND_TEMPLATES[templateKey];
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

const ACTION_TO_TEMPLATE = Object.fromEntries(
  Object.entries(COMMAND_TEMPLATES).map(([key, template]) => [template.action, key])
);

function initialTemplate(action) {
  if (COMMAND_TEMPLATES[action]) return action;
  // APPLY_CONFIG and UPDATE_FIRMWARE share the action "update_config"; the
  // reverse lookup collapses them (UPDATE_FIRMWARE won the insertion order),
  // which made reuse of an "Apply Configuration" command show the "Update
  // Firmware" title. Default update_config to APPLY_CONFIG; callers that know
  // the real template pass the template key directly.
  if (action === 'update_config') return 'APPLY_CONFIG';
  return ACTION_TO_TEMPLATE[action] || 'APPLY_CONFIG';
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
  const location = useLocation();
  const [sending, setSending] = useState(false);
  const [loading, setLoading] = useState(true);
  const [device, setDevice] = useState(null);
  const [toast, setToast] = useState(null);

  // State for the Command Builder
  // Initialize from location state if available
  const [selectedCommand, setSelectedCommand] = useState(
    initialTemplate(location.state?.initialCommand)
  );
  const [commandData, setCommandData] = useState(
    location.state?.initialData
      ? typeof location.state.initialData === 'string'
        ? location.state.initialData
        : JSON.stringify(location.state.initialData, null, 2)
      : JSON.stringify(COMMAND_TEMPLATES['APPLY_CONFIG'].defaultData, null, 2)
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
    title: 'Configuration Update',
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
        title: COMMAND_TEMPLATES[selectedCommand]?.label || 'Custom Command',
        body: `Executing ${selectedCommand} on ${device.name}`,
      }));
    }
  }, [selectedCommand, device]);

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
      if (COMMAND_TEMPLATES[selectedCommand]) {
        setCommandData(
          JSON.stringify(resolveDefaultData(selectedCommand, device?.os_details), null, 2)
        );
      } else {
        setCommandData('{}');
      }
      setJsonError(null);
      prevCommand.current = selectedCommand;
    }
  }, [selectedCommand, device?.os_details]);

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

  const template = COMMAND_TEMPLATES[selectedCommand];
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
      const response = await api.devices.triggerAction(id, action, finalPayload);
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
                    <select
                      value={selectedCommand}
                      onChange={(e) => setSelectedCommand(e.target.value)}
                      className="w-full bg-[#0a2b2f] border border-[#0e3b3f] rounded-lg px-3 py-2 text-sm text-slate-200 focus:outline-none focus:border-teal-500 focus:ring-1 focus:ring-teal-500 transition-all"
                    >
                      {Object.entries(COMMAND_TEMPLATES).map(([key, template]) => (
                        <option key={key} value={key}>
                          {template.label} ({key})
                        </option>
                      ))}
                    </select>
                    <p className="text-[10px] text-slate-500 mt-1">
                      {COMMAND_TEMPLATES[selectedCommand]?.description || 'Custom command'}
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
