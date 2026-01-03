import React, { useEffect, useState } from 'react';
import { Card, CardContent } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { CheckCircle2, XCircle, Apple, Package, Monitor, CheckCircle } from 'lucide-react';
import api from '@/services/api';
import { useNavigate } from 'react-router-dom';
import MetricCard from '@/components/Dashboard/MetricCard';
import AskAIWidget from '@/components/Dashboard/AskAIWidget';
import ActiveAlertsTicker from '@/components/Dashboard/ActiveAlertsTicker';

export default function Dashboard() {
  const [alerts, setAlerts] = useState([]);
  const [systemPulse, setSystemPulse] = useState({ status: 'idle', load_score: 0 });

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

  // Apple Icon (light grey)
  const AppleIcon = () => (
    <img
      src="https://cdn.jsdelivr.net/gh/simple-icons/simple-icons/icons/apple.svg"
      alt="Apple"
      className="w-5 h-5 text-gray-300"
      style={{ filter: 'invert(80%) grayscale(100%)' }}
    />
  );

  const WindowsIcon = () => (
    <img
      src="https://cdn.jsdelivr.net/gh/simple-icons/simple-icons/icons/windows.svg"
      alt="Windows"
      className="w-5 h-5"
      style={{
        filter:
          'invert(47%) sepia(100%) saturate(5000%) hue-rotate(180deg) brightness(95%) contrast(105%)',
      }}
    />
  );

  const [sites, setSites] = useState([]);
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
      try {
        // 1. Fetch Sites
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

        // Filter monitored items
        const monitoredSites = fetchedSites.filter((s) => s.is_monitored);
        const monitoredDevices = fetchedDevices.filter((d) => d.is_monitored);

        let itemsToDisplay = [];

        if (monitoredSites.length > 0 || monitoredDevices.length > 0) {
          itemsToDisplay = [
            ...monitoredSites.map((s) => ({ ...s, _type: 'site' })),
            ...monitoredDevices.map((d) => ({ ...d, _type: 'device' })),
          ];
        }
        // else {
        //      // Fallback removed: Dashboard is empty if nothing is monitored
        //      itemsToDisplay = [];
        // }

        const icons = [<WindowsIcon />, <AppleIcon />]; // rotate between these

        const sitesWithDefaults = itemsToDisplay.map((item, index) => ({
          site: item.name || `Item ${index + 1}`,
          online: Math.floor(Math.random() * 10) + 1,
          alert: ['2m ago', '5m ago', '—'][index % 3],
          // Alternate icons between Apple and Windows
          icon: icons[index % icons.length],
          id: item._type === 'device' ? item.device_id : item.site_id,
          type: item._type,
        }));

        setSites(sitesWithDefaults);

        // 3. Fetch Dashboard Metrics (CPU & Alerts)
        // const metrics = await api.analytics.getDashboardMetrics(); // Deprecated for alerts

        // 4. Fetch AI Anomalies
        try {
          const anomalyData = await api.ai.getAnomalies();
          if (anomalyData && anomalyData.anomalies) {
            const formattedAlerts = anomalyData.anomalies.map((a) => ({
              message: `${a.device_name}: ${a.severity === 'critical' ? 'CRITICAL' : 'WARNING'} - Score ${a.score}`,
              timestamp: a.timestamp,
              severity: a.severity,
              device_id: a.device_id,
            }));
            setAlerts(formattedAlerts);
          }
        } catch (e) {
          console.error('Failed to fetch anomalies:', e);
        }
      } catch (err) {
        console.error('Failed to fetch dashboard data:', err);
      } finally {
        setLoading(false);
      }
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
    <div className="h-screen bg-black text-gray-200 p-4 flex flex-col overflow-hidden">
      {/* Main Content: Two columns */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4 flex-1 min-h-0">
        {/* Left Column: Connected Sites */}
        <Card className="col-span-2 relative bg-[#080A0A] border border-primary bg-no-repeat bg-center bg-cover h-full flex flex-col">
          {/* Overlay for opacity */}
          <div className="absolute inset-0 bg-black/40 rounded-xl"></div>

          <CardContent className="p-4 relative z-10 flex flex-col h-full">
            <h2 className="text-lg font-semibold text-white mb-4">Monitored Resources</h2>

            <div className="flex-1 overflow-y-auto">
              {sites.length === 0 ? (
                <div className="text-center py-10 text-gray-400">
                  <p>No items monitored.</p>
                  <p className="text-sm mt-2">
                    Go to Sites or Devices to add them to the dashboard.
                  </p>
                </div>
              ) : (
                <MetricCard sites={sites} onItemClick={handleItemClick} />
              )}
            </div>

            {/* Buttons */}
            <div className="flex justify-center gap-4 mt-4 shrink-0 flex-wrap">
              <Button
                onClick={() => {
                  navigate('/data-collection');
                }}
                className="bg-transparent text-teal-400 border border-teal-400 hover:bg-teal-400/10"
              >
                Data Collection
              </Button>
              <Button
                onClick={() => {
                  navigate('/useractivity');
                }}
                className="bg-transparent text-teal-400 border border-teal-400 hover:bg-teal-400/10"
              >
                User Activity
              </Button>
              <Button
                onClick={() => {
                  navigate('/agents');
                }}
                className="bg-transparent text-teal-400 border border-teal-400 hover:bg-teal-400/10"
              >
                Agents
              </Button>
            </div>
          </CardContent>

          {/* World Map Background */}
          <img
            src="src/assets/images/world-map.png"
            alt="World Map"
            className="absolute inset-0 w-full h-full object-cover opacity-20"
          />

          {/* Glowing Site Dots */}
          <div className="absolute inset-0 pointer-events-none">
            {sites.map((site, index) => (
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

        {/* Right Column: Heartbeat, Active Alerts, AI Assistant */}
        <div className="flex flex-col gap-4 h-full min-h-0 overflow-y-auto pr-1">
          {/* CPU Usage removed to give more space to AI Assistant */}

          <Card className="relative bg-[#080A0A] border border-secondary bg-no-repeat bg-center bg-cover shrink-0">
            <CardContent className="p-4">
              <h2 className="text-lg font-semibold text-white mb-2">System Pulse</h2>
              <div className="flex space-x-2">
                {Array.from({ length: 10 }).map((_, i) => {
                  // Calculate if this circle should be active based on load_score
                  // i=0 -> 10%, i=1 -> 20%, ..., i=9 -> 100%
                  // We light up if load_score is "close" to this threshold or higher
                  // e.g. load=12 -> i=0 (10%) is active, i=1 (20%) is inactive
                  // Using Math.ceil(load / 10) logic:
                  // load=1-10 -> 1 circle
                  // load=11-20 -> 2 circles
                  const activeCount = Math.ceil((systemPulse.load_score || 0) / 10);
                  const isActive = i < activeCount;

                  // Equalizer Color Logic
                  let colorClass = 'bg-gray-800';
                  if (isActive) {
                    if (i < 6) {
                      // 10% - 60%: Green
                      colorClass = 'bg-green-500 shadow-[0_0_8px_rgba(34,197,94,0.6)]';
                    } else if (i < 8) {
                      // 70% - 80%: Yellow/Orange
                      colorClass = 'bg-yellow-500 shadow-[0_0_8px_rgba(234,179,8,0.6)]';
                    } else {
                      // 90% - 100%: Red
                      colorClass = 'bg-red-500 shadow-[0_0_10px_rgba(239,68,68,0.8)]';
                    }
                  }

                  return (
                    <span
                      key={i}
                      className={`w-4 h-4 rounded-full transition-all duration-300 ${colorClass} ${isActive ? 'scale-110' : 'scale-100'}`}
                    ></span>
                  );
                })}
              </div>
              <div className="flex flex-col mt-2">
                <p className="text-xs text-gray-400 flex justify-between w-full font-mono">
                  <span>
                    Load:{' '}
                    <span
                      className={
                        systemPulse.load_score >= 90
                          ? 'text-red-400 font-bold'
                          : systemPulse.load_score >= 70
                            ? 'text-yellow-400'
                            : 'text-green-400'
                      }
                    >
                      {systemPulse.load_score}%
                    </span>
                  </span>
                  <span className="text-gray-700">|</span>
                  <span>
                    Jobs:{' '}
                    <span
                      className={
                        systemPulse.active_jobs > 5
                          ? 'text-red-400 font-bold'
                          : systemPulse.active_jobs > 0
                            ? 'text-yellow-400'
                            : 'text-green-400'
                      }
                    >
                      {systemPulse.active_jobs > 0 ? systemPulse.active_jobs : 'IDLE'}
                    </span>
                  </span>
                  <span className="text-gray-700">|</span>
                  <span>
                    CPU:{' '}
                    <span
                      className={
                        (systemPulse.cpu_percent || 0) >= 90
                          ? 'text-red-400 font-bold'
                          : (systemPulse.cpu_percent || 0) >= 70
                            ? 'text-yellow-400'
                            : 'text-green-400'
                      }
                    >
                      {Math.round(systemPulse.cpu_percent || 0)}%
                    </span>
                  </span>
                  <span className="text-gray-700">|</span>
                  <span>
                    Mem:{' '}
                    <span
                      className={
                        (systemPulse.memory_percent || 0) >= 90
                          ? 'text-red-400 font-bold'
                          : (systemPulse.memory_percent || 0) >= 70
                            ? 'text-yellow-400'
                            : 'text-green-400'
                      }
                    >
                      {Math.round(systemPulse.memory_percent || 0)}%
                    </span>
                  </span>
                </p>
              </div>
            </CardContent>
          </Card>

          <Card className="relative bg-[#080A0A] border border-secondary bg-no-repeat bg-center bg-cover shrink-0">
            <CardContent className="p-4">
              <h2 className="text-lg font-semibold text-white mb-2">Active Alerts</h2>
              <ActiveAlertsTicker alerts={alerts} />
            </CardContent>
          </Card>

          {/* AI Assistant Widget */}
          <div className="flex-1 min-h-[200px]">
            <AskAIWidget />
          </div>
        </div>
      </div>
    </div>
  );
}
