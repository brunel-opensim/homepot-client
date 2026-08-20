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
    permission: 'command_execution',
    defaultData: { command: 'uname -a', run_as_root: false, timeout_seconds: 30 },
    description: 'Run one executable with arguments. Shell operators are not interpreted.',
  },
  RUN_SCRIPT: {
    label: 'Run Script',
    action: 'run_script',
    permission: 'command_execution',
    defaultData: { script: '#!/bin/sh\nid', run_as_root: false, timeout_seconds: 30 },
    description: 'Run a POSIX shell script supplied through standard input.',
  },
  APPLY_CONFIG: {
    label: 'Apply Configuration',
    action: 'update_pos_payment_config',
    permission: 'filesystem_access',
    defaultData: {
      volume: 50,
      brightness: 75,
      kiosk_mode: true,
      maintenance_window: '02:00-04:00',
    },
    description: 'Update device settings like volume, brightness, or app preferences.',
  },
  REBOOT_DEVICE: {
    label: 'Reboot Device',
    action: 'restart_pos_app',
    permission: 'command_execution',
    defaultData: {
      delay_seconds: 10,
      reason: 'Scheduled maintenance',
    },
    description: 'Restart the device operating system.',
  },
  UPDATE_FIRMWARE: {
    label: 'Update Firmware',
    action: 'update_pos_payment_config',
    permission: 'filesystem_access',
    defaultData: {
      version: '2.4.0',
      url: 'https://firmware.homepot.io/v2.4.0.bin',
      checksum: 'sha256:...',
    },
    description: 'Download and install a new system image.',
  },
  RUN_DIAGNOSTICS: {
    label: 'Run Diagnostics',
    action: 'health_check',
    permission: 'command_execution',
    defaultData: {
      tests: ['network', 'storage', 'memory'],
      upload_logs: true,
    },
    description: 'Execute self-tests and report status.',
  },
};

const PERMISSION_LABELS = {
  command_execution: 'Command & Script Execution',
  filesystem_access: 'File System Access',
  root_access: 'Root / Full Access',
};

const ACTION_TO_TEMPLATE = Object.fromEntries(
  Object.entries(COMMAND_TEMPLATES).map(([key, template]) => [template.action, key])
);

function initialTemplate(action) {
  if (COMMAND_TEMPLATES[action]) return action;
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
        setCommandData(JSON.stringify(COMMAND_TEMPLATES[selectedCommand].defaultData, null, 2));
      } else {
        setCommandData('{}');
      }
      setJsonError(null);
      prevCommand.current = selectedCommand;
    }
  }, [selectedCommand]); // Only dependency is selectedCommand

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
  const requiredPermissions = [
    template?.permission,
    ...(parsedData.run_as_root ? ['root_access'] : []),
  ].filter(Boolean);
  const missingPermissions = requiredPermissions.filter(
    (permission) => !device?.device_permissions?.[permission]
  );

  const payloadPreview = {
    title: payloadConfig.title,
    body: payloadConfig.body,
    data: {
      command: selectedCommand,
      timestamp: new Date().toISOString(),
      ...parsedData,
    },
    priority: payloadConfig.priority,
    ttl_seconds: payloadConfig.ttl,
    collapse_key: selectedCommand.toLowerCase(),
  };

  const handleSend = async () => {
    if (jsonError) return;
    setSending(true);

    try {
      const action = template.action;

      // Ensure data has required fields for the agent simulator
      const finalPayload = {
        ...payloadPreview,
        action: action,
        data: {
          ...payloadPreview.data,
          config_url: payloadPreview.data.url || 'https://config.homepot.io/v1/config.json',
          config_version: payloadPreview.data.version || '1.0.1',
        },
      };

      const response = await api.devices.triggerAction(id, action, finalPayload);
      const commandId = response.command_id;
      setTrackingCommandId(commandId);
      setTrackingCommandType(action);
      setTrackingData(null);

      setToast({
        message: `Command queued (${commandId.substring(0, 8)}…) — tracking lifecycle`,
        type: 'success',
      });
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
            setToast({
              message: `Command ${cmd.status.toUpperCase()} — ${cmd.command_id.substring(0, 8)}`,
              type: cmd.status === 'completed' ? 'success' : 'error',
            });
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
      <div className="max-w-7xl mx-auto w-full h-full flex flex-col">
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
            onClick={missingPermissions.length ? handleRequestAccess : handleSend}
            disabled={sending || !!jsonError}
            className={`px-4 h-9 ${jsonError ? 'bg-slate-700 cursor-not-allowed' : 'bg-teal-600 hover:bg-teal-500 text-white'}`}
          >
            {sending ? (
              'Sending...'
            ) : (
              <>
                {missingPermissions.length ? (
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
                    missingPermissions.length
                      ? 'border-amber-700/60 bg-amber-950/30 text-amber-300'
                      : 'border-emerald-700/50 bg-emerald-950/20 text-emerald-300'
                  }`}
                >
                  Required: {requiredPermissions.map((key) => PERMISSION_LABELS[key]).join(' + ')}
                  {missingPermissions.length > 0 && ' — awaiting device-owner approval'}
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
                  {JSON.stringify(payloadPreview, null, 2)}
                </pre>
              </div>

              <div className="bg-[#0f172a]/50 px-4 py-3 border-t border-[#1e293b] shrink-0">
                <p className="text-xs text-slate-500">
                  This payload will be sent to the device via FCM/APNs. The device agent will
                  intercept the <code>{selectedCommand}</code> command.
                </p>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
