import React from "react";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import {
  CheckCircle2,
  XCircle,
  Apple,
  Package,
  Monitor,
  CheckCircle,
} from "lucide-react";
import { Line } from "react-chartjs-2";
import {
  Chart as ChartJS,
  CategoryScale,
  LinearScale,
  PointElement,
  LineElement,
  Tooltip,
} from "chart.js";

// Register Chart.js modules
ChartJS.register(
  CategoryScale,
  LinearScale,
  PointElement,
  LineElement,
  Tooltip
);

export default function Dashboard() {
  const cpuData = {
    labels: Array.from({ length: 12 }, (_, i) => i + 1),
    datasets: [
      {
        label: "CPU",
        data: [20, 40, 35, 60, 50, 70, 60, 55, 65, 45, 50, 55],
        borderColor: "#22c55e",
        backgroundColor: "rgba(34,197,94,0.2)",
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
      style={{ filter: "invert(80%) grayscale(100%)" }}
    />
  );
  const sites = [
    {
      site: "Site 1",
      online: 5,
      alert: "5m ago",
      icon: <CheckCircle className="w-5 h-5 text-green-400" />,
    },
    {
      site: "Site 3",
      online: 4,
      alert: "3m ago",
      icon: <XCircle className="w-5 h-5 text-red-500" />,
    },
    {
      site: "Site 4",
      online: 7,
      alert: "20m ago",
      icon: <AppleIcon />,
    },
    {
      site: "Site 5",
      online: 3,
      alert: "—",
      icon: <Package className="w-5 h-5 text-yellow-500" />,
    },
  ];

  const WindowsIcon = () => (
    <img
      src="https://cdn.jsdelivr.net/gh/simple-icons/simple-icons/icons/windows.svg"
      alt="Windows"
      className="w-5 h-5"
      style={{
        filter:
          "invert(47%) sepia(100%) saturate(5000%) hue-rotate(180deg) brightness(95%) contrast(105%)",
      }}
    />
  );
  // const sitesNew = [
  //   {
  //     site: "Site 1",
  //     online: 5,
  //     alert: "5m ago",
  //     icon: <CheckCircle className="w-5 h-5 text-green-400" />,
  //   },
  //   {
  //     site: "Site 2",
  //     online: 8,
  //     alert: "12m ago",
  //     icon: <WindowsIcon className="text-blue-400" />,
  //   },
  // ];

  return (
    <div className="min-h-screen bg-black text-gray-200 p-6">
      {/* Top Bar */}
      <div className="flex justify-between items-center mb-6">
        <div className="flex space-x-14">
          <div className="flex flex-col items-start">
            <h1 className="text-2xl font-bold text-white">HOMEPOT</h1>
            <h3 className="text-xl font-medium text-white">CLIENT</h3>
          </div>
          <span className="text-green-400 font-semibold">
            All Systems Operational
          </span>
        </div>
        <div className="py-2 px-4 text-sm font-semibold rounded-lg flex items-center gap-2 bg-gray-900 border border-green-400">
          <span className="w-2 h-2 bg-green-400 rounded-full"></span>
          <span>Operational</span>
        </div>
      </div>

      {/* Main Content: Two columns */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Left Column: Connected Sites */}
        <Card className="col-span-2 relative bg-[#080A0A] border border-secondary bg-no-repeat bg-center bg-cover">
          {/* Overlay for opacity */}
          <div className="absolute inset-0 bg-black/40 rounded-xl"></div>

          <CardContent className="p-4 relative z-10 flex flex-col h-full">
            <h2 className="text-lg font-semibold text-white mb-4">
              Connected Sites
            </h2>

            {/* Main flex row: map + sitesNew strip */}
            {/* <div className="relative flex gap-4 h-64"> */}

            <div className="relative flex flex-col items-end gap-6">
              {/* sitesNew vertical strip on the right */}
              <div className="flex flex-col items-end gap-4">
                {[
                  {
                    site: "Site 1",
                    online: 5,
                    alert: "5m ago",
                    status: <CheckCircle className="w-5 h-5 text-green-400" />,
                  },
                  {
                    site: "Site 2",
                    online: 8,
                    alert: "12m ago",
                    status: <WindowsIcon />,
                  },
                ].map((s, i) => (
                  <div
                    key={i}
                    className="w-40 p-3 rounded-xl border border-secondary bg-gray-800/90"
                  >
                    <div className="flex justify-between items-center">
                      <h3 className="text-md font-semibold text-text">
                        {s.site}
                      </h3>
                      <span>{s.status}</span>
                    </div>
                    <p className="text-sm text-green-400">{s.online} Online</p>
                    <p className="text-xs text-gray-400">
                      Last Alert: {s.alert}
                    </p>
                  </div>
                ))}
              </div>
            </div>

            {/* sites at bottom */}
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mt-4 z-10">
              {sites.map((s, i) => (
                <div
                  key={i}
                  className="w-40 p-3 rounded-xl border border-secondary bg-gray-800/90"
                  // className="p-3 rounded-xl border border-gray-700 bg-gray-800 hover:border-green-400 transition"
                >
                  <div className="flex justify-between items-center">
                    <h3 className="text-md text-text font-semibold">{s.site}</h3>
                    {s.icon}
                  </div>
                  <p className="text-sm text-green-400">{s.online} Online</p>
                  <p className="text-xs text-gray-400">Last Alert: {s.alert}</p>
                </div>
              ))}
            </div>

            {/* Buttons */}
            <div className="flex justify-center space-x-4 mt-8">
              <Button className="bg-primary text-secondary border border-secondary">
                View Sites
              </Button>
              <Button className="bg-primary text-secondary border border-secondary">
                View Devices
              </Button>
              <Button className="bg-primary text-secondary border border-secondary">
                Send Notification
              </Button>
              <Button className="bg-primary text-secondary border border-secondary">
                Run Troubleshoot
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
              style={{ top: "30%", left: "20%" }}
            ></span>
            <span
              className="absolute w-3 h-3 bg-cyan-400 rounded-full blur-md animate-pulse"
              style={{ top: "40%", left: "50%" }}
            ></span>
            <span
              className="absolute w-3 h-3 bg-cyan-400 rounded-full blur-md animate-pulse"
              style={{ top: "55%", left: "70%" }}
            ></span>
            <span
              className="absolute w-3 h-3 bg-cyan-400 rounded-full blur-md animate-pulse"
              style={{ top: "65%", left: "30%" }}
            ></span>
          </div>
        </Card>

        {/* Right Column: CPU, Heartbeat, Active Alerts */}
        <div className="flex flex-col gap-6 h-full">
          <Card className="col-span-2 relative bg-[#080A0A] border border-secondary bg-no-repeat bg-center bg-cover">
            <CardContent className="p-4">
              <h2 className="text-lg font-semibold text-white mb-2">
                CPU Usage
              </h2>
              <Line data={cpuData} options={cpuOptions} height={100} />
            </CardContent>
          </Card>

          <Card className="col-span-2 relative bg-[#080A0A] border border-secondary bg-no-repeat bg-center bg-cover">
            <CardContent className="p-4">
              <h2 className="text-lg font-semibold text-white mb-2">
                Heartbeat Status
              </h2>
              <div className="flex space-x-2">
                {Array.from({ length: 12 }).map((_, i) => (
                  <span
                    key={i}
                    className={`w-4 h-4 rounded-full ${
                      i % 4 === 0
                        ? "bg-green-400"
                        : i % 3 === 0
                        ? "bg-orange-400"
                        : "bg-gray-600"
                    }`}
                  ></span>
                ))}
              </div>
              <p className="text-xs text-gray-400 mt-2">Last 5 min</p>
            </CardContent>
          </Card>

          <Card className="col-span-2 relative bg-[#080A0A] border border-secondary bg-no-repeat bg-center bg-cover flex-1">
            <CardContent className="p-4">
              <h2 className="text-lg font-semibold text-white mb-2">
                Active Alerts
              </h2>
              <ul className="space-y-2">
                <li className="text-red-400 text-sm">
                  Device offline – 6m ago
                </li>
                <li className="text-red-400 text-sm">
                  Site not responding – 9m ago
                </li>
                <li className="text-red-400 text-sm">
                  High latency detected – 17m ago
                </li>
              </ul>
            </CardContent>
          </Card>
        </div>
      </div>
    </div>
  );
}
