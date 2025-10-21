import React from "react";
import { useParams, useNavigate } from "react-router-dom";
import { Button } from "@/components/ui/button";

// Sparkline component
function Sparkline({
  data = [4, 6, 5, 7, 6, 8, 9],
  height = 48,
  animated = false,
}) {
  const width = data.length * 20;
  const max = Math.max(...data) || 1;
  const min = Math.min(...data) || 0;

  const points = data
    .map((d, i) => {
      const x = (i / (data.length - 1 || 1)) * width;
      const y = height - ((d - min) / (max - min || 1)) * height;
      return `${x},${y}`;
    })
    .join(" ");

  const pathD = `M${points.split(" ").join(" L ")}`;

  return (
    <div className="w-full h-[60px] sm:h-[100px] md:h-[150px] overflow-hidden">
      <svg
        viewBox={`0 0 ${width} ${height}`}
        className={`w-full h-full ${animated ? "animate-pulse" : ""}`}
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

function Wave({}) {
  return (
    <svg
      className="w-6 h-4"
      viewBox="0 0 24 8"
      fill="none"
      xmlns="http://www.w3.org/2000/svg"
    >
      <path
        d="M0 4 C2 0, 4 8, 6 4 S10 0, 12 4 S16 8, 18 4 S22 0, 24 4"
        stroke="#06b6d4"
        strokeWidth="1.5"
        fill="transparent"
      >
        <animate
          attributeName="d"
          // dur="2s"
          repeatCount="indefinite"
          values="
          M0 4 C2 0, 4 8, 6 4 S10 0, 12 4 S16 8, 18 4 S22 0, 24 4;
          M0 4 C2 8, 4 0, 6 4 S10 8, 12 4 S16 0, 18 4 S22 8, 24 4;
          M0 4 C2 0, 4 8, 6 4 S10 0, 12 4 S16 8, 18 4 S22 0, 24 4;
          M0 4 C2 0, 4 8, 6 4 S10 0, 12 4 S16 8, 18 4 S22 0, 24 4;
          M0 4 C2 0, 4 8, 6 4 S10 0, 12 4 S16 8, 18 4 S22 0, 24 4
        "
        />
      </path>
    </svg>
  );
}
const sparkData = {
  small: [6, 3, 5, 4, 7, 6, 8],
  medium: [10, 14, 9, 12, 18, 16, 20, 18, 22],
};

export default function SiteDeviceScreen() {
  const { deviceId: id } = useParams();
  const navigate = useNavigate();

  const WindowsIcon = () => (
    <img
      src="https://cdn.jsdelivr.net/gh/simple-icons/simple-icons/icons/windows.svg"
      alt="Windows"
      className="w-5 h-5"
      style={{
        filter:
          "invert(86%) sepia(36%) saturate(319%) hue-rotate(122deg) brightness(99%) contrast(98%)",
      }}
    />
  );

  // Apple Icon (light grey)
  const AppleIcon = () => (
    <img
      src="https://cdn.jsdelivr.net/gh/simple-icons/simple-icons/icons/apple.svg"
      alt="Apple"
      className="w-5 h-5 text-gray-300"
      style={{
        filter:
          "invert(86%) sepia(36%) saturate(319%) hue-rotate(122deg) brightness(99%) contrast(98%)",
      }}
    />
  );

  const LinuxIcon = () => (
    <img
      src="https://cdn.jsdelivr.net/gh/simple-icons/simple-icons/icons/linux.svg"
      alt="Linux"
      className="w-5 h-5"
      style={{
        filter:
          "invert(86%) sepia(36%) saturate(319%) hue-rotate(122deg) brightness(99%) contrast(98%)",
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
          "invert(86%) sepia(36%) saturate(319%) hue-rotate(122deg) brightness(99%) contrast(98%)",
      }}
    />
  );

  const site = {
    id,
    name: `SITE-${id}`,
    location: "New York",
    lastPing: "1m ago",
    lastAlert: "5m ago",
    devices: [
      {
        id: "00002",
        name: "Device-00002",
        healthy: true,
        uptime: "12h",
        icon: <WindowsIcon />,
      },
      {
        id: "00003",
        name: "Device-00003",
        healthy: true,
        uptime: "10h",
        icon: <AppleIcon />,
      },
      {
        id: "00004",
        name: "Device-00004",
        healthy: true,
        uptime: "8h",
        icon: <LinuxIcon />,
      },
      {
        id: "00005",
        name: "Device-00005",
        healthy: true,
        uptime: "6h",
        icon: <AndroidIcon />,
      },
      {
        id: "00006",
        name: "Device-00006",
        healthy: true,
        uptime: "9h",
        icon: <WindowsIcon />,
      },
      {
        id: "00007",
        name: "Device-00007",
        healthy: true,
        uptime: "5h",
        icon: <AppleIcon />,
      },
    ],
    alerts: [
      {
        time: "5 min ago",
        event: "Notifications Sent",
        color: "text-textPrimary",
      },
      { time: "10 min ago", event: "Device Offline", color: "text-red-400" },
      { time: "30 min ago", event: "Device Offline", color: "text-red-400" },
    ],

    error: [{ time: "1 hour ago", event: "Error", color: "text-red-400" }],
  };

  return (
    <div className="min-h-screen bg-[#0b0e13] text-white px-4 sm:px-6 lg:px-10 py-6">
      {/* Header Section */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 mb-8">
        <div className="text-start">
          <h1 className="text-2xl sm:text-3xl font-semibold">{site.name}</h1>
          <p className="text-lg sm:text-xl text-textPrimary">{site.location}</p>

          <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between mt-2 gap-44">
            {/* Last Ping / Last Alert */}
            <div className="flex flex-wrap gap-4 text-xs sm:text-sm text-textPrimary">
              <span>Last Ping: {site.lastPing}</span>
              <span>Last Alert: {site.lastAlert}</span>
            </div>

            {/* Icons with border and spacing */}
            <div className="flex items-center gap-5 border border-[#1f2735] rounded-md p-2 mt-2 sm:mt-0">
              <WindowsIcon />
              <AppleIcon />
              <AndroidIcon />
            </div>

            {/* <div className="flex items-center gap-2 border border-[#1f2735] rounded-md p-2 mt-2 sm:mt-0">
              <Wave />
            </div> */}
          </div>
        </div>

        <div className="flex flex-wrap gap-3 ">
          <Button className="bg-transparent border border-teal-400 text-teal-300 hover:bg-teal-900/30 text-sm sm:text-base">
            View Devices
          </Button>
          <Button className="bg-transparent border border-teal-400 text-teal-300 hover:bg-teal-900/30 text-sm sm:text-base">
            Run Troubleshoot
          </Button>
        </div>
      </div>

      <div className="border-b border-[#1f2735] mb-6 border"></div>
      {/* Main Layout */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-8  ">
        {/* Device Overview */}

        <div className=" lg:col-span-2 space-y-4 border-r border-[#1f2735] pr-4">
          <h2 className="text-lg sm:text-xl font-semibold mb-2 text-start">
            Device Overview
          </h2>
          <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-3 gap-4">
            {site.devices.map((device) => (
              <div
                key={device.id}
                className="bg-[#141a24] border border-[#1f2735] rounded-xl p-4 hover:border-teal-400 transition"
              >
                <div className="flex items-center justify-between mb-2">
                  <h3 className="text-md font-medium">{device.name}</h3>
                  {device.icon}
                </div>
                <p
                  className={`text-md mb-2 text-start ${
                    device.healthy ? "text-textPrimary" : "text-red-400"
                  }`}
                >
                  {device.healthy ? "Healthy" : "Offline"}
                </p>
                <p className="text-start text-textPrimary text-xs mt-1">
                  Uptime {device.uptime}
                </p>
                <p className="text-start text-textPrimary text-xs mt-1">
                  2025-09-15&nbsp;&nbsp;07:30
                </p>
              </div>
            ))}
          </div>
        </div>

        {/* Live Metrics + Alerts */}
        <div className="space-y-4">
          <h2 className="text-lg sm:text-xl font-semibold mb-2 text-start">
            Live Metrics
          </h2>

          {/* Make metrics horizontally scrollable on small screens */}
          <div className="flex flex-col sm:flex-row sm:overflow-x-auto gap-4">
            <div className="bg-[#141a24] flex-1 min-w-[220px] border border-[#1f2735] rounded-xl p-4">
              <p className="text-sm mb-2 text-textPrimary flex items-center gap-2">
                CPU Usage
              </p>
              <Sparkline data={sparkData.medium} height={200} animated />
            </div>
            <div className="bg-[#141a24] flex-1 min-w-[220px] border border-[#1f2735] rounded-xl p-4">
              <p className="text-sm mb-2 text-textPrimary flex items-center gap-2">
                Memory Usage
              </p>
              <Sparkline data={sparkData.small} height={200} animated />
            </div>
          </div>

          <h2 className="text-lg sm:text-xl font-semibold mt-6 mb-2 text-start">
            Alerts & Events
          </h2>
          <div className="bg-[#141a24] border border-[#1f2735] rounded-xl p-4 space-y-3">
            {site.alerts.map((alert, index) => (
              <div
                key={index}
                className="flex flex-wrap justify-between text-sm sm:text-base"
              >
                <span className="text-textPrimary">{alert.time}</span>
                <span className={alert.color}>{alert.event}</span>
              </div>
            ))}
          </div>
          <div className="bg-[#141a24] border border-[#1f2735] rounded-xl p-4 space-y-3">
            {site.error.map((alert, index) => (
              <div
                key={index}
                className="flex flex-wrap justify-between text-sm sm:text-base"
              >
                <span className="text-textPrimary">{alert.time}</span>
                <span className={alert.color}>{alert.event}</span>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}
