import React, { useEffect, useState } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import {
  Activity,
  Server,
  RefreshCw,
  AlertCircle,
  CheckCircle2,
  ArrowLeft,
  Database,
  Play,
} from 'lucide-react';
import api from '@/services/api';
import { useNavigate } from 'react-router-dom';

export default function DataCollection() {
  const navigate = useNavigate();
  const [agents, setAgents] = useState([]);
  const [lastUpdated, setLastUpdated] = useState(new Date());
  const [isCollecting, setIsCollecting] = useState(false);
  const [loadingStatus, setLoadingStatus] = useState(true);

  const fetchAgents = async () => {
    try {
      const res = await api.agents.getListAgents();
      setAgents(res.agents || []);
      setLastUpdated(new Date());
    } catch (err) {
      console.error('Failed to fetch agents:', err);
    }
  };

  const fetchStatus = async () => {
    try {
      const res = await api.agents.getSimulationStatus();
      setIsCollecting(res.is_running);
    } catch (err) {
      console.error('Failed to fetch simulation status:', err);
    } finally {
      setLoadingStatus(false);
    }
  };

  const toggleCollection = async () => {
    try {
      setLoadingStatus(true);
      if (isCollecting) {
        await api.agents.stopSimulation();
      } else {
        await api.agents.startSimulation();
      }
      // Wait a bit for backend to update
      setTimeout(fetchStatus, 500);
    } catch (err) {
      console.error('Failed to toggle simulation:', err);
      setLoadingStatus(false);
    }
  };

  useEffect(() => {
    fetchStatus();
    fetchAgents();
    const interval = setInterval(() => {
      fetchAgents();
      // Optionally poll status too, but might be overkill
      fetchStatus();
    }, 2000);
    return () => clearInterval(interval);
  }, []);

  const getStatusBadge = (state) => {
    const baseClasses =
      'inline-flex items-center rounded-full border px-2.5 py-0.5 text-xs font-semibold transition-colors focus:outline-none focus:ring-2 focus:ring-ring focus:ring-offset-2 capitalize';

    const s = state?.toLowerCase();

    switch (s) {
      case 'running':
      case 'idle':
      case 'online':
        return (
          <span
            className={`${baseClasses} bg-emerald-500/10 text-emerald-500 border-emerald-500/20`}
          >
            {state || 'Online'}
          </span>
        );
      case 'updating':
      case 'downloading':
      case 'restarting':
      case 'health_check':
        return (
          <span className={`${baseClasses} bg-blue-500/10 text-blue-500 border-blue-500/20`}>
            {state}
          </span>
        );
      case 'error':
        return (
          <span className={`${baseClasses} bg-red-500/10 text-red-500 border-red-500/20`}>
            {state}
          </span>
        );
      case 'unknown':
      case 'offline':
      default:
        return (
          <span className={`${baseClasses} bg-slate-500/10 text-slate-400 border-slate-500/20`}>
            {state || 'Unknown'}
          </span>
        );
    }
  };

  return (
    <div className="min-h-screen bg-black text-white p-6 space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-4">
          <Button
            variant="ghost"
            size="icon"
            onClick={() => navigate('/dashboard')}
            className="rounded-full"
          >
            <ArrowLeft className="w-5 h-5" />
          </Button>
          <div>
            <h1 className="text-3xl font-bold tracking-tight">Data Collection</h1>
            <p className="text-muted-foreground">Real-time monitoring of agents</p>
          </div>
        </div>
        <div className="flex items-center gap-4">
          <div className="flex items-center gap-2 text-sm text-muted-foreground">
            <Activity className="w-4 h-4 animate-pulse text-green-500" />
            Last updated: {lastUpdated.toLocaleTimeString()}
          </div>
          <Button
            onClick={toggleCollection}
            disabled={loadingStatus}
            variant={isCollecting ? 'secondary' : 'default'}
            className="min-w-[160px]"
          >
            {loadingStatus ? (
              <>
                <RefreshCw className="w-4 h-4 mr-2 animate-spin" />
                Updating...
              </>
            ) : isCollecting ? (
              <>
                <RefreshCw className="w-4 h-4 mr-2 animate-spin" />
                Stop Collection
              </>
            ) : (
              <>
                <Play className="w-4 h-4 mr-2" />
                Start Collection
              </>
            )}
          </Button>
        </div>
      </div>

      {/* Stats Overview */}
      <div className="grid gap-4 md:grid-cols-3">
        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Active Agents</CardTitle>
            <Server className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{agents.length}</div>
            <p className="text-xs text-muted-foreground">Simulated POS devices</p>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Total Transactions</CardTitle>
            <Database className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">
              {agents
                .reduce(
                  (acc, agent) => acc + (agent.last_health_check?.metrics?.transactions_today || 0),
                  0
                )
                .toLocaleString()}
            </div>
            <p className="text-xs text-muted-foreground">Processed today</p>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">System Health</CardTitle>
            <Activity className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold text-green-500">98.2%</div>
            <p className="text-xs text-muted-foreground">Average uptime</p>
          </CardContent>
        </Card>
      </div>

      {/* Agents Grid */}
      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
        {agents.map((agent) => (
          <Card key={agent.device_id} className="overflow-hidden transition-all hover:shadow-md">
            <CardHeader className="flex flex-row items-start justify-between space-y-0 pb-2 bg-muted/50">
              <div className="space-y-1">
                <CardTitle className="text-base font-medium flex items-center gap-2">
                  <Server className="w-4 h-4 text-muted-foreground" />
                  {agent.device_id}
                </CardTitle>
                <p className="text-xs text-muted-foreground font-mono">v{agent.config_version}</p>
              </div>
              {getStatusBadge(agent.state)}
            </CardHeader>
            <CardContent className="pt-4 space-y-3">
              <div className="grid grid-cols-2 gap-2 text-sm">
                <div className="space-y-1">
                  <p className="text-xs text-muted-foreground">CPU Usage</p>
                  <div className="font-medium">
                    {agent.last_health_check?.metrics?.cpu_usage_percent?.toFixed(1) || 0}%
                  </div>
                </div>
                <div className="space-y-1">
                  <p className="text-xs text-muted-foreground">Memory</p>
                  <div className="font-medium">
                    {agent.last_health_check?.metrics?.memory_usage_percent?.toFixed(1) || 0}%
                  </div>
                </div>
                <div className="space-y-1">
                  <p className="text-xs text-muted-foreground">Latency</p>
                  <div className="font-medium">
                    {agent.last_health_check?.metrics?.network_latency_ms?.toFixed(2) || 0}ms
                  </div>
                </div>
                <div className="space-y-1">
                  <p className="text-xs text-muted-foreground">Errors</p>
                  <div
                    className={`font-medium ${agent.last_health_check?.metrics?.error_rate > 0 ? 'text-red-500' : ''}`}
                  >
                    {agent.last_health_check?.metrics?.error_rate?.toFixed(2) || 0}%
                  </div>
                </div>
              </div>

              <div className="pt-2 border-t text-xs text-muted-foreground flex items-center justify-between">
                <span>Last check:</span>
                <span className="font-mono">
                  {agent.last_health_check?.timestamp
                    ? new Date(agent.last_health_check.timestamp).toLocaleTimeString()
                    : '-'}
                </span>
              </div>
            </CardContent>
          </Card>
        ))}
      </div>
    </div>
  );
}
