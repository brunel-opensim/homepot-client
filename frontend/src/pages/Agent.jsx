import React, { useEffect, useState } from 'react';
import { Card } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Loader2, CheckCircle, AlertTriangle, ArrowLeft } from 'lucide-react';
import api from '@/services/api';

export default function AgentList() {
  const [agents, setAgents] = useState([]);
  const [loading, setLoading] = useState(true);

  console.log('agents..', agents);

  //   const handleOpenAgent = (deviceId) => {
  //     navigate(`/agent/${deviceId}`);
  //   };

  useEffect(() => {
    const fetchAgents = async () => {
      try {
        const res = await api.agents.getListAgents();
        setAgents(res.agents || []);
      } catch (err) {
        console.error('Failed to fetch agents:', err);
      } finally {
        setLoading(false);
      }
    };

    fetchAgents();
  }, []);

  const getStatusColor = (state) => {
    switch (state) {
      case 'running':
        return 'bg-green-500';
      case 'idle':
        return 'bg-yellow-500';
      case 'offline':
        return 'bg-red-500';
      default:
        return 'bg-gray-500';
    }
  };

  const getHealthIcon = (lastCheck) => {
    if (!lastCheck) {
      return (
        <span className="flex items-center gap-1 text-yellow-400">
          <AlertTriangle className="w-4 h-4" />
          Unknown
        </span>
      );
    }

    return (
      <span className="flex items-center gap-1 text-green-400">
        <CheckCircle className="w-4 h-4" />
        Healthy
      </span>
    );
  };

  if (loading) {
    return (
      <div className="flex justify-center items-center h-64">
        <Loader2 className="h-8 w-8 text-primary animate-spin" />
      </div>
    );
  }

  const formatDate = (ts) => {
    if (!ts) return '—';

    // remove microseconds: .xxxxx
    const clean = ts.replace(/\.\d+/, '');

    const date = new Date(clean);
    if (isNaN(date.getTime())) return '—';

    return date.toLocaleString();
  };

  return (
    <div className="min-h-screen p-6 text-white">
      {/* Back Button */}
      <Button
        variant="ghost"
        onClick={() => window.history.back()}
        className="mb-4 pl-0 hover:pl-1 transition-all text-gray-400 hover:text-white hover:bg-transparent"
      >
        <ArrowLeft className="h-4 w-4 mr-2" />
        Back to Dashboard
      </Button>

      {/* Shrink table width */}
      <div className="max-w-4xl mx-auto">
        <h1 className="text-3xl font-bold mb-6">Agents</h1>
        <Card className="border-border bg-card">
          <div className="relative w-full overflow-auto">
            <table className="w-full text-sm">
              <thead className="border-b border-border bg-gray-900/40">
                <tr>
                  <th className="h-12 px-4 text-left text-gray-400">Device ID</th>
                  <th className="h-12 px-4 text-left text-gray-400">Status</th>
                  <th className="h-12 px-4 text-left text-gray-400">Health</th>
                  <th className="h-12 px-4 text-left text-gray-400">Last Seen</th>
                  {/* <th className="h-12 px-4 text-left text-gray-400">Config</th> */}
                </tr>
              </thead>

              <tbody>
                {agents.map((agent) => (
                  <tr key={agent.device_id} className="border-b border-border hover:bg-muted/40">
                    {/* Device ID */}
                    <td
                      className="p-4 font-medium cursor-pointer text-blue-400 hover:underline"
                      onClick={() => (window.location.href = `/device/${agent.device_id}`)}
                    >
                      {agent.device_id}
                    </td>

                    {/* Status */}
                    <td className="p-4">
                      <div className="flex items-center gap-2">
                        <span className={`w-3 h-3 rounded-full ${getStatusColor(agent.uptime)}`} />
                        {agent.uptime === 'running' ? 'Online' : 'Offline'}
                      </div>
                    </td>

                    {/* Health */}
                    <td className="p-4">{getHealthIcon(agent.last_health_check)}</td>

                    {/* Last Seen */}
                    <td className="p-4 text-gray-300">
                      {formatDate(agent.last_health_check?.last_restart)}
                    </td>

                    {/* Config */}
                    {/* <td className="p-4 text-gray-300">
                      v{agent.config_version || "N/A"}
                    </td> */}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Card>
      </div>
    </div>
  );
}
