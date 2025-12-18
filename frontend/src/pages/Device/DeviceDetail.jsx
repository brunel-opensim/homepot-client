import { Button } from '@/components/ui/button';
import api from '@/services/api';
import { trackActivity } from '@/utils/analytics';
import { debounce } from '@/utils/debounce';
import { ArrowLeft, Loader2 } from 'lucide-react';
import React, { useEffect, useRef, useState } from 'react';
import { useParams } from 'react-router-dom';

export default function Device() {
  const { id } = useParams();

  const [device, setDevice] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const [commandInput, setCommandInput] = useState('');

  const [cmdInput, setCmdInput] = useState('');

  const [showModal, setShowModal] = useState(false);
  const [progress, setProgress] = useState(0);

  useEffect(() => {
    const fetchDevice = async () => {
      try {
        const deviceData = await api.devices.getDeviceById(id); // returns an object, not array
        if (!deviceData) {
          setError('Device not found.');
        } else {
          setDevice(deviceData); // just use the object
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

  /** Track page view on load */
  /** Track page view correctly */
  useEffect(() => {
    trackActivity('page_view', `/devices/${id}`, { device_id: id });
  }, [id]);

  /* ===================== DEBOUNCED INPUT TRACKER ===================== */
  const debouncedTrackInput = useRef(
    debounce((value) => {
      trackActivity('input', `/devices/${id}`, {
        action: 'typing_command',
        command: value,
        device_id: id,
      });
    }, 600)
  ).current;

  /** Track header button clicks */
  const handleButtonClick = async (action) => {
    await trackActivity('click', `/devices/${id}`, {
      action,
      device_id: id,
    });
  };

  /** Tracks command submissions */
  const handleCommandSubmit = async () => {
    if (!commandInput) return;

    await trackActivity('form_submit', `/devices/${id}`, {
      action: 'input',
      command: commandInput,
      device_id: id,
    });

    setCommandInput('');
  };

  // const handleCmdInputChange = async (e) => {
  //   setCmdInput(e.target.value);

  //   // Track input activity
  //   if (e.target.value.trim() !== '') {
  //     await trackActivity('input', `/devices/${id}`, {
  //       action: 'typing_command',
  //       command: e.target.value.trim(),
  //       device_id: id,
  //     });
  //   }
  // };

  const handleCmdInputChange = (e) => {
    const value = e.target.value;
    setCmdInput(value);

    if (value.trim()) {
      debouncedTrackInput(value.trim());
    }
  };

  const handleSendCommand = async () => {
    if (!cmdInput.trim()) return;

    const payload = {
      type: 'command',
      action: cmdInput.trim(),
      params: {},
    };

    try {
      // Track command submission before sending
      await trackActivity('form_submit', `/devices/${id}`, {
        action: 'send_command',
        command: cmdInput.trim(),
        device_id: id,
      });

      setShowModal(true);
      setProgress(0);

      // UI fake-progress animation (optional)
      let value = 0;
      const interval = setInterval(() => {
        value += 15;
        setProgress((prev) => Math.min(prev + 15, 100));
        if (value >= 100) clearInterval(interval);
      }, 500);

      await api.agents.sendPush(id, payload);

      // close modal after 5 seconds & go back
      setTimeout(() => {
        setShowModal(false);
        window.location.href = `/dashboard`;
      }, 5000);

      setCmdInput('');
    } catch (err) {
      console.error('Failed to send command:', err);
      alert('Failed to send command');
      setShowModal(false);
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

  const stats = {
    cpu: { label: 'CPU', value: '3,4rh', subtitle: 'avg 3.4%' },
    memory: { label: 'Memory', value: '4 MW', subtitle: 'used 4GB' },
    disk: { label: 'Disk', value: '25s ago', subtitle: 'last check' },
  };

  const command = [
    { title: 'Configuration updated', date: '22 Jan 2024' },
    { title: 'Alert resolved', date: '2024-04-23' },
  ];

  const connections = [
    { name: 'POS System' },
    { name: 'Delivery App', status: 'online' },
    { name: 'Payment Gateway', status: 'online' },
  ];

  const audit = [
    { title: 'Configuration updated', date: '22 Jan 2024' },
    { title: 'Alert resolved', date: '2024-04-23' },
  ];

  const sparkData = {
    small: [6, 3, 5, 4, 7, 6, 8],
    medium: [10, 14, 9, 12, 18, 16, 20, 18, 22],
  };

  return (
    <>
      {showModal && (
        <div className="fixed inset-0 bg-black/60 backdrop-blur-sm flex items-center justify-center z-50">
          <div className="bg-[#062125] border border-[#0e3b3f] rounded-xl p-6 w-80 shadow-xl text-center">
            <h2 className="text-xl font-semibold text-teal-300 mb-3">Updating...</h2>

            {/* Progress Bar */}
            <div className="w-full bg-[#0a2b2f] rounded-full h-3 overflow-hidden mb-3">
              <div
                className="bg-teal-400 h-full transition-all duration-300"
                style={{ width: `${progress}%` }}
              />
            </div>

            <div className="text-sm text-slate-300 mb-1">Applying config...</div>
            {/* <div className="text-xs text-slate-500">Time: 5 seconds</div> */}
          </div>
        </div>
      )}

      <div className="min-h-screen bg-gradient-to-b from-[#041014] to-[#03121a] text-slate-200 p-6 sm:p-10 font-sans">
        <Button
          variant="ghost"
          onClick={() => window.history.back()}
          className="mb-4 pl-0 hover:pl-1 transition-all text-gray-400 hover:text-white hover:bg-transparent"
        >
          <ArrowLeft className="h-4 w-4 mr-2" />
          Go to Back
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
                {/* <h1 className="text-2xl sm:text-3xl font-semibold tracking-tight">DEVICE-00001</h1> */}
                <h1 className="text-2xl sm:text-3xl font-semibold tracking-tight">
                  {device?.name || device?.device_id || 'Unknown Device'}
                </h1>

                <div className="flex items-center gap-2 mt-1 text-sm text-emerald-300">
                  <span className="w-2 h-2 rounded-full bg-emerald-400 shadow-[0_0_10px_rgba(34,197,94,0.14)] inline-block" />
                  <span className="font-medium">
                    Healthy
                    {/* {device.status ? device.status.toUpperCase() : 'UNKNOWN'} */}
                  </span>
                </div>
              </div>
            </div>

            <div className="flex items-center gap-3">
              {['Reconnect', 'Run Command', 'Audit Log', 'Exit'].map((btn) => (
                <ActionButton key={btn} onClick={() => handleButtonClick(btn)}>
                  {btn}
                </ActionButton>
              ))}

              {/* <ActionButton>Reconnect</ActionButton>
            <ActionButton>Run Command</ActionButton>
            <ActionButton>Audit Log</ActionButton>
            <ActionButton>Exit</ActionButton> */}
            </div>
          </header>

          {/* Main Grid */}
          <div className="grid grid-cols-1 lg:grid-cols-12 gap-4 text-left">
            {/* Top Row */}
            <div className="lg:col-span-8 grid grid-cols-1 md:grid-cols-3 gap-4">
              {/* Health & Status */}
              <LargeCard className="md:col-span-2">
                <h3 className="text-sm text-slate-300 font-medium mb-4">HEALTH & STATUS</h3>
                <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
                  {['cpu', 'memory', 'disk'].map((key) => (
                    <div key={key} className="flex flex-col gap-1">
                      <StatBlock
                        data={sparkData.small}
                        title={stats[key].label}
                        value={stats[key].value}
                        subtitle={stats[key].subtitle}
                      />
                    </div>
                  ))}
                </div>
              </LargeCard>

              {/* Settings */}
              <Card className="text-left">
                <h3 className="text-sm text-slate-300 font-medium">SETTINGS</h3>
                <div className="border-t border-[#1f2735] mt-2"></div>
                <div className="mt-3">
                  <input
                    className="w-full bg-[#051a1d] border border-[#0e2f37] rounded px-3 py-2 text-sm outline-none placeholder:text-slate-500"
                    placeholder="Enter command"
                    value={commandInput}
                    onChange={(e) => setCommandInput(e.target.value)}
                    onKeyDown={(e) => e.key === 'Enter' && handleCommandSubmit()}
                  />
                  <div className="mt-3 text-sm text-slate-200">restart POS</div>
                  <div className="mt-1 text-xs text-slate-400">restart POS</div>
                </div>
              </Card>
            </div>

            {/* Command (Top right) */}
            <Card className="lg:col-span-4 text-left">
              <h3 className="text-sm text-slate-300 font-medium mb-3">COMMAND</h3>
              <div className="border-t border-[#1f2735] mb-2"></div>
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
                <h3 className="text-sm text-slate-300 font-medium">CONNECTIONS</h3>
                <div className="border-t border-[#1f2735] mt-2"></div>
                <ul className="mt-4 space-y-3 text-sm">
                  {connections.map((c) => (
                    <li key={c.name} className="flex items-center justify-between">
                      <span className="font-medium">{c.name}</span>
                      <div
                        className={`w-3 h-3 rounded-full ${
                          c.status === 'online'
                            ? 'bg-emerald-400 shadow-[0_0_8px_rgba(34,197,94,0.12)]'
                            : ''
                        }`}
                      />
                    </li>
                  ))}
                </ul>
                <div className="border-t border-[#1f2735] mt-4"></div>
                <div className="mt-4">
                  <div className="text-xs text-slate-400 mb-2">Network</div>
                  <div className="w-full h-12">
                    <Sparkline data={sparkData.medium} height={48} animated />
                  </div>
                </div>
              </Card>

              {/* Command Input */}
              <Card>
                <h3 className="text-sm text-slate-300 font-medium mb-3">COMMAND</h3>
                <div className="border-t border-[#1f2735] mb-2"></div>
                <div className="flex flex-col gap-3">
                  <div className="relative">
                    <input
                      className="w-full bg-[#051a1d] border border-[#0e2f37] rounded px-3 py-2 text-sm outline-none placeholder:text-slate-500 pr-10"
                      placeholder="Enter command"
                      value={cmdInput}
                      // onChange={(e) => setCmdInput(e.target.value)}
                      onChange={handleCmdInputChange}
                      onKeyDown={(e) => e.key === 'Enter' && handleSendCommand()}
                    />
                    <button
                      onClick={handleSendCommand}
                      className="absolute right-1 top-1/2 -translate-y-1/2 px-2 py-1 rounded text-teal-300 text-sm hover:bg-teal-500/30"
                    >
                      &gt;
                    </button>
                  </div>
                  <div className="text-sm text-slate-200 mt-2">restart POS</div>
                  <div className="border-t border-[#1f2735] mb-2"></div>
                  <div className="text-xs text-slate-400">Logs</div>
                  <div className="text-sm text-slate-200 mt-3">restart POS</div>
                  <div className="text-xs text-slate-400">Logs</div>
                </div>
              </Card>

              {/* Audit & Logs */}
              <Card>
                <h3 className="text-sm text-slate-300 font-medium mb-3">AUDIT & LOGS</h3>
                <div className="border-t border-[#1f2735] mb-2"></div>
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
                <div className="border-t border-[#1f2735] mt-2"></div>
                <div className="mt-3 text-sm text-slate-200">Uptime</div>
                <div className="mt-2">
                  <Sparkline data={[8, 10, 12, 10, 14, 16, 18]} height={48} animated />
                </div>
                <div className="border-t border-[#1f2735] mt-2"></div>
                <div className="mt-3 text-sm text-slate-200">Alerts</div>
                <div className="mt-2">
                  <Sparkline data={[4, 6, 5, 6, 7, 6, 8]} height={48} animated />
                </div>
              </Card>
            </div>
          </div>
        </div>
      </div>
    </>
  );
}

/* === Small Reusable Components === */
function Card({ children, className = '' }) {
  return (
    <div
      className={`border border-[#0e2f37] rounded-2xl p-4 shadow-[inset_0_1px_0_rgba(255,255,255,0.02)] ${className}`}
    >
      {children}
    </div>
  );
}

function LargeCard({ children, className = '' }) {
  return (
    <div
      className={`border border-[#103237] rounded-2xl p-4 shadow-[0_8px_30px_rgba(2,136,153,0.06)] ${className}`}
    >
      {children}
    </div>
  );
}

function ActionButton({ children, onClick }) {
  return (
    <button
      onClick={onClick}
      className="px-4 py-2 rounded-md text-sm font-medium border backdrop-blur-sm border-[#0b3b3f] text-teal-200 hover:brightness-105"
    >
      {children}
    </button>
  );
}

function StatBlock({ title, value, subtitle, data = [] }) {
  return (
    <div className="border border-[#0d2b2f] rounded-lg p-3 flex flex-col gap-2 text-left">
      <div className="w-full h-10">
        <Sparkline data={data} height={40} animated />
      </div>
      <div className="mt-2">
        <div className="text-xs text-slate-400">{title}</div>
        <div className="text-sm font-semibold tracking-tight">{value}</div>
        <div className="text-xs text-slate-400">{subtitle}</div>
      </div>
    </div>
  );
}

function Sparkline({ data = [4, 6, 5, 7, 6, 8, 9], height = 40, animated = false }) {
  const width = 144;
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
  );
}
