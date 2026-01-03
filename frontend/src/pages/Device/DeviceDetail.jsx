import { Button } from '@/components/ui/button';
import { Toast } from '@/components/ui/Toast';
import api from '@/services/api';
import { trackActivity } from '@/utils/analytics';
import { ArrowLeft, Loader2, Radio } from 'lucide-react';
import React, { useEffect, useState, useRef } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import {
  AlertsWidget,
  AuditWidget,
  CommandHistoryWidget,
  DeviceActionsWidget,
  DirectConnectWidget,
  LogsWidget,
  StatBlock,
} from './DeviceWidgets';

// Device Capability Definitions
const DEVICE_CAPABILITIES = {
  pos_terminal: {
    showHealth: true,
    showCommandHistory: true,
    showConnections: true,
    showAudit: true,
    showMonitoring: true,
  },
  iot_sensor: {
    showHealth: true,
    showCommandHistory: true,
    showConnections: true,
    showAudit: true,
    showMonitoring: true,
  },
  industrial_controller: {
    showHealth: true,
    showCommandHistory: true,
    showConnections: true,
    showAudit: true,
    showMonitoring: true,
  },
  gateway: {
    showHealth: true,
    showCommandHistory: true,
    showConnections: true,
    showAudit: true,
    showMonitoring: true,
  },
  unknown: {
    showHealth: true,
    showCommandHistory: true,
    showConnections: true,
    showAudit: true,
    showMonitoring: true,
  },
};

// Define available actions per device type
const DEVICE_ACTIONS = {
  pos_terminal: [
    { key: 'refresh_kiosk', label: 'Refresh Kiosk' },
    { key: 'update_settings', label: 'Update Configurations' },
    { key: 'status_request', label: 'Request Status' },
    { key: 'fetch_system_apps', label: 'Fetch Apps' },
  ],
  iot_sensor: [
    { key: 'status_request', label: 'Request Status' },
    { key: 'update_settings', label: 'Update Configurations' },
  ],
  industrial_controller: [
    { key: 'status_request', label: 'Request Status' },
    { key: 'update_settings', label: 'Update Configurations' },
  ],
  gateway: [
    { key: 'status_request', label: 'Request Status' },
    { key: 'update_settings', label: 'Update Configurations' },
    { key: 'fetch_system_apps', label: 'Fetch Apps' },
  ],
  unknown: [
    { key: 'status_request', label: 'Request Status' },
    { key: 'update_settings', label: 'Update Configurations' },
  ],
};

export default function Device() {
  const { id } = useParams();
  const navigate = useNavigate();

  const [device, setDevice] = useState(null);
  const [alerts, setAlerts] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const [showPushModal, setShowPushModal] = useState(false);
  const [pushMessage, setPushMessage] = useState('');
  const [actionLoading, setActionLoading] = useState(null);
  const [toast, setToast] = useState(null);

  // Terminal State
  const [isTerminalOpen, setIsTerminalOpen] = useState(false);
  const [terminalOutput, setTerminalOutput] = useState([]);
  const [terminalInput, setTerminalInput] = useState('');
  const terminalEndRef = useRef(null);

  // Mock Data (In a real app, this would come from the API or a store)
  const stats = {
    cpu: { label: 'CPU', value: '3,4rh', subtitle: 'avg 3.4%' },
    memory: { label: 'Memory', value: '4 MW', subtitle: 'used 4GB' },
    disk: { label: 'Disk', value: '25s ago', subtitle: 'last check' },
  };

  const [commandHistory, setCommandHistory] = useState([
    { title: 'Configuration updated', date: '22 Jan 2024' },
    { title: 'Alert resolved', date: '2024-04-23' },
  ]);

  const [audit] = useState([
    { title: 'Configuration updated', date: '22 Jan 2024' },
    { title: 'Alert resolved', date: '2024-04-23' },
  ]);

  const [logs, setLogs] = useState([
    { message: 'Connection established', timestamp: '2024-04-23 10:00:00' },
    { message: 'Data sync completed', timestamp: '2024-04-23 10:05:00' },
  ]);

  useEffect(() => {
    const fetchDevice = async () => {
      try {
        const deviceData = await api.devices.getDeviceById(id);
        if (!deviceData) {
          setError('Device not found.');
        } else {
          setDevice(deviceData);

          // Fetch device health/alerts from AI anomalies to ensure consistency with Dashboard
          try {
            const anomalyData = await api.ai.getAnomalies();
            if (anomalyData && anomalyData.anomalies) {
              // Filter anomalies for this specific device
              const deviceAnomalies = anomalyData.anomalies
                .filter((a) => a.device_id === id)
                .map((a) => ({
                  message:
                    a.reasons && a.reasons.length > 0
                      ? a.reasons[0]
                      : `${a.severity === 'critical' ? 'CRITICAL' : 'WARNING'} - Score ${a.score}`,
                  timestamp: a.timestamp,
                  severity: a.severity,
                }));
              setAlerts(deviceAnomalies);
            }
          } catch (healthErr) {
            console.warn('Failed to fetch device health:', healthErr);
          }
        }
      } catch (err) {
        console.error('Failed to fetch device:', err);
        setError('Failed to load device details.');
      } finally {
        setLoading(false);
      }
    };

    fetchDevice();
  }, [id]);

  useEffect(() => {
    trackActivity('page_view', `/devices/${id}`, { device_id: id });
  }, [id]);

  // Auto-scroll terminal
  useEffect(() => {
    terminalEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [terminalOutput, isTerminalOpen]);

  const handleToggleMonitor = async () => {
    try {
      const updatedDevice = await api.devices.toggleMonitor(id, !device.is_monitored);
      setDevice((prev) => ({ ...prev, is_monitored: updatedDevice.is_monitored }));
    } catch (err) {
      console.error('Failed to toggle monitor:', err);
    }
  };

  const handleActionClick = async (actionKey) => {
    try {
      setActionLoading(actionKey);
      await trackActivity('click', `/devices/${id}`, {
        action: 'device_action',
        command: actionKey,
        device_id: id,
      });

      console.log(`Triggering action: ${actionKey} for device ${id}`);

      // Call the Generic API
      await api.devices.triggerAction(id, actionKey);

      // Update Command History
      const newHistoryItem = {
        title: `Action: ${actionKey.replace('_', ' ')}`,
        date: new Date().toLocaleString(),
      };
      setCommandHistory((prev) => [newHistoryItem, ...prev]);

      // Update Logs
      const newLogItem = {
        message: `Action ${actionKey} triggered successfully`,
        timestamp: new Date().toLocaleString(),
      };
      setLogs((prev) => [newLogItem, ...prev]);

      // Handle specific actions
      if (actionKey === 'status_request') {
        // Simulate a status update or refresh device data
        const deviceData = await api.devices.getDeviceById(id);
        setDevice(deviceData);
        setToast({
          message: `Status updated: ${deviceData?.status || 'Online'}`,
          type: 'success',
        });
      } else if (actionKey === 'update_settings') {
        navigate(`/device/${id}/settings`);
      } else {
        setToast({
          message: `Action ${actionKey.replace('_', ' ')} triggered successfully`,
          type: 'success',
        });
      }
    } catch (err) {
      console.error('Failed to trigger action:', err);
      setToast({
        message: `Failed to trigger action: ${err.message}`,
        type: 'error',
      });

      // Log failure
      const errorLogItem = {
        message: `Action ${actionKey} failed: ${err.message}`,
        timestamp: new Date().toLocaleString(),
      };
      setLogs((prev) => [errorLogItem, ...prev]);
    } finally {
      setActionLoading(null);
    }
  };

  const handleDirectConnect = async () => {
    try {
      await trackActivity('click', `/devices/${id}`, {
        action: 'direct_connect',
        device_id: id,
      });

      setIsTerminalOpen(true);
      setTerminalOutput([
        { type: 'info', text: `Connecting to ${device?.name || id}...` },
        { type: 'success', text: 'Secure channel established (TLS 1.3)' },
        { type: 'info', text: 'Welcome to Remote Shell v2.1.0' },
        { type: 'info', text: 'Type "help" for available commands.' },
      ]);
    } catch (err) {
      console.error('Failed to initiate connection:', err);
    }
  };

  const handleTerminalSubmit = (e) => {
    e.preventDefault();
    if (!terminalInput.trim()) return;

    const cmd = terminalInput.trim();
    setTerminalOutput((prev) => [
      ...prev,
      {
        type: 'input',
        text: `root@${device?.name?.toLowerCase().replace(/\s+/g, '-') || 'device'}:~# ${cmd}`,
      },
    ]);
    setTerminalInput('');

    // Mock terminal responses
    setTimeout(() => {
      let response = { type: 'output', text: '' };
      switch (cmd.toLowerCase()) {
        case 'help':
          response.text = 'Available commands: status, reboot, logs, clear, exit';
          break;
        case 'status':
          response.text = `Device: ${device?.name}\nStatus: ${device?.status}\nUptime: 14d 2h 12m`;
          break;
        case 'clear':
          setTerminalOutput([]);
          return;
        case 'exit':
          setIsTerminalOpen(false);
          return;
        default:
          response.text = `Command not found: ${cmd}`;
          response.type = 'error';
      }
      setTerminalOutput((prev) => [...prev, response]);
    }, 300);
  };

  const handleSendPush = async () => {
    if (!pushMessage.trim()) return;

    try {
      await api.agents.sendPush(id, {
        title: 'Message from Admin',
        body: pushMessage,
        priority: 'high',
      });
      setShowPushModal(false);
      setPushMessage('');
      setToast({ message: 'Push notification sent successfully!', type: 'success' });
    } catch (err) {
      console.error('Failed to send push:', err);
      setToast({ message: 'Failed to send push notification', type: 'error' });
    }
  };

  if (loading) {
    return (
      <div className="flex justify-center items-center h-64">
        <Loader2 className="h-8 w-8 animate-spin text-teal-400" />
      </div>
    );
  }

  if (error) {
    return (
      <div className="p-10 text-center text-red-400">
        {error}
        <br />
        <Button onClick={() => window.history.back()}>Go Back</Button>
      </div>
    );
  }

  // Mock Data (In a real app, this would come from the API or a store)
  // Removed static stats definition as it is now defined above with state variables
  // const stats = { ... };

  // Removed static commandHistory definition
  // const commandHistory = [ ... ];

  // Removed static connections definition
  // const connections = [ ... ];

  // Removed static audit definition
  // const audit = [ ... ];

  // Removed static logs definition
  // const logs = [ ... ];

  const sparkData = {
    small: [6, 3, 5, 4, 7, 6, 8],
    medium: [10, 14, 9, 12, 18, 16, 20, 18, 22],
  };

  // Consolidated Metrics for Tier 2
  const metrics = [
    {
      key: 'cpu',
      label: 'CPU',
      value: stats.cpu.value,
      subtitle: stats.cpu.subtitle,
      data: sparkData.small,
    },
    {
      key: 'memory',
      label: 'Memory',
      value: stats.memory.value,
      subtitle: stats.memory.subtitle,
      data: sparkData.small,
    },
    {
      key: 'disk',
      label: 'Disk',
      value: stats.disk.value,
      subtitle: stats.disk.subtitle,
      data: sparkData.small,
    },
    {
      key: 'uptime',
      label: 'Uptime',
      value: '99.9%',
      subtitle: 'last 30 days',
      data: [8, 10, 12, 10, 14, 16, 18],
    },
    { key: 'alerts', label: 'Alerts', value: '2', subtitle: 'active', data: [4, 6, 5, 6, 7, 6, 8] },
    {
      key: 'network',
      label: 'Network',
      value: '1.2 GB',
      subtitle: 'traffic',
      data: sparkData.medium,
    },
  ];

  // Determine capabilities based on device type
  const deviceType = device?.device_type || 'unknown';
  const capabilities = DEVICE_CAPABILITIES[deviceType] || DEVICE_CAPABILITIES['unknown'];
  const actions = DEVICE_ACTIONS[deviceType] || [];

  return (
    <>
      {toast && <Toast message={toast.message} type={toast.type} onClose={() => setToast(null)} />}

      {showPushModal && (
        <div className="fixed inset-0 bg-black/60 backdrop-blur-sm flex items-center justify-center z-50">
          <div className="bg-[#062125] border border-[#0e3b3f] rounded-xl p-6 w-96 shadow-xl">
            <h2 className="text-xl font-semibold text-teal-300 mb-4">Send Push Notification</h2>
            <textarea
              className="w-full bg-[#0a2b2f] border border-[#0e3b3f] rounded-lg p-3 text-slate-200 focus:outline-none focus:border-teal-500 mb-4 h-32 resize-none"
              placeholder="Enter your message here..."
              value={pushMessage}
              onChange={(e) => setPushMessage(e.target.value)}
            />
            <div className="flex justify-end gap-3">
              <button
                onClick={() => setShowPushModal(false)}
                className="px-4 py-2 rounded-md text-sm font-medium text-slate-400 hover:text-white"
              >
                Cancel
              </button>
              <button
                onClick={handleSendPush}
                className="px-4 py-2 rounded-md text-sm font-medium bg-teal-600 text-white hover:bg-teal-500"
              >
                Send
              </button>
            </div>
          </div>
        </div>
      )}

      <div className="min-h-screen bg-gradient-to-b from-[#041014] to-[#03121a] text-slate-200 p-6 sm:p-10 font-sans">
        <Button
          variant="ghost"
          onClick={() => navigate('/device')}
          className="mb-4 pl-0 hover:pl-1 transition-all text-gray-400 hover:text-white hover:bg-transparent"
        >
          <ArrowLeft className="h-4 w-4 mr-2" />
          Back
        </Button>

        <div className="max-w-7xl mx-auto">
          {/* Header */}
          <header className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 mb-6">
            <div className="flex items-center gap-4">
              <div className="w-16 h-16 rounded-xl bg-gradient-to-tr from-teal-400 to-cyan-400 flex items-center justify-center shadow-[0_6px_24px_rgba(2,136,153,0.18)] ring-1 ring-white/5">
                <svg
                  xmlns="http://www.w3.org/2000/svg"
                  className="w-9 h-9 text-[#022426]"
                  viewBox="0 0 24 24"
                  fill="none"
                  stroke="currentColor"
                >
                  <path
                    strokeWidth="1.6"
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    d="M9 12h6M9 16h6M8 8h8M5 21h14a1 1 0 001-1V8a1 1 0 00-1-1H5a1 1 0 00-1 1v12a1 1 0 001 1z"
                  />
                </svg>
              </div>

              <div className="leading-tight">
                <h1 className="text-2xl sm:text-3xl font-semibold tracking-tight">
                  {device?.name || device?.device_id || 'Unknown Device'}
                </h1>

                <div className="flex items-center gap-2 mt-1 text-sm text-emerald-300">
                  <span className="w-2 h-2 rounded-full bg-emerald-400 shadow-[0_0_10px_rgba(34,197,94,0.14)] inline-block" />
                  <span className="font-medium">
                    {device?.status ? device.status.toUpperCase() : 'UNKNOWN'}
                  </span>
                </div>
                <div className="text-xs text-slate-500 mt-1 uppercase tracking-wider">
                  {device?.device_type?.replace('_', ' ') || 'UNKNOWN TYPE'}
                </div>
              </div>
            </div>

            <div className="flex items-center gap-3">
              <ActionButton
                onClick={handleToggleMonitor}
                className={device?.is_monitored ? 'text-yellow-400 border-yellow-400' : ''}
              >
                {device?.is_monitored ? 'Monitored' : 'Add to Dashboard'}
              </ActionButton>

              <ActionButton onClick={handleDirectConnect} className="flex items-center gap-2">
                <Radio className="w-4 h-4" />
                Direct Connect
              </ActionButton>

              <ActionButton onClick={() => navigate('/dashboard')}>Exit</ActionButton>
            </div>
          </header>

          {/* Main Grid */}
          <div className="flex flex-col gap-6">
            {/* Alerts Widget */}
            <AlertsWidget alerts={alerts} />

            {/* Tier 2: Metrics Row (6 columns) */}
            <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-4">
              {metrics.map((metric) => (
                <StatBlock
                  key={metric.key}
                  title={metric.label}
                  value={metric.value}
                  subtitle={metric.subtitle}
                  data={metric.data}
                />
              ))}
            </div>

            {/* Tier 3: Actions, History & Terminal (Left) | Logs & Audit (Right) */}
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
              {/* Left Column */}
              <div className="space-y-4">
                {/* Device Actions */}
                {actions.length > 0 && (
                  <DeviceActionsWidget
                    actions={actions}
                    onActionClick={handleActionClick}
                    loadingAction={actionLoading}
                  />
                )}

                {/* Command History (Moved from Right) */}
                {capabilities.showCommandHistory && (
                  <CommandHistoryWidget commandHistory={commandHistory} />
                )}

                {/* Direct Connect Terminal */}
                <DirectConnectWidget
                  isOpen={isTerminalOpen}
                  onClose={() => setIsTerminalOpen(false)}
                  terminalOutput={terminalOutput}
                  terminalInput={terminalInput}
                  setTerminalInput={setTerminalInput}
                  handleTerminalSubmit={handleTerminalSubmit}
                  terminalEndRef={terminalEndRef}
                  deviceName={device?.name}
                />
              </div>

              {/* Right Column */}
              <div className="space-y-4">
                {/* Logs */}
                <LogsWidget logs={logs} />

                {/* Audit (Moved from Left) */}
                {capabilities.showAudit && <AuditWidget audit={audit} />}
              </div>
            </div>
          </div>
        </div>
      </div>
    </>
  );
}

function ActionButton({ children, onClick, className }) {
  return (
    <button
      onClick={onClick}
      className={`px-4 py-2 rounded-md text-sm font-medium border backdrop-blur-sm border-[#0b3b3f] text-teal-200 hover:brightness-105 ${className || ''}`}
    >
      {children}
    </button>
  );
}
