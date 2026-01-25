import { Button } from '@/components/ui/button';
import { Toast } from '@/components/ui/Toast';
import api from '@/services/api';
import { trackActivity } from '@/utils/analytics';
import {
  ArrowLeft,
  Loader2,
  Radio,
  FileText,
  Shield,
  TerminalSquare,
  History,
  Activity,
  AlertTriangle,
} from 'lucide-react';
import React, { useEffect, useState, useRef, useCallback } from 'react';
import { useParams, useNavigate, useLocation } from 'react-router-dom';
import {
  AlertsWidget,
  AuditWidget,
  JobHistoryWidget,
  DeviceActionsWidget,
  DeviceInfoWidget,
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
    { key: 'status_request', label: 'Request Status' },
    { key: 'update_settings', label: 'Compose Command' },
  ],
  iot_sensor: [
    { key: 'status_request', label: 'Request Status' },
    { key: 'update_settings', label: 'Compose Command' },
  ],
  industrial_controller: [
    { key: 'status_request', label: 'Request Status' },
    { key: 'update_settings', label: 'Compose Command' },
  ],
  gateway: [
    { key: 'status_request', label: 'Request Status' },
    { key: 'update_settings', label: 'Compose Command' },
  ],
  unknown: [
    { key: 'status_request', label: 'Request Status' },
    { key: 'update_settings', label: 'Compose Command' },
  ],
};

/* === Helpers === */
function formatUptime(seconds) {
  if (!seconds) return '0s';
  const days = Math.floor(seconds / 86400);
  const hours = Math.floor((seconds % 86400) / 3600);
  if (days > 0) return `${days}d ${hours}h`;
  const minutes = Math.floor((seconds % 3600) / 60);
  return `${hours}h ${minutes}m`;
}

export default function Device() {
  const { id } = useParams();
  const navigate = useNavigate();
  const location = useLocation();

  const [device, setDevice] = useState(null);
  const [alerts, setAlerts] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [activeTab, setActiveTab] = useState('logs');

  // Real Data States
  // metrics: raw data not currently used for display (we use stats)
  const [errorLogs, setErrorLogs] = useState([]);
  const [auditLogs, setAuditLogs] = useState([]);
  const [jobHistory, setJobHistory] = useState([]);
  // pushLogs: raw data not currently used for display
  const [stats, setStats] = useState({
    cpu: { label: 'CPU', value: '0%', subtitle: 'avg 0%', data: [] },
    memory: { label: 'Memory', value: '0GB', subtitle: 'used 0GB', data: [] },
    disk: { label: 'Disk', value: '0%', subtitle: 'last check', data: [] },
    network: { label: 'Network', value: '0ms', subtitle: 'latency', data: [] },
    uptime: { label: 'Uptime', value: '0s', subtitle: 'system up', data: [] },
  });

  const [showPushModal, setShowPushModal] = useState(false);
  const [pushMessage, setPushMessage] = useState('');
  const [actionLoading, setActionLoading] = useState(null);
  const [toast, setToast] = useState(null);

  const handleToastClose = useCallback(() => {
    setToast(null);
  }, []);

  // Terminal State
  const [isTerminalOpen, setIsTerminalOpen] = useState(false);
  const [terminalOutput, setTerminalOutput] = useState([]);
  const [terminalInput, setTerminalInput] = useState('');
  const terminalEndRef = useRef(null);

  useEffect(() => {
    const fetchDevice = async () => {
      try {
        const deviceData = await api.devices.getDeviceById(id);
        if (!deviceData) {
          setError('Device not found.');
        } else {
          setDevice(deviceData);

          // Fetch related data in parallel
          try {
            const [metricsData, auditData, jobsData, , errorData] = await Promise.all([
              api.devices.getMetrics(id, 20),
              api.devices.getAuditLogs(id, 10),
              api.devices.getJobs(id, 10),
              api.devices.getPushLogs(id, 10),
              api.devices.getErrorLogs(id, 10),
            ]);

            // setMetrics(metricsData); // unused
            setAuditLogs(auditData);
            setJobHistory(jobsData);
            // setPushLogs(pushData); // unused
            setErrorLogs(errorData);

            // Process Stats
            if (metricsData && metricsData.length > 0) {
              const latest = metricsData[0];
              const cpuTrend = metricsData.map((m) => m.cpu_percent).reverse();
              const memTrend = metricsData.map((m) => m.memory_percent).reverse();
              const diskTrend = metricsData.map((m) => m.disk_percent).reverse();
              const netTrend = metricsData.map((m) => m.network_latency_ms).reverse();

              // Extract uptime from extra_metrics if available
              const currentUptime = latest.extra_metrics?.uptime_seconds || 0;
              const uptimeTrend = metricsData
                .map((m) => m.extra_metrics?.uptime_seconds || 0)
                .reverse();

              setStats({
                cpu: {
                  label: 'CPU',
                  value: `${latest.cpu_percent?.toFixed(1) || 0}%`,
                  subtitle: 'current load',
                  data: cpuTrend,
                },
                memory: {
                  label: 'Memory',
                  value: `${latest.memory_percent?.toFixed(1) || 0}%`,
                  subtitle: 'utilization',
                  data: memTrend,
                },
                disk: {
                  label: 'Disk',
                  value: `${latest.disk_percent?.toFixed(1) || 0}%`,
                  subtitle: 'usage',
                  data: diskTrend,
                },
                network: {
                  label: 'Network',
                  value: `${latest.network_latency_ms?.toFixed(0) || 0}ms`,
                  subtitle: 'latency',
                  data: netTrend,
                },
                uptime: {
                  label: 'Uptime',
                  value: formatUptime(currentUptime),
                  subtitle: 'system up',
                  data: uptimeTrend,
                },
              });
            }
          } catch (relatedErr) {
            console.warn('Failed to fetch related device data', relatedErr);
            // Don't fail the whole page load
          }

          // Fetch persistent alerts AND AI anomalies
          try {
            const [alertsData, anomalyData] = await Promise.all([
              api.devices.getAlerts(id),
              api.ai.getAnomalies().catch(() => ({ anomalies: [] })), // Fail gracefully
            ]);

            let combinedAlerts = [];

            // 1. Standard Monitor Alerts
            if (alertsData && Array.isArray(alertsData)) {
              combinedAlerts = combinedAlerts.concat(
                alertsData.map((a) => ({
                  id: a.id,
                  message: `${a.title}: ${a.description}`,
                  severity: a.severity,
                  timestamp: a.timestamp,
                  source: 'Monitor',
                }))
              );
            }

            // 2. AI Anomalies
            if (anomalyData && anomalyData.anomalies) {
              const deviceAnomalies = anomalyData.anomalies.filter((a) => a.device_id === id);

              // Create a set of "signatures" from existing alerts to avoid duplicates
              const existingSignatures = new Set(
                combinedAlerts.map((a) => a.message.toLowerCase())
              );

              const newAnomalies = deviceAnomalies.filter((anom) => {
                if (!anom.reasons || anom.reasons.length === 0) return true;

                // Check if any reason is already covered by an existing alert
                // Anomaly Reason: "High CPU: 92%"
                // DB Alert Message: "[DEMO] High CPU: 92%..."
                const isCovered = anom.reasons.some((r) => {
                  const reasonKey = r.split(':')[0].toLowerCase(); // "high cpu"
                  // Check if any existing alert contains this key phrase
                  for (let sig of existingSignatures) {
                    if (sig.includes(reasonKey)) return true;
                  }
                  return false;
                });

                return !isCovered;
              });

              combinedAlerts = combinedAlerts.concat(
                newAnomalies.map((a) => ({
                  id: null, // AI Anomalies are transient, so no ID
                  message:
                    a.reasons && a.reasons.length > 0
                      ? `Anomaly: ${a.reasons[0]}`
                      : `Anomaly Detected (Score: ${a.score})`,
                  severity: a.severity === 'critical' ? 'critical' : 'warning',
                  timestamp: a.timestamp,
                  source: 'AI Analysis',
                }))
              );
            }

            // Sort by timestamp descending
            combinedAlerts.sort((a, b) => new Date(b.timestamp) - new Date(a.timestamp));

            setAlerts(combinedAlerts);
          } catch (alertsErr) {
            console.warn('Failed to fetch device alerts:', alertsErr);
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

    // Poll for live metrics every 2 seconds matching the agent loop
    const pollInterval = setInterval(() => {
      // 1. Fetch Metrics
      api.devices
        .getMetrics(id, 20)
        .then((metricsData) => {
          if (metricsData && metricsData.length > 0) {
            const latest = metricsData[0];
            const cpuTrend = metricsData.map((m) => m.cpu_percent).reverse();
            const memTrend = metricsData.map((m) => m.memory_percent).reverse();
            const diskTrend = metricsData.map((m) => m.disk_percent).reverse();
            const netTrend = metricsData.map((m) => m.network_latency_ms).reverse();

            // Extract uptime from extra_metrics if available
            const currentUptime = latest.extra_metrics?.uptime_seconds || 0;
            const uptimeTrend = metricsData
              .map((m) => m.extra_metrics?.uptime_seconds || 0)
              .reverse();

            setStats({
              cpu: {
                label: 'CPU',
                value: `${latest.cpu_percent?.toFixed(1) || 0}%`,
                subtitle: 'current load',
                data: cpuTrend,
              },
              memory: {
                label: 'Memory',
                value: `${latest.memory_percent?.toFixed(1) || 0}%`,
                subtitle: 'utilization',
                data: memTrend,
              },
              disk: {
                label: 'Disk',
                value: `${latest.disk_percent?.toFixed(1) || 0}%`,
                subtitle: 'usage',
                data: diskTrend,
              },
              network: {
                label: 'Network',
                value: `${latest.network_latency_ms?.toFixed(0) || 0}ms`,
                subtitle: 'latency',
                data: netTrend,
              },
              uptime: {
                label: 'Uptime',
                value: formatUptime(currentUptime),
                subtitle: 'system up',
                data: uptimeTrend,
              },
            });
          }
        })
        .catch((err) => console.debug('Metric poll skipped', err));

      // 2. Fetch Logs (if tab is active)
      // We check activeTab inside the effect, but activeTab state might be stale in closure.
      // However, fetching these small JSONs is cheap enough to do always for "Live" feel.
      // Limit to latest 50 entries to prevent memory growth (the "overwrite" behavior)
      api.devices
        .getErrorLogs(id, 50)
        .then((errorData) => {
          setErrorLogs(errorData);
        })
        .catch((err) => console.debug('Log poll skipped', err));

      // 3. Fetch Audit Logs (if tab is active or just always for consistency)
      // Limit to 50 for consistency with other tabs
      api.devices
        .getAuditLogs(id, 50)
        .then((auditData) => {
          setAuditLogs(auditData);
        })
        .catch((err) => console.debug('Audit poll skipped', err));

      // 4. Fetch Job History
      api.devices
        .getJobs(id, 50)
        .then((jobsData) => {
          setJobHistory(jobsData);
        })
        .catch((err) => console.debug('Job poll skipped', err));

      // 5. Fetch Alerts - Live
      // We must fetch from DB alerts AND AI to maintain the unified list.
      // Currently, the polling only updates from DB, and overwrites the initial merged list!
      // This is why IDs disappear after the first render (polling overwrites merged state).

      Promise.all([
        api.devices.getAlerts(id),
        api.ai.getAnomalies().catch(() => ({ anomalies: [] })),
      ])
        .then(([alertsData, anomalyData]) => {
          let combinedAlerts = [];

          if (alertsData && Array.isArray(alertsData)) {
            combinedAlerts = combinedAlerts.concat(
              alertsData.map((a) => ({
                id: a.id,
                message: `${a.title}: ${a.description}`,
                severity: a.severity,
                timestamp: a.timestamp,
                source: 'Monitor',
              }))
            );
          }

          if (anomalyData && anomalyData.anomalies) {
            const deviceAnomalies = anomalyData.anomalies.filter((a) => a.device_id === id);

            // Create duplicates check based on message signatures
            const existingSignatures = new Set(combinedAlerts.map((a) => a.message.toLowerCase()));

            const newAnomalies = deviceAnomalies.filter((anom) => {
              if (!anom.reasons || anom.reasons.length === 0) return true;
              const isCovered = anom.reasons.some((r) => {
                const reasonKey = r.split(':')[0].toLowerCase();
                for (let sig of existingSignatures) {
                  if (sig.includes(reasonKey)) return true;
                }
                return false;
              });
              return !isCovered;
            });

            combinedAlerts = combinedAlerts.concat(
              newAnomalies.map((a) => ({
                id: null,
                message:
                  a.reasons && a.reasons.length > 0
                    ? `Anomaly: ${a.reasons[0]}`
                    : `Anomaly Detected (Score: ${a.score})`,
                severity: a.severity === 'critical' ? 'critical' : 'warning',
                timestamp: a.timestamp,
                source: 'AI Analysis',
              }))
            );
          }

          combinedAlerts.sort((a, b) => new Date(b.timestamp) - new Date(a.timestamp));
          setAlerts(combinedAlerts);
        })
        .catch((err) => console.debug('Alerts poll skipped', err));
    }, 2000);

    return () => clearInterval(pollInterval);
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
      setJobHistory((prev) => [newHistoryItem, ...prev]);

      // Update Logs (Toast only since we don't have local logs anymore)
      // const newLogItem = ...

      // Handle specific actions
      if (actionKey === 'status_request') {
        // 1. Create a tracking Job
        if (device?.site_id) {
          try {
            await api.jobs.create(device.site_id, {
              action: 'Manual Status Check',
              description: `User requested status check for device ${id}`,
              priority: 'high',
              device_id: id,
            });
          } catch (jobErr) {
            console.warn('Failed to create tracking job:', jobErr);
          }
        }

        // 2. Refresh device data
        const deviceData = await api.devices.getDeviceById(id);
        setDevice(deviceData);
        setToast({
          message: `Status request sent. Job created.`,
          type: 'success',
        });
      } else if (actionKey === 'update_settings') {
        navigate(`/device/${id}/push-review`);
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
      // NOTE: We rely on server-side logging for errors now.
      // Re-fetch logs if needed, or just show toast.
      /*
      const errorLogItem = {
        message: `Action ${actionKey} failed: ${err.message}`,
        timestamp: new Date().toLocaleString(),
      };
      setLogs((prev) => [errorLogItem, ...prev]);
      */
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
  const statCards = [
    {
      key: 'cpu',
      label: 'CPU',
      value: stats.cpu.value,
      subtitle: stats.cpu.subtitle,
      data: stats.cpu.data.length > 0 ? stats.cpu.data : sparkData.small,
    },
    {
      key: 'memory',
      label: 'Memory',
      value: stats.memory.value,
      subtitle: stats.memory.subtitle,
      data: stats.memory.data.length > 0 ? stats.memory.data : sparkData.small,
    },
    {
      key: 'disk',
      label: 'Disk',
      value: stats.disk.value,
      subtitle: stats.disk.subtitle,
      data: stats.disk.data.length > 0 ? stats.disk.data : sparkData.small,
    },
    {
      key: 'uptime',
      label: 'Uptime',
      value: stats.uptime?.value || '0s',
      subtitle: stats.uptime?.subtitle || 'system up',
      data: stats.uptime?.data?.length > 0 ? stats.uptime.data : [0, 1, 2, 3, 4],
    },
    {
      key: 'network',
      label: 'Network',
      value: stats.network.value,
      subtitle: stats.network.subtitle,
      data: stats.network.data.length > 0 ? stats.network.data : sparkData.medium,
    },
    {
      key: 'alerts',
      label: 'Alerts',
      value: alerts.length.toString(),
      subtitle: 'active',
      data: [4, 6, 5, 6, 7, 6, 8],
    },
  ];

  // Determine capabilities based on device type
  // const deviceType = device?.device_type || 'unknown';
  // const capabilities = DEVICE_CAPABILITIES[deviceType] || DEVICE_CAPABILITIES['unknown'];
  // NOTE: Capabilities are now handled by tab visibility or individual widget logic in the new layout
  const actions = DEVICE_ACTIONS[device?.device_type] || [];

  return (
    <>
      {toast && <Toast message={toast.message} type={toast.type} onClose={handleToastClose} />}

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

      <div className="h-full bg-gradient-to-b from-[#041014] to-[#03121a] text-slate-200 p-2 font-sans flex flex-col overflow-hidden">
        <div className="max-w-7xl mx-auto w-full h-full flex flex-col">
          {/* Fixed Header Section */}
          <div className="shrink-0 space-y-2 mb-4">
            <Button
              variant="ghost"
              onClick={() => {
                if (location.state?.from === 'site' && location.state?.siteId) {
                  navigate(`/sites/${location.state.siteId}`);
                } else if (device?.site_id) {
                  navigate(`/sites/${device.site_id}`);
                } else {
                  navigate('/device');
                }
              }}
              className="pl-0 hover:pl-1 transition-all text-gray-400 hover:text-white hover:bg-transparent"
            >
              <ArrowLeft className="h-4 w-4 mr-2" />
              {location.state?.from === 'site' || device?.site_id ? 'Back to Site' : 'Back'}
            </Button>

            <header className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
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
                  <div className="text-xs text-slate-500 mt-1 font-mono tracking-wider">
                    {device?.device_id || 'NO ID'}
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
          </div>

          {/* Main Layout: Right Actions (Sidebar) + Left Content */}
          <div className="flex flex-col lg:flex-row gap-4 items-stretch flex-1 min-h-0 overflow-hidden">
            {/* Main Column: Context & History */}
            <div className="w-full lg:w-3/4 flex flex-col gap-4 h-full overflow-hidden">
              {/* Metrics Grid */}
              <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-4 shrink-0">
                {statCards.map((metric) => (
                  <StatBlock
                    key={metric.key}
                    title={metric.label}
                    value={metric.value}
                    subtitle={metric.subtitle}
                    data={metric.data}
                  />
                ))}
              </div>

              {/* Activity Tabs */}
              <div className="bg-[#06181c] border border-[#0e3b3f] rounded-xl overflow-hidden shadow-sm flex flex-col flex-1 min-h-0">
                <div className="flex border-b border-[#0e3b3f] bg-[#041014] overflow-x-auto shrink-0">
                  <button
                    onClick={() => setActiveTab('logs')}
                    className={`flex items-center gap-2 px-6 py-3 text-sm font-medium border-b-2 transition-colors whitespace-nowrap ${
                      activeTab === 'logs'
                        ? 'border-teal-500 text-teal-400 bg-teal-500/5'
                        : 'border-transparent text-slate-400 hover:text-slate-200'
                    }`}
                  >
                    <FileText className="w-4 h-4" /> Live Logs
                  </button>
                  <button
                    onClick={() => setActiveTab('audit')}
                    className={`flex items-center gap-2 px-6 py-3 text-sm font-medium border-b-2 transition-colors whitespace-nowrap ${
                      activeTab === 'audit'
                        ? 'border-teal-500 text-teal-400 bg-teal-500/5'
                        : 'border-transparent text-slate-400 hover:text-slate-200'
                    }`}
                  >
                    <Shield className="w-4 h-4" /> Audit Trail
                  </button>
                  <button
                    onClick={() => setActiveTab('jobs')}
                    className={`flex items-center gap-2 px-6 py-3 text-sm font-medium border-b-2 transition-colors whitespace-nowrap ${
                      activeTab === 'jobs'
                        ? 'border-teal-500 text-teal-400 bg-teal-500/5'
                        : 'border-transparent text-slate-400 hover:text-slate-200'
                    }`}
                  >
                    <History className="w-4 h-4" /> Job History
                  </button>
                  <button
                    onClick={() => setActiveTab('alerts')}
                    className={`flex items-center gap-2 px-6 py-3 text-sm font-medium border-b-2 transition-colors whitespace-nowrap ${
                      activeTab === 'alerts'
                        ? 'border-teal-500 text-teal-400 bg-teal-500/5'
                        : 'border-transparent text-slate-400 hover:text-slate-200'
                    }`}
                  >
                    <AlertTriangle className="w-4 h-4" /> Alerts
                    {alerts.length > 0 && (
                      <span className="ml-1 px-1.5 py-0.5 text-xs bg-red-500/20 text-red-400 rounded-full">
                        {alerts.length}
                      </span>
                    )}
                  </button>
                </div>

                <div className="p-4 flex-1 overflow-auto">
                  {activeTab === 'logs' && <LogsWidget logs={errorLogs} />}
                  {activeTab === 'audit' && <AuditWidget audit={auditLogs} />}
                  {activeTab === 'jobs' && <JobHistoryWidget jobs={jobHistory} />}
                  {activeTab === 'alerts' && <AlertsWidget alerts={alerts} />}
                </div>
              </div>
            </div>

            {/* Sidebar Column: Identity & Actions */}
            <div className="w-full lg:w-1/4 space-y-4 overflow-y-auto pr-1">
              <DeviceInfoWidget device={device} />

              {actions.length > 0 && (
                <DeviceActionsWidget
                  actions={actions}
                  onActionClick={handleActionClick}
                  loadingAction={actionLoading}
                />
              )}

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
