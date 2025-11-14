import React, { useEffect, useState, useMemo } from 'react';
import { Button } from '@/components/ui/button';
import api from '@/services/api';

// Sparkline component (unchanged, small improvement: guard for length 1)
function Sparkline({ data = [4, 6, 5, 7, 6, 8, 9], height = 48, animated = false }) {
  const width = Math.max(1, data.length) * 20;
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
    <div className="w-full h-[60px] sm:h-[100px] md:h-[150px] overflow-hidden">
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
    </div>
  );
}

const sparkData = {
  small: [6, 3, 5, 4, 7, 6, 8],
  medium: [10, 14, 9, 12, 18, 16, 20, 18, 22],
};

export default function SiteDeviceScreen() {
  // removed siteId dependency — showing overall devices
  const [devices, setDevices] = useState([]);
  const [loading, setLoading] = useState(true);

  // fetch devices once on mount
  useEffect(() => {
    let cancelled = false;

    const fetchDevicesData = async () => {
      setLoading(true);
      try {
        const data = await api.devices.list();
        if (cancelled) return;
        const fetchedDevices = data?.devices || [];
        console.log('fetchedDevices: ', fetchedDevices);
        setDevices(fetchedDevices);
      } catch (error) {
        console.error('Error from fetchDevicesData:', error?.message ?? error);
        setDevices([]);
      } finally {
        if (!cancelled) setLoading(false);
      }
    };

    fetchDevicesData();
    return () => {
      cancelled = true;
    };
  }, []);

  // Show all devices (no filtering by site)
  const allDevices = useMemo(() => devices, [devices]);

  // Basic "site" info for header (now reflects overall view)
  const site = useMemo(() => {
    return {
      id: 'all',
      name: 'All Sites',
      location: 'Multiple',
      lastPing: '—',
      lastAlert: '—',
      devices: allDevices.map((d) => {
        return {
          id:
            d.device_id ??
            d.id ??
            `${d.name ?? 'device'}-${Math.random().toString(36).slice(2, 7)}`,
          name: d.name ?? d.device_id ?? 'Unnamed device',
          healthy: d.healthy ?? true,
          uptime: d.uptime ?? null,
          icon: null,
          created_at: d.created_at ?? null,
          raw: d,
        };
      }),
    };
  }, [allDevices]);

  // helper for formatting created_at into Asia/Kolkata locale
  const formatDateIST = (isoString) => {
    if (!isoString) return '—';
    try {
      const dt = new Date(isoString);
      return dt.toLocaleString('en-IN', { timeZone: 'Asia/Kolkata' });
    } catch {
      return isoString;
    }
  };

  // Simple Icon components kept but unused unless you map them
  const WindowsIcon = () => (
    <img
      src="https://cdn.jsdelivr.net/gh/simple-icons/simple-icons/icons/windows.svg"
      alt="Windows"
      className="w-5 h-5"
      style={{
        filter:
          'invert(86%) sepia(36%) saturate(319%) hue-rotate(122deg) brightness(99%) contrast(98%)',
      }}
    />
  );
  const AppleIcon = () => (
    <img
      src="https://cdn.jsdelivr.net/gh/simple-icons/simple-icons/icons/apple.svg"
      alt="Apple"
      className="w-5 h-5 text-gray-300"
      style={{
        filter:
          'invert(86%) sepia(36%) saturate(319%) hue-rotate(122deg) brightness(99%) contrast(98%)',
      }}
    />
  );
  const AndroidIcon = () => (
    <img
      src="https://cdn.jsdelivr.net/gh/simple-icons/simple-icons/icons/android.svg"
      alt="Android"
      className="w-5 h-5 text-gray-300"
      style={{
        filter:
          'invert(86%) sepia(36%) saturate(319%) hue-rotate(122deg) brightness(99%) contrast(98%)',
      }}
    />
  );

  return (
    <div className="min-h-screen bg-[#0b0e13] text-white px-4 sm:px-6 lg:px-10 py-6">
      {/* Header Section */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 mb-8">
        <div className="text-start">
          <h1 className="text-2xl sm:text-3xl font-semibold">{site.name}</h1>
          <p className="text-lg sm:text-xl text-textPrimary">{site.location}</p>

          <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between mt-2 gap-44">
            <div className="flex flex-wrap gap-4 text-xs sm:text-sm text-textPrimary">
              <span>Last Ping: {site.lastPing}</span>
              <span>Last Alert: {site.lastAlert}</span>
            </div>

            <div className="flex items-center gap-5 border border-[#1f2735] rounded-md p-2 mt-2 sm:mt-0">
              <WindowsIcon />
              <AppleIcon />
              <AndroidIcon />
            </div>
          </div>
        </div>

        <div className="flex flex-wrap gap-3">
          <Button className="bg-transparent border border-teal-400 text-teal-300 hover:bg-teal-900/30 text-sm sm:text-base">
            View Devices
          </Button>
          <Button className="bg-transparent border border-teal-400 text-teal-300 hover:bg-teal-900/30 text-sm sm:text-base">
            Run Troubleshoot
          </Button>
        </div>
      </div>

      <div className="border-b border-[#1f2735] mb-6"></div>

      {/* Main Layout */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
        {/* Device Overview (uses API data) */}
        <div className="lg:col-span-2 space-y-4 border-r border-[#1f2735] pr-4">
          <h2 className="text-lg sm:text-xl font-semibold mb-2 text-start">Device Overview</h2>

          {loading ? (
            <div className="text-textPrimary">Loading devices...</div>
          ) : site.devices.length === 0 ? (
            <div className="text-textPrimary">No devices found.</div>
          ) : (
            <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-3 gap-4">
              {site.devices.map((device) => (
                <div
                  key={device.id}
                  className="bg-[#141a24] border border-[#1f2735] rounded-xl p-4 hover:border-teal-400 transition"
                >
                  <div className="flex items-center justify-between mb-2">
                    <h3 className="text-md font-medium">{device.name}</h3>
                    {device.icon ? device.icon : null}
                  </div>

                  <p
                    className={`text-md mb-2 text-start ${device.healthy ? 'text-textPrimary' : 'text-red-400'}`}
                  >
                    {device.healthy ? 'Healthy' : 'Offline'}
                  </p>

                  <p className="text-start text-textPrimary text-xs mt-1">
                    {device.uptime
                      ? `Uptime ${device.uptime}`
                      : device.created_at
                        ? `Created: ${formatDateIST(device.created_at)}`
                        : '—'}
                  </p>

                  <p className="text-start text-textPrimary text-xs mt-1">
                    {device.raw?.ip_address ? `IP: ${device.raw.ip_address}` : null}
                  </p>
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Live Metrics + Alerts (keeps UI but uses generic data) */}
        <div className="space-y-4">
          <h2 className="text-lg sm:text-xl font-semibold mb-2 text-start">Live Metrics</h2>
          <div className="flex flex-col sm:flex-row sm:overflow-x-auto gap-4">
            <div className="bg-[#141a24] flex-1 min-w-[220px] border border-[#1f2735] rounded-xl p-4">
              <p className="text-sm mb-2 text-textPrimary flex items-center gap-2">CPU Usage</p>
              <Sparkline data={sparkData.medium} height={200} animated />
            </div>
            <div className="bg-[#141a24] flex-1 min-w-[220px] border border-[#1f2735] rounded-xl p-4">
              <p className="text-sm mb-2 text-textPrimary flex items-center gap-2">Memory Usage</p>
              <Sparkline data={sparkData.small} height={200} animated />
            </div>
          </div>

          <h2 className="text-lg sm:text-xl font-semibold mt-6 mb-2 text-start">Alerts & Events</h2>
          <div className="bg-[#141a24] border border-[#1f2735] rounded-xl p-4 space-y-3">
            <div className="text-textPrimary text-sm">No alerts available from API.</div>
          </div>

          <div className="bg-[#141a24] border border-[#1f2735] rounded-xl p-4 space-y-3">
            <div className="text-textPrimary text-sm">No errors reported.</div>
          </div>
        </div>
      </div>
    </div>
  );
}
