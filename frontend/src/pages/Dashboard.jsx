import React, { useEffect, useState } from 'react';
import { Card, CardContent } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { CheckCircle2, XCircle, Apple, Package, Monitor, CheckCircle } from 'lucide-react';
import api from '@/services/api';
import { useNavigate } from 'react-router-dom';
import MetricCard from '@/components/Dashboard/MetricCard';
import AskAIWidget from '@/components/Dashboard/AskAIWidget';
import ActiveAlertsTicker from '@/components/Dashboard/ActiveAlertsTicker';
import WorldMapImage from '@/assets/images/world-map.png';
import { MAX_AUTO_MONITORED_CARDS, buildMonitoredBoard } from '@/utils/dashboardBoard';

// Collapse an alert reason to a stable "kind" by stripping the numeric metric
// value and units, e.g. 'High Latency: 825ms' -> 'high latency'. This lets
// repeated periodic alerts of the same kind be deduplicated.
const normalizeAlertKind = (reason) =>
  String(reason || '')
    .replace(/\d+(\.\d+)?/g, '')
    .replace(/\b(ms|%|mb|gb|bytes?|seconds?|secs?)\b/g, '')
    .replace(/[:.,]/g, ' ')
    .replace(/\s+/g, ' ')
    .trim()
    .toLowerCase();

export default function Dashboard() {
  const [alerts, setAlerts] = useState([]);
  const [systemPulse, setSystemPulse] = useState({ status: 'idle', load_score: 0 });
  const [summary, setSummary] = useState(null);
  const [extraMonitored, setExtraMonitored] = useState(0);
  const [monitoredItems, setMonitoredItems] = useState([]);
  const clearMonitoredBoard = () => {
    setMonitoredItems([]);
    setExtraMonitored(0);
  };

  useEffect(() => {
    // Poll system pulse every 1 second
    const fetchPulse = async () => {
      try {
        const data = await api.health.getSystemPulse();
        setSystemPulse(data);
      } catch (e) {
        console.error('Failed to fetch system pulse', e);
      }
    };

    fetchPulse();
    const pulseInterval = setInterval(fetchPulse, 1000);

    return () => {
      clearInterval(pulseInterval);
    };
  }, []); // Run once on mount

  const [loading, setLoading] = useState(true);
  const navigate = useNavigate();

  const handleItemClick = (item) => {
    if (item.type === 'device' && item.id) {
      navigate(`/device/${item.id}`);
    } else if (item.type === 'site' && item.id) {
      navigate(`/sites/${item.id}`);
    }
  };

  useEffect(() => {
    const fetchData = async () => {
      // 1. Fetch Dashboard Summary
      try {
        const summaryData = await api.dashboard.summary();
        setSummary(summaryData);
      } catch (e) {
        console.error('Failed to fetch dashboard summary', e);
      }

      try {
        // 2. Fetch Sites
        const sitesData = await api.sites.list();
        const fetchedSites = sitesData?.sites || [];

        // 2. Fetch Devices
        let fetchedDevices = [];
        try {
          const devicesData = await api.devices.list();
          fetchedDevices = devicesData?.devices || [];
        } catch (e) {
          console.error('Failed to fetch devices for dashboard', e);
        }

        // 3. Fetch AI Anomalies (Moved up to support auto-monitoring)
        let anomalies = [];
        let finalAlerts = [];
        try {
          const anomalyData = await api.ai.getAnomalies();
          if (anomalyData && anomalyData.anomalies) {
            anomalies = anomalyData.anomalies;
            // Keep only the LATEST anomaly per (device, alert kind) so
            // repeated periodic alerts (e.g. 'High Latency' at different
            // values) collapse to the most recent one instead of accumulating.
            const latestByKind = new Map();
            for (const a of anomalies) {
              const kind = normalizeAlertKind(a.reasons?.[0] || a.severity || 'alert');
              const key = `${a.device_id}::${kind}`;
              const existing = latestByKind.get(key);
              if (!existing || new Date(a.timestamp) > new Date(existing.timestamp)) {
                latestByKind.set(key, a);
              }
            }
            finalAlerts = Array.from(latestByKind.values()).map((a) => ({
              id: a.id,
              message:
                a.reasons && a.reasons.length > 0
                  ? `${a.device_name}: ${a.reasons[0]}`
                  : `${a.device_name}: ${a.severity === 'critical' ? 'CRITICAL' : 'WARNING'} - Score ${a.score}`,
              timestamp: a.timestamp,
              severity: a.severity,
              device_id: a.device_id,
            }));
          }
        } catch (e) {
          console.error('Failed to fetch anomalies:', e);
        }

        // Filter monitored items
        const monitoredSites = fetchedSites.filter((s) => s.is_monitored);

        // Auto-monitor devices with active alerts
        const alertedDeviceIds = new Set(anomalies.map((a) => a.device_id));
        const monitoredDevices = fetchedDevices.filter(
          (d) => d.is_monitored || alertedDeviceIds.has(d.device_id)
        );

        let itemsToDisplay = [];

        if (monitoredSites.length > 0 || monitoredDevices.length > 0) {
          itemsToDisplay = [
            ...monitoredSites.map((s) => ({ ...s, _type: 'site' })),
            ...monitoredDevices.map((d) => ({ ...d, _type: 'device' })),
          ];
        }

        // Bound the auto-monitored board: sort by urgency (critical first,
        // then most recent) and cap the card count so a fleet-wide alert
        // storm cannot flood the technician's view.
        const board = buildMonitoredBoard({
          items: itemsToDisplay,
          anomalies,
          sites: fetchedSites,
          devices: fetchedDevices,
        });
        itemsToDisplay = board.items;
        setExtraMonitored(board.hidden);

        // Helper to format time ago
        const formatTimeAgo = (isoString) => {
          if (!isoString) return '—';
          try {
            const date = new Date(isoString);
            const now = new Date();
            const diffMs = now - date;
            const diffMins = Math.floor(diffMs / 60000); // minutes
            if (diffMins < 1) return 'Just now';
            if (diffMins < 60) return `${diffMins}m ago`;
            const diffHours = Math.floor(diffMins / 60);
            if (diffHours < 24) return `${diffHours}h ago`;
            const diffDays = Math.floor(diffHours / 24);
            return `${diffDays}d ago`;
          } catch {
            return '—';
          }
        };

        const sitesWithDefaults = itemsToDisplay.map((item, index) => {
          let osList = [];

          // Calculate Online Count
          let onlineCount = 0;

          // Find latest alert for Sync
          let itemAlerts = [];

          if (item._type === 'site') {
            // Count devices for this site that are online
            // Note: cached 'fetchedDevices' has all devices with site_id
            const siteDevices = fetchedDevices.filter((d) => d.site_id === item.site_id);
            onlineCount = siteDevices.filter(
              (d) => d.connectivity_state && d.connectivity_state.toLowerCase() === 'online'
            ).length;

            // Sites contain multiple OS types. Let's use the ones provided by the backend!
            osList = item.os_types || ['windows', 'linux', 'apple', 'android', 'web', 'iot'];

            // Alerts for site: Filter anomalies for devices in this site
            const siteDeviceIds = new Set(siteDevices.map((d) => d.device_id));
            itemAlerts = anomalies.filter((a) => siteDeviceIds.has(a.device_id));
          } else {
            // Single Device
            onlineCount =
              item.connectivity_state && item.connectivity_state.toLowerCase() === 'online' ? 1 : 0;

            // Identify OS by name/description for single device
            const normalizedName = (
              item.os_details ||
              item.name ||
              item.description ||
              ''
            ).toLowerCase();
            if (normalizedName.includes('windows') || normalizedName.includes('win')) {
              osList = ['windows'];
            } else if (
              normalizedName.includes('linux') ||
              normalizedName.includes('ubuntu') ||
              normalizedName.includes('debian')
            ) {
              osList = ['linux'];
            } else if (
              normalizedName.includes('mac') ||
              normalizedName.includes('apple') ||
              normalizedName.includes('ios') ||
              normalizedName.includes('osx')
            ) {
              osList = ['apple'];
            } else if (normalizedName.includes('android')) {
              osList = ['android'];
            } else if (normalizedName.includes('web')) {
              osList = ['web'];
            } else {
              osList = ['iot']; // Default
            }

            // Alerts for device
            itemAlerts = anomalies.filter((a) => a.device_id === item.device_id);
          }

          // Sort alerts to find the latest one
          const latestAlert =
            itemAlerts.length > 0
              ? itemAlerts.sort((a, b) => new Date(b.timestamp) - new Date(a.timestamp))[0]
              : null;

          return {
            site: item.name || `Item ${index + 1}`,
            online: onlineCount,
            alert: latestAlert ? formatTimeAgo(latestAlert.timestamp) : '—',
            osList, // Send list of OS strings for MetricCard to render
            id: item._type === 'device' ? item.device_id : item.site_id,
            type: item._type,
          };
        });

        setMonitoredItems(sitesWithDefaults);
        setAlerts(finalAlerts);
      } catch (err) {
        console.error('Failed to fetch monitored dashboard data:', err);
        clearMonitoredBoard();
      }

      setLoading(false);
    };

    fetchData();
    const interval = setInterval(fetchData, 30000); // Poll every 30s
    return () => clearInterval(interval);
  }, []);

  if (loading) {
    return (
      <div className="h-screen bg-black text-gray-200 flex items-center justify-center">
        <p className="text-teal-400 animate-pulse">Loading sites...</p>
      </div>
    );
  }

  return (
    <div className="h-full bg-black text-gray-200 p-2 flex flex-col overflow-hidden rounded-2xl shadow-xl border border-gray-800">
      {/* Summary Stats */}
      {summary && (
        <div className="grid grid-cols-2 md:grid-cols-5 gap-2 mb-2 shrink-0">
          <Card className="bg-[#080A0A] border border-gray-800">
            <CardContent className="p-2 text-center">
              <p className="text-xs text-gray-400">Total Devices</p>
              <p className="text-xl font-bold text-white">{summary.total_devices || 0}</p>
            </CardContent>
          </Card>
          <Card className="bg-[#080A0A] border border-gray-800">
            <CardContent className="p-2 text-center">
              <p className="text-xs text-gray-400">Online</p>
              <p className="text-xl font-bold text-green-400">
                {summary.connectivity_counts?.online || 0}
              </p>
            </CardContent>
          </Card>
          <Card className="bg-[#080A0A] border border-gray-800">
            <CardContent className="p-2 text-center">
              <p className="text-xs text-gray-400">Offline</p>
              <p className="text-xl font-bold text-red-400">
                {summary.connectivity_counts?.offline || 0}
              </p>
            </CardContent>
          </Card>
          <Card className="bg-[#080A0A] border border-gray-800">
            <CardContent className="p-2 text-center">
              <p className="text-xs text-gray-400">Active</p>
              <p className="text-xl font-bold text-teal-400">
                {summary.lifecycle_counts?.active || 0}
              </p>
            </CardContent>
          </Card>

          {/* System Pulse (compact) */}
          <Card className="bg-[#080A0A] border border-gray-800">
            <CardContent className="p-2">
              <p className="text-xs text-gray-400 text-center mb-1">System Pulse</p>
              <div className="flex justify-center space-x-1 mb-1">
                {Array.from({ length: 10 }).map((_, i) => {
                  const activeCount = Math.ceil((systemPulse.load_score || 0) / 10);
                  const isActive = i < activeCount;
                  let colorClass = 'bg-gray-800';
                  if (isActive) {
                    if (i < 6) colorClass = 'bg-green-500';
                    else if (i < 8) colorClass = 'bg-yellow-500';
                    else colorClass = 'bg-red-500';
                  }
                  return (
                    <span
                      key={i}
                      className={`w-2 h-2 rounded-full ${colorClass} ${isActive ? 'scale-110' : ''}`}
                    />
                  );
                })}
              </div>
              <p className="text-[10px] text-gray-400 font-mono text-center truncate">
                Load {systemPulse.load_score || 0}%{' · '}
                CPU {Math.round(systemPulse.cpu_percent || 0)}%{' · '}
                Mem {Math.round(systemPulse.memory_percent || 0)}%
              </p>
            </CardContent>
          </Card>
        </div>
      )}

      {/* Main Content: Two columns */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-2 flex-1 min-h-0 overflow-hidden">
        {/* Left Column: Connected Sites */}
        <Card className="col-span-2 relative bg-[#080A0A] border border-primary bg-no-repeat bg-center bg-cover h-full flex flex-col overflow-hidden">
          {/* Overlay for opacity */}
          <div className="absolute inset-0 bg-black/40 rounded-xl z-0"></div>

          <CardContent className="p-3 relative z-10 flex flex-col h-full overflow-hidden">
            <h2 className="text-lg font-semibold text-white mb-2 shrink-0">Monitored Resources</h2>

            {extraMonitored > 0 && (
              <p className="text-xs text-amber-400 font-mono mb-1 shrink-0">
                +{extraMonitored} more item{extraMonitored > 1 ? 's' : ''} hidden — showing top{' '}
                {MAX_AUTO_MONITORED_CARDS}
              </p>
            )}

            <div className="flex-1 overflow-y-auto min-h-0">
              {monitoredItems.length === 0 ? (
                <div className="text-center py-10 text-gray-400">
                  <p>No items monitored.</p>
                  <p className="text-sm mt-2">
                    Go to Sites or Devices to add them to the dashboard.
                  </p>
                </div>
              ) : (
                <MetricCard sites={monitoredItems} onItemClick={handleItemClick} />
              )}
            </div>

            {/* Buttons */}
            <div className="flex justify-center gap-2 mt-2 shrink-0 flex-wrap">
              <Button
                size="sm"
                onClick={() => {
                  navigate('/data-collection');
                }}
                className="bg-transparent text-teal-400 border border-teal-400 hover:bg-teal-400/10 h-8 text-xs"
              >
                Data Collection
              </Button>
              <Button
                size="sm"
                onClick={() => {
                  navigate('/useractivity');
                }}
                className="bg-transparent text-teal-400 border border-teal-400 hover:bg-teal-400/10 h-8 text-xs"
              >
                User Activity
              </Button>
              <Button
                size="sm"
                onClick={() => {
                  navigate('/agents');
                }}
                className="bg-transparent text-teal-400 border border-teal-400 hover:bg-teal-400/10 h-8 text-xs"
              >
                Agents
              </Button>
            </div>
          </CardContent>

          {/* World Map Background */}
          <div className="absolute inset-0 overflow-hidden rounded-xl z-0 pointer-events-none">
            <img
              src={WorldMapImage}
              alt="World Map"
              className="w-full h-full object-cover opacity-20"
            />
          </div>

          {/* Glowing Site Dots */}
          <div className="absolute inset-0 pointer-events-none z-10">
            {monitoredItems.map((site, index) => (
              <span
                key={index}
                className="absolute w-3 h-3 bg-cyan-400 rounded-full blur-md animate-pulse"
                style={{
                  top: `${30 + ((index * 17) % 40)}%`,
                  left: `${20 + ((index * 23) % 60)}%`,
                }}
                title={site.site}
              ></span>
            ))}
          </div>
        </Card>

        {/* Right Column: AI Assistant (Pulse/Alerts moved to StatusStrip above) */}
        <div className="flex flex-col gap-2 h-full min-h-0 overflow-hidden pr-1">
          <div className="flex-none">
            <Card className="bg-[#080A0A] border border-secondary shrink-0">
              <CardContent className="p-2">
                <div className="w-full min-w-0">
                  <ActiveAlertsTicker alerts={alerts} />
                </div>
              </CardContent>
            </Card>
          </div>

          {/* AI Assistant Widget */}
          <div className="flex-1 min-h-0 overflow-hidden">
            <AskAIWidget />
          </div>
        </div>
      </div>
    </div>
  );
}
