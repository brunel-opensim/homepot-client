import React, { useEffect, useState } from 'react';
import { Card, CardContent } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { CheckCircle2, XCircle, Apple, Package, Monitor, CheckCircle } from 'lucide-react';
import api from '@/services/api';
import { Line } from 'react-chartjs-2';
import {
  Chart as ChartJS,
  CategoryScale,
  LinearScale,
  PointElement,
  LineElement,
  Tooltip,
} from 'chart.js';
import { useNavigate } from 'react-router-dom';
import MetricCard from '@/components/Dashboard/MetricCard';
import AskAIWidget from '@/components/Dashboard/AskAIWidget';

// Register Chart.js modules
ChartJS.register(CategoryScale, LinearScale, PointElement, LineElement, Tooltip);

export default function Dashboard() {
  const cpuData = {
    labels: Array.from({ length: 12 }, (_, i) => i + 1),
    datasets: [
      {
        label: 'CPU',
        data: [20, 40, 35, 60, 50, 70, 60, 55, 65, 45, 50, 55],
        borderColor: '#22c55e',
        backgroundColor: 'rgba(34,197,94,0.2)',
        tension: 0.4,
      },
    ],
  };

  const cpuOptions = {
    responsive: true,
    plugins: { legend: { display: false } },
    scales: { x: { display: false }, y: { display: false } },
  };

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

  useEffect(() => {
    const fetchSites = async () => {
      try {
        const data = await api.sites.list();
        const fetchedSites = data?.sites || [];

        const icons = [<WindowsIcon />, <AppleIcon />]; // rotate between these

        const sitesWithDefaults = fetchedSites.map((site, index) => ({
          site: site.name || `Site ${index + 1}`,
          online: Math.floor(Math.random() * 10) + 1,
          alert: ['2m ago', '5m ago', '—'][index % 3],
          // Alternate icons between Apple and Windows
          icon: icons[index % icons.length],
        }));

        setSites(sitesWithDefaults);
      } catch (err) {
        console.error('Failed to fetch sites:', err);
      } finally {
        setLoading(false);
      }
    };

    fetchSites();
  }, []);

  const handleLogout = async () => {
    try {
      await api.auth.logout(); // calling your API logout
      window.location.href = '/login'; // redirect
    } catch (err) {
      console.error('Logout failed:', err);
    }
  };

  if (loading) {
    return (
      <div className="min-h-screen bg-black text-gray-200 flex items-center justify-center">
        <p className="text-teal-400 animate-pulse">Loading sites...</p>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-black text-gray-200 p-6">
      {/* Top Bar */}
      <div className="flex justify-between items-center mb-6">
        <div className="flex space-x-14">
          <div className="flex flex-col items-start">
            <h1 className="text-2xl font-bold text-white">HOMEPOT</h1>
            <h3 className="text-xl font-medium text-white">CLIENT</h3>
          </div>
          <span className="text-green-400 font-semibold">All Systems Operational</span>
        </div>
        <div className="py-2 px-4 text-sm font-semibold rounded-lg flex items-center gap-2 bg-gray-900 border border-green-400">
          <span className="w-2 h-2 bg-green-400 rounded-full"></span>
          <span>Operational</span>
        </div>

        {/* Logout Button */}
        <button
          onClick={handleLogout}
          className="py-2 px-4 text-sm font-semibold rounded-lg bg-red-500 hover:bg-red-600 text-white transition"
        >
          Logout
        </button>
      </div>

      {/* Main Content: Two columns */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Left Column: Connected Sites */}
        <Card className="col-span-2 relative bg-[#080A0A] border border-primary bg-no-repeat bg-center bg-cover">
          {/* Overlay for opacity */}
          <div className="absolute inset-0 bg-black/40 rounded-xl"></div>

          <CardContent className="p-4 relative z-10 flex flex-col h-full">
            <h2 className="text-lg font-semibold text-white mb-4">Connected Sites</h2>

            <MetricCard sites={sites} />

            {/* Buttons */}
            <div className="flex justify-center space-x-4 mt-8">
              <Button
                onClick={() => {
                  navigate('/sites');
                }}
                className="bg-transparent text-teal-400 border border-teal-400 hover:bg-teal-400/10"
              >
                View Sites
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
                Agent
              </Button>
              <Button className="bg-transparent text-teal-400 border border-teal-400 hover:bg-teal-400/10">
                Send Notification
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
          <div className="absolute inset-0">
            <span
              className="absolute w-3 h-3 bg-cyan-400 rounded-full blur-md animate-pulse"
              style={{ top: '30%', left: '20%' }}
            ></span>
            <span
              className="absolute w-3 h-3 bg-cyan-400 rounded-full blur-md animate-pulse"
              style={{ top: '40%', left: '50%' }}
            ></span>
            <span
              className="absolute w-3 h-3 bg-cyan-400 rounded-full blur-md animate-pulse"
              style={{ top: '55%', left: '70%' }}
            ></span>
            <span
              className="absolute w-3 h-3 bg-cyan-400 rounded-full blur-md animate-pulse"
              style={{ top: '65%', left: '30%' }}
            ></span>
          </div>
        </Card>

        {/* Right Column: CPU, Heartbeat, Active Alerts */}
        <div className="flex flex-col gap-6 h-full">
          <Card className="col-span-2 relative bg-[#080A0A] border border-secondary bg-no-repeat bg-center bg-cover">
            <CardContent className="p-4">
              <h2 className="text-lg font-semibold text-white mb-2">CPU Usage</h2>
              <Line data={cpuData} options={cpuOptions} height={100} />
            </CardContent>
          </Card>

          <Card className="col-span-2 relative bg-[#080A0A] border border-secondary bg-no-repeat bg-center bg-cover">
            <CardContent className="p-4">
              <h2 className="text-lg font-semibold text-white mb-2">Heartbeat Status</h2>
              <div className="flex space-x-2">
                {Array.from({ length: 12 }).map((_, i) => (
                  <span
                    key={i}
                    className={`w-4 h-4 rounded-full ${
                      i % 4 === 0 ? 'bg-green-400' : i % 3 === 0 ? 'bg-orange-400' : 'bg-gray-600'
                    }`}
                  ></span>
                ))}
              </div>
              <p className="text-xs text-gray-400 mt-2">Last 5 min</p>
            </CardContent>
          </Card>

          <Card className="col-span-2 relative bg-[#080A0A] border border-secondary bg-no-repeat bg-center bg-cover">
            <CardContent className="p-4">
              <h2 className="text-lg font-semibold text-white mb-2">Active Alerts</h2>
              <ul className="space-y-2">
                <li className="text-red-400 text-sm">Device offline – 6m ago</li>
                <li className="text-red-400 text-sm">Site not responding – 9m ago</li>
                <li className="text-red-400 text-sm">High latency detected – 17m ago</li>
              </ul>
            </CardContent>
          </Card>

          {/* AI Assistant Widget */}
          <div className="col-span-2 h-[400px]">
            <AskAIWidget />
          </div>
        </div>
      </div>
    </div>
  );
}
