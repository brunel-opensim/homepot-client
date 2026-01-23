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
    <div className="h-full max-h-screen bg-black text-white p-2 font-sans flex flex-col overflow-hidden">
      {/* Header */}
      <div className="shrink-0 flex items-center justify-between mb-4">
        <div className="flex items-center gap-4">
          <Button
            variant="ghost"
            size="icon"
            onClick={() => navigate('/dashboard')}
            className="rounded-full hover:bg-white/10"
          >
            <ArrowLeft className="w-5 h-5" />
          </Button>
          <div>
            <h1 className="text-xl font-bold tracking-tight">Data Collection</h1>
            <p className="text-xs text-muted-foreground">Real-time monitoring of agents</p>
          </div>
        </div>
        <div className="flex items-center gap-4">
          <div className="flex items-center gap-2 text-xs text-muted-foreground">
            <Activity className="w-3 h-3 animate-pulse text-green-500" />
            Last updated: {lastUpdated.toLocaleTimeString()}
          </div>
          <Button
            onClick={toggleCollection}
            disabled={loadingStatus}
            variant={isCollecting ? 'secondary' : 'default'}
            className="min-w-[140px] h-9"
          >
            {loadingStatus ? (
              <>
                <RefreshCw className="w-3 h-3 mr-2 animate-spin" />
                Updating...
              </>
            ) : isCollecting ? (
              <>
                <RefreshCw className="w-3 h-3 mr-2 animate-spin" />
                Stop Collection
              </>
            ) : (
              <>
                <Play className="w-3 h-3 mr-2" />
                Start Collection
              </>
            )}
          </Button>
        </div>
      </div>

      <div className="flex-1 min-h-0 flex flex-col gap-4 overflow-hidden">
        {/* Stats Overview */}
        <div className="grid gap-4 md:grid-cols-3 shrink-0">
          <Card className="bg-card/50 border-gray-800">
            <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2 p-4">
              <CardTitle className="text-sm font-medium text-gray-300">Active Agents</CardTitle>
              <Server className="h-4 w-4 text-muted-foreground" />
            </CardHeader>
            <CardContent className="p-4 pt-0">
              <div className="text-2xl font-bold text-white">{agents.length}</div>
              <p className="text-xs text-muted-foreground">Simulated POS devices</p>
            </CardContent>
          </Card>
          <Card className="bg-card/50 border-gray-800">
            <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2 p-4">
              <CardTitle className="text-sm font-medium text-gray-300">
                Total Transactions
              </CardTitle>
              <Database className="h-4 w-4 text-muted-foreground" />
            </CardHeader>
            <CardContent className="p-4 pt-0">
              <div className="text-2xl font-bold text-white">
                {agents
                  .reduce(
                    (acc, agent) =>
                      acc + (agent.last_health_check?.metrics?.transactions_today || 0),
                    0
                  )
                  .toLocaleString()}
              </div>
              <p className="text-xs text-muted-foreground">Processed today</p>
            </CardContent>
          </Card>
          <Card className="bg-card/50 border-gray-800">
            <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2 p-4">
              <CardTitle className="text-sm font-medium text-gray-300">System Health</CardTitle>
              <Activity className="h-4 w-4 text-muted-foreground" />
            </CardHeader>
            <CardContent className="p-4 pt-0">
              <div className="text-2xl font-bold text-green-500">98.2%</div>
              <p className="text-xs text-muted-foreground">Average uptime</p>
            </CardContent>
          </Card>
        </div>

        {/* Agents Grid */}
        <div className="flex-1 overflow-y-auto min-h-0 pr-1">
          <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 pb-2">
            {agents.map((agent) => (
              <Card
                key={agent.device_id}
                onClick={() => navigate(`/device/${agent.device_id}`)}
                className="overflow-hidden transition-all hover:bg-accent/5 bg-card/30 border-gray-800 cursor-pointer hover:border-teal-500/50"
              >
                <CardHeader className="flex flex-row items-start justify-between space-y-0 pb-2 p-3 bg-muted/20">
                  <div className="space-y-1">
                    <CardTitle className="text-sm font-medium flex items-center gap-2 text-white/90">
                      <Server className="w-3 h-3 text-muted-foreground" />
                      {agent.device_id}
                    </CardTitle>
                    <p className="text-[10px] text-muted-foreground font-mono">
                      v{agent.config_version}
                    </p>
                  </div>
                  {getStatusBadge(agent.state)}
                </CardHeader>
                <CardContent className="p-3 pt-3 space-y-3">
                  <div className="grid grid-cols-2 gap-2 text-xs">
                    <div className="space-y-0.5">
                      <p className="text-[10px] text-muted-foreground">CPU Usage</p>
                      <div className="font-medium text-gray-300">
                        {agent.last_health_check?.metrics?.cpu_usage_percent?.toFixed(1) || 0}%
                      </div>
                    </div>
                    <div className="space-y-0.5">
                      <p className="text-[10px] text-muted-foreground">Memory</p>
                      <div className="font-medium text-gray-300">
                        {agent.last_health_check?.metrics?.memory_usage_percent?.toFixed(1) || 0}%
                      </div>
                    </div>
                    <div className="space-y-0.5">
                      <p className="text-[10px] text-muted-foreground">Latency</p>
                      <div className="font-medium text-gray-300">
                        {agent.last_health_check?.metrics?.network_latency_ms?.toFixed(2) || 0}ms
                      </div>
                    </div>
                    <div className="space-y-0.5">
                      <p className="text-[10px] text-muted-foreground">Errors</p>
                      <div
                        className={`font-medium ${agent.last_health_check?.metrics?.error_rate > 0 ? 'text-red-400' : 'text-gray-300'}`}
                      >
                        {agent.last_health_check?.metrics?.error_rate?.toFixed(2) || 0}%
                      </div>
                    </div>
                  </div>

                  <div className="pt-2 border-t border-gray-800/50 text-[10px] text-muted-foreground flex items-center justify-between">
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
      </div>
    </div>
  );
}
