import React from "react";

export default function Device() {
  const stats = {
    cpu: { label: "CPU", value: "3,4rh", subtitle: "avg 3.4%" },
    memory: { label: "Memory", value: "4 MW", subtitle: "used 4GB" },
    disk: { label: "Disk", value: "25s ago", subtitle: "last check" },
  };

  const command = [
    { title: "Configuration updated", date: "22 Jan 2024" },
    { title: "Alert resolved", date: "2024-04-23" },
  ];

  const connections = [
    { name: "POS System" },
    { name: "Delivery App", status: "online" },
    { name: "Payment Gateway", status: "online" },
  ];

  const audit = [
    { title: "Configuration updated", date: "22 Jan 2024" },
    { title: "Alert resolved", date: "2024-04-23" },
  ];

  const sparkData = {
    small: [6, 3, 5, 4, 7, 6, 8],
    medium: [10, 14, 9, 12, 18, 16, 20, 18, 22],
  };

  return (
    <div className="min-h-screen bg-gradient-to-b from-[#041014] to-[#03121a] text-slate-200 p-6 sm:p-10 font-sans">
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
                DEVICE-00001
              </h1>
              <div className="flex items-center gap-2 mt-1 text-sm text-emerald-300">
                <span className="w-2 h-2 rounded-full bg-emerald-400 shadow-[0_0_10px_rgba(34,197,94,0.14)] inline-block" />
                <span className="font-medium">Healthy</span>
              </div>
            </div>
          </div>

          <div className="flex items-center gap-3">
            <ActionButton>Reconnect</ActionButton>
            <ActionButton>Run Command</ActionButton>
            <ActionButton>Audit Log</ActionButton>
            <ActionButton>Exit</ActionButton>
          </div>
        </header>

        {/* Main Grid */}
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-4 text-left">
          {/* Top Row */}
          <div className="lg:col-span-8 grid grid-cols-1 md:grid-cols-3 gap-4">
            {/* Health & Status */}
            <LargeCard className="md:col-span-2">
              <h3 className="text-sm text-slate-300 font-medium mb-4">
                HEALTH & STATUS
              </h3>
              <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
                <div className="flex flex-col gap-1">
                  <StatBlock data={sparkData.small} />
                  <div className="text-sm font-semibold tracking-tight">
                    {stats.cpu.label}
                  </div>
                  <div className="text-xs text-slate-400">
                    {stats.cpu.value}
                  </div>
                </div>

                <div className="flex flex-col gap-1">
                  <StatBlock data={sparkData.small} />
                  <div className="text-sm font-semibold tracking-tight">
                    {stats.memory.label}
                  </div>
                  <div className="text-xs text-slate-400">
                    {stats.memory.value}
                  </div>
                </div>

                <div className="flex flex-col gap-1">
                  <StatBlock data={sparkData.small} />
                  <div className="text-sm font-semibold tracking-tight">
                    {stats.disk.label}
                  </div>
                  <div className="text-xs text-slate-400">
                    {stats.disk.value}
                  </div>
                </div>
              </div>
            </LargeCard>

            {/* Settings */}
            <Card className="text-left">
              <h3 className="text-sm text-slate-300 font-medium">SETTINGS</h3>
              <div className="mt-3">
                <input
                  className="w-full bg-[#051a1d] border border-[#0e2f37] rounded px-3 py-2 text-sm outline-none placeholder:text-slate-500"
                  placeholder="Enter command"
                />
                <div className="mt-3 text-sm text-slate-200">restart POS</div>
                <div className="mt-1 text-xs text-slate-400">festart POS</div>
              </div>
            </Card>
          </div>

          {/* Command (Top right) */}
          <Card className="lg:col-span-4 text-left">
            <h3 className="text-sm text-slate-300 font-medium mb-3">COMMAND</h3>
            <div className="space-y-3 text-sm">
              {command.map((a) => (
                <div key={a.title} className="flex flex-col">
                  <div className="text-slate-200">{a.title}</div>
                  <div className="text-xs text-slate-400">{a.date}</div>
                </div>
              ))}
            </div>
          </Card>

          {/* Bottom Row */}
          <div className="lg:col-span-12 grid grid-cols-1 md:grid-cols-4 gap-4 text-left">
            {/* Connections */}
            <Card>
              <h3 className="text-sm text-slate-300 font-medium">
                CONNECTIONS
              </h3>
              <ul className="mt-4 space-y-3 text-sm">
                {connections.map((c) => (
                  <li
                    key={c.name}
                    className="flex items-center justify-between"
                  >
                    <span className="font-medium">{c.name}</span>
                    <div
                      className={`w-3 h-3 rounded-full ${
                        c.status === "online"
                          ? "bg-emerald-400 shadow-[0_0_8px_rgba(34,197,94,0.12)]"
                          : ""
                      }`}
                    />
                  </li>
                ))}
              </ul>
              <div className="mt-4">
                <div className="text-xs text-slate-400 mb-2 ">Network</div>
                <div className="w-full h-12">
                  <Sparkline data={sparkData.medium} height={48} animated />
                </div>
              </div>
            </Card>

            {/* Command Input */}
            <Card>
              <h3 className="text-sm text-slate-300 font-medium mb-3">
                COMMAND
              </h3>
              <div className="flex flex-col gap-3">
                <div className="relative">
                  <input
                    className="w-full bg-[#051a1d] border border-[#0e2f37] rounded px-3 py-2 text-sm outline-none placeholder:text-slate-500 pr-10"
                    placeholder="Enter command"
                  />
                  <button className="absolute right-1 top-1/2 -translate-y-1/2 px-2 py-1 rounded  text-teal-300 text-sm  hover:bg-teal-500/30">
                    &gt;
                  </button>
                </div>

                <div className="text-sm text-slate-200 mt-2">restart POS</div>
                <div className="text-xs text-slate-400">Logs</div>

                <div className="text-sm text-slate-200 mt-3">restart POS</div>
                <div className="text-xs text-slate-400">Logs</div>
              </div>
            </Card>

            {/* Audit & Logs */}
            <Card>
              <h3 className="text-sm text-slate-300 font-medium mb-3">
                AUDIT & LOGS
              </h3>
              <div className="space-y-3 text-sm">
                {audit.map((a) => (
                  <div key={a.title} className="flex flex-col">
                    <div className="text-slate-200">{a.title}</div>
                    <div className="text-xs text-slate-400">{a.date}</div>
                  </div>
                ))}
              </div>
            </Card>

            {/* Monitoring */}
            <Card>
              <h3 className="text-sm text-slate-300 font-medium">MONITORING</h3>
              <div className="mt-3 text-sm text-slate-200">Uptime</div>
              <div className="mt-2">
                <Sparkline data={[8, 10, 12, 10, 14, 16, 18]} height={48} />
              </div>
              <div className="mt-3 text-sm text-slate-200">Alerts</div>
              <div className="mt-2">
                <Sparkline data={[4, 6, 5, 6, 7, 6, 8]} height={48} />
              </div>
            </Card>
          </div>
        </div>
      </div>
    </div>
  );
}

/* === Small Reusable Components === */
function Card({ children, className = "" }) {
  return (
    <div
      className={`border border-[#0e2f37] rounded-2xl p-4 shadow-[inset_0_1px_0_rgba(255,255,255,0.02)] ${className}`}
    >
      {children}
    </div>
  );
}

function LargeCard({ children, className = "" }) {
  return (
    <div
      className={`bg-gradient-to-b from-[#072026] to-[#04181b] border border-[#103237] rounded-2xl p-4 shadow-[0_8px_30px_rgba(2,136,153,0.06)] ${className}`}
    >
      {children}
    </div>
  );
}

function ActionButton({ children }) {
  return (
    <button className="px-4 py-2 rounded-md text-sm font-medium border backdrop-blur-sm border-[#0b3b3f] text-teal-200 hover:brightness-105">
      {children}
    </button>
  );
}

function StatBlock({ title, value, subtitle, data = [] }) {
  return (
    <div className=" border border-[#0d2b2f] rounded-lg p-3 flex flex-col gap-2 text-left">
      <div className="w-full h-10">
        <Sparkline data={data} height={40} small />
      </div>
      <div className="mt-2">
        <div className="text-xs text-slate-400">{title}</div>
        <div className="text-sm font-semibold tracking-tight">{value}</div>
        <div className="text-xs text-slate-400">{subtitle}</div>
      </div>
    </div>
  );
}

function Sparkline({
  data = [4, 6, 5, 7, 6, 8, 9],
  height = 40,
  animated = false,
}) {
  const width = 144;
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
    <svg
      viewBox={`0 0 ${width} ${height}`}
      className="w-full h-full"
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
  );
}
