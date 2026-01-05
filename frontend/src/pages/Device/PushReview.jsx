import { Button } from '@/components/ui/button';
import { Toast } from '@/components/ui/Toast';
import api from '@/services/api';
import {
  AuditWidget,
  CommandHistoryWidget,
  DeviceActionsWidget,
  DirectConnectWidget,
  LogsWidget,
  StatBlock,
} from './DeviceWidgets';
import { AlertTriangle, ArrowLeft, FileJson, MessageSquare, Rocket, Terminal } from 'lucide-react';
import React, { useEffect, useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';

// Predefined templates for common commands
const COMMAND_TEMPLATES = {
  APPLY_CONFIG: {
    label: 'Apply Configuration',
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
    defaultData: {
      delay_seconds: 10,
      reason: 'Scheduled maintenance',
    },
    description: 'Restart the device operating system.',
  },
  UPDATE_FIRMWARE: {
    label: 'Update Firmware',
    defaultData: {
      version: '2.4.0',
      url: 'https://firmware.homepot.io/v2.4.0.bin',
      checksum: 'sha256:...',
    },
    description: 'Download and install a new system image.',
  },
  RUN_DIAGNOSTICS: {
    label: 'Run Diagnostics',
    defaultData: {
      tests: ['network', 'storage', 'memory'],
      upload_logs: true,
    },
    description: 'Execute self-tests and report status.',
  },
  CUSTOM: {
    label: 'Custom Command',
    defaultData: {},
    description: 'Send a raw command payload.',
  },
};

export default function PushReview() {
  const { id } = useParams();
  const navigate = useNavigate();
  const [sending, setSending] = useState(false);
  const [loading, setLoading] = useState(true);
  const [device, setDevice] = useState(null);
  const [toast, setToast] = useState(null);

  // State for the Command Builder
  const [selectedCommand, setSelectedCommand] = useState('APPLY_CONFIG');
  const [commandData, setCommandData] = useState(
    JSON.stringify(COMMAND_TEMPLATES['APPLY_CONFIG'].defaultData, null, 2)
  );
  const [jsonError, setJsonError] = useState(null);

  // State for the Notification Envelope
  const [payloadConfig, setPayloadConfig] = useState({
    title: 'Configuration Update',
    body: '',
    priority: 'high',
    ttl: 300,
  });

  useEffect(() => {
    const fetchDevice = async () => {
      try {
        const deviceData = await api.devices.getDeviceById(id);
        setDevice(deviceData);
        setPayloadConfig((prev) => ({
          ...prev,
          body: `Executing ${selectedCommand} on ${deviceData.name}`,
        }));
      } catch (err) {
        console.error('Failed to load device:', err);
      } finally {
        setLoading(false);
      }
    };
    fetchDevice();
  }, [id]);

  // Update body when command changes
  useEffect(() => {
    if (device) {
      setPayloadConfig((prev) => ({
        ...prev,
        title: COMMAND_TEMPLATES[selectedCommand].label,
        body: `Executing ${selectedCommand} on ${device.name}`,
      }));
    }
    // Reset data to template default when command type changes
    setCommandData(JSON.stringify(COMMAND_TEMPLATES[selectedCommand].defaultData, null, 2));
    setJsonError(null);
  }, [selectedCommand, device]);

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
      // Send the push notification via API
      // We map the selected command to the action expected by the agent
      let action = 'unknown';
      if (selectedCommand === 'APPLY_CONFIG') action = 'update_pos_payment_config';
      else if (selectedCommand === 'REBOOT_DEVICE') action = 'restart_pos_app';
      else if (selectedCommand === 'RUN_DIAGNOSTICS') action = 'health_check';
      else if (selectedCommand === 'UPDATE_FIRMWARE') action = 'update_pos_payment_config'; // Reuse config update for firmware sim

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

      const response = await api.agents.sendPush(id, finalPayload);

      // Check if the agent reported an error
      if (response.response && response.response.status === 'error') {
        throw new Error(response.response.message || 'Agent reported an internal error');
      }

      // Check for warnings (e.g. DB log failure)
      if (response.response && response.response.warning) {
        setToast({
          message: `Success, but DB Log Failed: ${response.response.warning}`,
          type: 'error',
        });
        return; // Stay on page to show error
      }

      const jobId = response.response?.device_id
        ? `job-${response.response.device_id.substring(0, 8)}`
        : `job-${Math.random().toString(36).substr(2, 8)}`;

      setToast({
        message: `Command Sent Successfully! Job ID: ${jobId}`,
        type: 'success',
      });

      setTimeout(() => {
        navigate(`/device/${id}/settings`);
      }, 1500);
    } catch (err) {
      console.error('Failed to send push:', err);
      setToast({
        message: `Failed to send command: ${err.message || 'Unknown error'}`,
        type: 'error',
      });
    } finally {
      setSending(false);
    }
  };

  if (loading) return <div className="p-10 text-center text-slate-400">Loading...</div>;

  return (
    <div className="min-h-screen bg-gradient-to-b from-[#041014] to-[#03121a] text-slate-200 p-6 sm:p-10 font-sans">
      {toast && <Toast message={toast.message} type={toast.type} onClose={() => setToast(null)} />}
      <div className="max-w-6xl mx-auto">
        {/* Header */}
        <div className="flex items-center justify-between mb-8">
          <div className="flex items-center gap-4">
            <Button
              variant="ghost"
              onClick={() => navigate(`/device/${id}`)}
              className="pl-0 hover:pl-1 transition-all text-gray-400 hover:text-white hover:bg-transparent"
            >
              <ArrowLeft className="h-4 w-4 mr-2" />
              Back to Device
            </Button>
            <div>
              <h1 className="text-2xl font-semibold tracking-tight">Compose Command</h1>
              <div className="text-sm text-slate-400">
                Target: <span className="text-teal-400">{device?.name}</span> ({id})
              </div>
            </div>
          </div>
          <Button
            onClick={handleSend}
            disabled={sending || !!jsonError}
            className={`px-6 ${jsonError ? 'bg-slate-700 cursor-not-allowed' : 'bg-teal-600 hover:bg-teal-500 text-white'}`}
          >
            {sending ? (
              'Sending...'
            ) : (
              <>
                <Rocket className="h-4 w-4 mr-2" />
                Push Command
              </>
            )}
          </Button>
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
          {/* Left Column: Command Builder */}
          <div className="space-y-6">
            <div className="bg-[#06181c] border border-[#0e2f37] rounded-xl p-6">
              <div className="flex items-center gap-2 mb-6">
                <Terminal className="h-5 w-5 text-teal-400" />
                <h2 className="text-lg font-medium text-teal-100">Command Configuration</h2>
              </div>

              <div className="space-y-6">
                {/* Command Selector */}
                <div>
                  <label className="block text-xs text-slate-400 mb-1.5 uppercase tracking-wider">
                    Command Type
                  </label>
                  <div className="grid grid-cols-1 gap-2">
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
                    <p className="text-xs text-slate-500 mt-1">
                      {COMMAND_TEMPLATES[selectedCommand].description}
                    </p>
                  </div>
                </div>

                {/* JSON Data Editor */}
                <div className="space-y-2">
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
                      className={`w-full bg-[#020817] border ${jsonError ? 'border-red-500/50' : 'border-[#0e3b3f]'} rounded-lg px-4 py-3 text-sm font-mono text-blue-300 focus:outline-none focus:border-teal-500 transition-all h-64 resize-none leading-relaxed`}
                      spellCheck="false"
                    />
                  </div>
                </div>

                {/* Notification Envelope Settings */}
                <div className="pt-4 border-t border-[#0e2f37] space-y-4">
                  <h3 className="text-xs font-medium text-slate-500 uppercase tracking-wider flex items-center gap-2">
                    <MessageSquare className="h-3 w-3" /> Notification Envelope
                  </h3>
                  <div className="grid grid-cols-2 gap-4">
                    <div className="col-span-2">
                      <label className="block text-xs text-slate-400 mb-1.5">Title</label>
                      <input
                        type="text"
                        value={payloadConfig.title}
                        onChange={(e) =>
                          setPayloadConfig((prev) => ({ ...prev, title: e.target.value }))
                        }
                        className="w-full bg-[#0a2b2f] border border-[#0e3b3f] rounded-lg px-3 py-2 text-sm text-slate-200 focus:outline-none focus:border-teal-500"
                      />
                    </div>
                    <div>
                      <label className="block text-xs text-slate-400 mb-1.5">Priority</label>
                      <select
                        value={payloadConfig.priority}
                        onChange={(e) =>
                          setPayloadConfig((prev) => ({ ...prev, priority: e.target.value }))
                        }
                        className="w-full bg-[#0a2b2f] border border-[#0e3b3f] rounded-lg px-3 py-2 text-sm text-slate-200 focus:outline-none focus:border-teal-500"
                      >
                        <option value="high">High (Immediate)</option>
                        <option value="normal">Normal</option>
                      </select>
                    </div>
                    <div>
                      <label className="block text-xs text-slate-400 mb-1.5">TTL (Seconds)</label>
                      <input
                        type="number"
                        value={payloadConfig.ttl}
                        onChange={(e) =>
                          setPayloadConfig((prev) => ({ ...prev, ttl: parseInt(e.target.value) }))
                        }
                        className="w-full bg-[#0a2b2f] border border-[#0e3b3f] rounded-lg px-3 py-2 text-sm text-slate-200 focus:outline-none focus:border-teal-500"
                      />
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </div>

          {/* Right Column: JSON Payload Preview */}
          <div className="space-y-6">
            <div className="bg-[#020817] border border-[#1e293b] rounded-xl overflow-hidden flex flex-col h-full sticky top-6">
              <div className="bg-[#0f172a] px-4 py-3 border-b border-[#1e293b] flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <FileJson className="h-4 w-4 text-blue-400" />
                  <span className="text-sm font-medium text-slate-300">Final Payload Preview</span>
                </div>
                <div className="flex items-center gap-2">
                  <span className="text-xs text-slate-500">Live</span>
                </div>
              </div>

              <div className="p-4 overflow-auto flex-1">
                <pre className="font-mono text-xs text-blue-300 leading-relaxed">
                  {JSON.stringify(payloadPreview, null, 2)}
                </pre>
              </div>

              <div className="bg-[#0f172a]/50 px-4 py-3 border-t border-[#1e293b]">
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
