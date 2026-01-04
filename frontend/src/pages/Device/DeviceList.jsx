import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { Search, Monitor, ArrowLeft, Activity, Server } from 'lucide-react';
import { Button } from '@/components/ui/button';
import api from '@/services/api';
import { trackActivity, trackSearch } from '@/utils/analytics';

export default function DeviceList() {
  const navigate = useNavigate();
  const [devices, setDevices] = useState([]);
  const [loading, setLoading] = useState(true);
  const [searchTerm, setSearchTerm] = useState('');
  const [statusFilter, setStatusFilter] = useState('');

  useEffect(() => {
    fetchDevices();
    trackActivity('page_view', '/device');
  }, []);

  const fetchDevices = async () => {
    try {
      setLoading(true);
      const data = await api.devices.list();
      // Handle different response structures
      const fetchedDevices = Array.isArray(data) ? data : data.devices || [];

      // Sort alphabetically by name
      fetchedDevices.sort((a, b) => (a.name || '').localeCompare(b.name || ''));

      setDevices(fetchedDevices);
    } catch (err) {
      console.error('Failed to fetch devices:', err);
    } finally {
      setLoading(false);
    }
  };

  const filteredDevices = devices.filter((device) => {
    const matchSearch =
      (device.name?.toLowerCase() || '').includes(searchTerm.toLowerCase()) ||
      (device.device_id?.toLowerCase() || '').includes(searchTerm.toLowerCase());

    const matchStatus = statusFilter
      ? device.status?.toLowerCase() === statusFilter.toLowerCase()
      : true;

    return matchSearch && matchStatus;
  });

  if (loading) {
    return (
      <div className="min-h-screen bg-[#0b0e13] text-white flex items-center justify-center">
        <p className="text-teal-400 animate-pulse">Loading devices...</p>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-[#0b0e13] text-white p-6">
      <Button
        variant="ghost"
        onClick={() => navigate('/dashboard')}
        className="mb-4 pl-0 hover:pl-1 transition-all text-gray-400 hover:text-white hover:bg-transparent"
      >
        <ArrowLeft className="h-4 w-4 mr-2" />
        Back to Dashboard
      </Button>

      <div className="flex flex-col md:flex-row justify-between items-center mb-6 gap-3">
        <h1 className="text-2xl font-semibold">Manage Devices</h1>
      </div>

      <div className="flex flex-col md:flex-row items-center gap-3 mb-6">
        {/* Search input */}
        <div className="relative w-full md:w-1/2">
          <span className="absolute inset-y-0 left-0 flex items-center pl-3 pointer-events-none">
            <Search className="h-5 w-5 text-gray-400" />
          </span>
          <input
            type="text"
            placeholder="Search by device ID or name"
            className="bg-[#141a24] border border-[#1f2735] text-white px-10 py-2 rounded-lg w-full focus:outline-none focus:border-teal-500 transition-colors"
            value={searchTerm}
            onChange={(e) => {
              setSearchTerm(e.target.value);
              trackSearch(e.target.value, '/device', 0);
            }}
          />
        </div>

        {/* Status Filter */}
        <select
          className="bg-[#141a24] border border-[#1f2735] text-white w-full md:w-80 px-4 py-[10px] rounded-lg focus:outline-none focus:border-teal-500 transition-colors"
          value={statusFilter}
          onChange={(e) => setStatusFilter(e.target.value)}
        >
          <option value="">All Statuses</option>
          <option value="online">Online</option>
          <option value="offline">Offline</option>
          <option value="error">Error</option>
        </select>
      </div>

      <div className="grid sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4">
        {filteredDevices.map((device) => (
          <div
            key={device.id || device.device_id}
            className="bg-[#141a24] border border-[#1f2735] rounded-xl p-5 hover:border-teal-400 transition-all flex flex-col group relative cursor-pointer"
            onClick={() => navigate(`/device/${device.device_id}`)}
          >
            <div className="flex justify-between items-start mb-4">
              <div className="p-2 rounded-lg bg-[#1f2735] text-teal-400">
                <Monitor size={24} />
              </div>
              <div
                className={`px-2 py-1 rounded text-xs font-medium ${
                  (device.status || '').toLowerCase() === 'online'
                    ? 'bg-green-500/10 text-green-400'
                    : (device.status || '').toLowerCase() === 'offline'
                      ? 'bg-gray-500/10 text-gray-400'
                      : 'bg-red-500/10 text-red-400'
                }`}
              >
                {device.status?.toUpperCase() || 'UNKNOWN'}
              </div>
            </div>

            <div className="mb-4">
              <h2 className="text-lg font-semibold text-white truncate">
                {device.name || device.device_id}
              </h2>
              <p className="text-sm text-gray-400 truncate">ID: {device.device_id}</p>
            </div>

            <div className="mt-auto space-y-2">
              <div className="flex items-center justify-between text-sm text-gray-400">
                <span className="flex items-center gap-2">
                  <Server size={14} />
                  Site
                </span>
                <span className="text-gray-300">{device.site_id || 'Unassigned'}</span>
              </div>
              <div className="flex items-center justify-between text-sm text-gray-400">
                <span className="flex items-center gap-2">
                  <Activity size={14} />
                  Type
                </span>
                <span className="text-gray-300">{device.device_type || 'Generic'}</span>
              </div>
            </div>
          </div>
        ))}

        {filteredDevices.length === 0 && (
          <div className="col-span-full text-center py-12 text-gray-500">
            No devices found matching your criteria.
          </div>
        )}
      </div>
    </div>
  );
}
