import React, { useEffect, useState, useMemo } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import {
  Loader2,
  CheckCircle,
  AlertTriangle,
  ArrowLeft,
  RefreshCw,
  Server,
  Activity,
  ArrowUpDown,
} from 'lucide-react';
import api from '@/services/api';
import { useNavigate } from 'react-router-dom';

export default function AgentList() {
  const navigate = useNavigate();
  const [agents, setAgents] = useState([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [sortConfig, setSortConfig] = useState({ key: 'status', direction: 'desc' });

  const fetchAgents = async () => {
    try {
      setRefreshing(true);
      const res = await api.agents.getListAgents();
      setAgents(res.agents || []);
    } catch (err) {
      console.error('Failed to fetch agents:', err);
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  };

  useEffect(() => {
    fetchAgents();
  }, []);

  const handleSort = (key) => {
    let direction = 'asc';
    if (sortConfig.key === key && sortConfig.direction === 'asc') {
      direction = 'desc';
    }
    setSortConfig({ key, direction });
  };

  const sortedAgents = useMemo(() => {
    let sortableItems = [...agents];
    if (sortConfig.key !== null) {
      sortableItems.sort((a, b) => {
        let aValue, bValue;

        switch (sortConfig.key) {
          case 'status':
            // 1 for Online, 0 for Offline
            aValue = a.uptime === 'running' || a.uptime === 'online' ? 1 : 0;
            bValue = b.uptime === 'running' || b.uptime === 'online' ? 1 : 0;
            break;
          case 'health':
            // 1 for Healthy (has check), 0 for Unknown
            aValue = a.last_health_check ? 1 : 0;
            bValue = b.last_health_check ? 1 : 0;
            break;
          case 'last_seen':
            aValue = a.last_health_check?.last_restart || '';
            bValue = b.last_health_check?.last_restart || '';
            break;
          case 'device_id':
            aValue = a.device_id;
            bValue = b.device_id;
            break;
          default:
            return 0;
        }

        if (aValue < bValue) {
          return sortConfig.direction === 'asc' ? -1 : 1;
        }
        if (aValue > bValue) {
          return sortConfig.direction === 'asc' ? 1 : -1;
        }
        return 0;
      });
    }
    return sortableItems;
  }, [agents, sortConfig]);

  const getStatusBadge = (state) => {
    const isOnline = state === 'running' || state === 'online';
    return (
      <span
        className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ${
          isOnline
            ? 'bg-green-900/30 text-green-400 border border-green-800'
            : 'bg-red-900/30 text-red-400 border border-red-800'
        }`}
      >
        <span
          className={`w-1.5 h-1.5 rounded-full mr-1.5 ${isOnline ? 'bg-green-400' : 'bg-red-400'}`}
        />
        {isOnline ? 'Online' : 'Offline'}
      </span>
    );
  };

  const getHealthIcon = (lastCheck) => {
    if (!lastCheck) {
      return (
        <span className="flex items-center gap-1.5 text-yellow-500 text-sm">
          <AlertTriangle className="w-4 h-4" />
          Unknown
        </span>
      );
    }

    return (
      <span className="flex items-center gap-1.5 text-emerald-400 text-sm">
        <CheckCircle className="w-4 h-4" />
        Healthy
      </span>
    );
  };

  const formatDate = (ts) => {
    if (!ts) return '—';
    const clean = ts.replace(/\.\d+/, '');
    const date = new Date(clean);
    if (isNaN(date.getTime())) return '—';
    return date.toLocaleString(undefined, {
      month: 'short',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
    });
  };

  // Calculate stats
  const totalAgents = agents.length;
  const onlineAgents = agents.filter((a) => a.uptime === 'running' || a.uptime === 'online').length;
  const offlineAgents = totalAgents - onlineAgents;

  if (loading) {
    return (
      <div className="min-h-screen bg-slate-950 flex justify-center items-center">
        <Loader2 className="h-8 w-8 text-teal-400 animate-spin" />
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-slate-950 p-6 text-slate-200">
      <div className="max-w-6xl mx-auto space-y-6">
        {/* Header Section */}
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
          <div>
            <Button
              variant="ghost"
              onClick={() => navigate('/dashboard')}
              className="pl-0 hover:pl-1 transition-all text-slate-400 hover:text-white hover:bg-transparent mb-2"
            >
              <ArrowLeft className="h-4 w-4 mr-2" />
              Back to Dashboard
            </Button>
            <h1 className="text-3xl font-bold text-white tracking-tight">Device Agents</h1>
            <p className="text-slate-400 mt-1">
              Monitor real-time status and health of connected agents.
            </p>
          </div>
          <Button
            onClick={fetchAgents}
            disabled={refreshing}
            className="bg-slate-800 hover:bg-slate-700 text-white border border-slate-700"
          >
            <RefreshCw className={`h-4 w-4 mr-2 ${refreshing ? 'animate-spin' : ''}`} />
            Refresh List
          </Button>
        </div>

        {/* Stats Cards */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          <Card className="bg-slate-900/50 border-slate-800">
            <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
              <CardTitle className="text-sm font-medium text-slate-400">Total Agents</CardTitle>
              <Server className="h-4 w-4 text-slate-400" />
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold text-white">{totalAgents}</div>
            </CardContent>
          </Card>
          <Card className="bg-slate-900/50 border-slate-800">
            <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
              <CardTitle className="text-sm font-medium text-emerald-400">Online</CardTitle>
              <Activity className="h-4 w-4 text-emerald-400" />
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold text-white">{onlineAgents}</div>
            </CardContent>
          </Card>
          <Card className="bg-slate-900/50 border-slate-800">
            <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
              <CardTitle className="text-sm font-medium text-red-400">Offline</CardTitle>
              <AlertTriangle className="h-4 w-4 text-red-400" />
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold text-white">{offlineAgents}</div>
            </CardContent>
          </Card>
        </div>

        {/* Agents Table */}
        <Card className="border-slate-800 bg-slate-900/50 backdrop-blur-sm overflow-hidden">
          <div className="relative w-full overflow-auto">
            <table className="w-full text-sm text-left">
              <thead className="text-xs uppercase bg-slate-900/80 text-slate-400 border-b border-slate-800">
                <tr>
                  <th
                    className="px-6 py-4 font-medium cursor-pointer hover:text-white transition-colors group"
                    onClick={() => handleSort('device_id')}
                  >
                    <div className="flex items-center gap-2">
                      Device ID
                      <ArrowUpDown
                        className={`h-3 w-3 ${sortConfig.key === 'device_id' ? 'text-teal-400' : 'text-slate-600 group-hover:text-slate-400'}`}
                      />
                    </div>
                  </th>
                  <th
                    className="px-6 py-4 font-medium cursor-pointer hover:text-white transition-colors group"
                    onClick={() => handleSort('status')}
                  >
                    <div className="flex items-center gap-2">
                      Status
                      <ArrowUpDown
                        className={`h-3 w-3 ${sortConfig.key === 'status' ? 'text-teal-400' : 'text-slate-600 group-hover:text-slate-400'}`}
                      />
                    </div>
                  </th>
                  <th
                    className="px-6 py-4 font-medium cursor-pointer hover:text-white transition-colors group"
                    onClick={() => handleSort('health')}
                  >
                    <div className="flex items-center gap-2">
                      Health Check
                      <ArrowUpDown
                        className={`h-3 w-3 ${sortConfig.key === 'health' ? 'text-teal-400' : 'text-slate-600 group-hover:text-slate-400'}`}
                      />
                    </div>
                  </th>
                  <th
                    className="px-6 py-4 font-medium cursor-pointer hover:text-white transition-colors group"
                    onClick={() => handleSort('last_seen')}
                  >
                    <div className="flex items-center gap-2">
                      Last Seen
                      <ArrowUpDown
                        className={`h-3 w-3 ${sortConfig.key === 'last_seen' ? 'text-teal-400' : 'text-slate-600 group-hover:text-slate-400'}`}
                      />
                    </div>
                  </th>
                  <th className="px-6 py-4 font-medium text-right">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-800">
                {sortedAgents.length === 0 ? (
                  <tr>
                    <td colSpan={5} className="px-6 py-12 text-center text-slate-500">
                      No agents found. Register a device to get started.
                    </td>
                  </tr>
                ) : (
                  sortedAgents.map((agent) => (
                    <tr key={agent.device_id} className="hover:bg-slate-800/50 transition-colors">
                      <td className="px-6 py-4 font-medium text-white">{agent.device_id}</td>
                      <td className="px-6 py-4">{getStatusBadge(agent.uptime)}</td>
                      <td className="px-6 py-4">{getHealthIcon(agent.last_health_check)}</td>
                      <td className="px-6 py-4 text-slate-400 font-mono text-xs">
                        {formatDate(agent.last_health_check?.last_restart)}
                      </td>
                      <td className="px-6 py-4 text-right">
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={() => navigate(`/device/${agent.device_id}`)}
                          className="text-teal-400 hover:text-teal-300 hover:bg-teal-400/10 h-8"
                        >
                          View Details
                        </Button>
                      </td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
        </Card>
      </div>
    </div>
  );
}
