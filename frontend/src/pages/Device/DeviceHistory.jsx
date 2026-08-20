import React, { useState, useEffect, useCallback } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import {
  ArrowLeft,
  Loader2,
  Clock,
  FileJson,
  CheckCircle2,
  XCircle,
  RefreshCw,
  Eye,
  AlertCircle,
} from 'lucide-react';
import api from '@/services/api';
import { Button } from '@/components/ui/button';
import { Card } from '@/components/ui/card';
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
} from '@/components/ui/dialog';
import { Toast } from '@/components/ui/Toast';
import {
  lifecycleStages,
  formatCommandType,
  resultMessage,
  getStatusMeta,
} from '@/utils/commandLifecycle';

function StatusBadge({ status }) {
  const meta = getStatusMeta(status);
  return (
    <span
      className={`inline-flex items-center gap-1 text-[10px] px-2 py-0.5 rounded-full border font-medium whitespace-nowrap ${meta.color} ${meta.bg} ${meta.border}`}
    >
      {meta.label.toUpperCase()}
    </span>
  );
}

function StageStamp({ label, time }) {
  return (
    <div className="flex items-center gap-1.5">
      <span className="text-slate-500 text-[10px]">{label}</span>
      <span className="font-mono text-[10px] text-slate-300">
        {time ? new Date(time).toLocaleTimeString() : '—'}
      </span>
    </div>
  );
}

export default function DeviceHistory() {
  const { id } = useParams();
  const navigate = useNavigate();
  const [history, setHistory] = useState([]);
  const [loading, setLoading] = useState(true);
  const [device, setDevice] = useState(null);
  const [selectedCommand, setSelectedCommand] = useState(null);
  const [isDetailsModalOpen, setIsDetailsModalOpen] = useState(false);
  const [toast, setToast] = useState(null);

  const fetchData = useCallback(async () => {
    try {
      const [deviceData, commandData] = await Promise.all([
        api.devices.getDeviceById(id),
        api.devices.getCommands(id, 50),
      ]);
      setDevice(deviceData);
      setHistory(commandData || []);
    } catch (err) {
      console.error('Failed to load command history:', err);
      setToast({ title: 'Error', message: 'Failed to load command history', type: 'error' });
    } finally {
      setLoading(false);
    }
  }, [id]);

  useEffect(() => {
    fetchData();
    const interval = setInterval(fetchData, 5000);
    return () => clearInterval(interval);
  }, [fetchData]);

  const openDetails = (cmd) => {
    setSelectedCommand(cmd);
    setIsDetailsModalOpen(true);
  };

  const handleReuse = (cmd) => {
    const data = cmd.payload?.data;
    if (!data || typeof data !== 'object') return;
    const reuseData = { ...data };
    delete reuseData.timestamp;
    delete reuseData.command;
    navigate(`/device/${id}/push-review`, {
      state: {
        initialCommand: cmd.command_type,
        initialData: reuseData,
      },
    });
  };

  if (loading) {
    return (
      <div className="flex justify-center items-center h-full">
        <Loader2 className="h-8 w-8 animate-spin text-primary" />
      </div>
    );
  }

  return (
    <div className="h-full bg-gradient-to-b from-[#041014] to-[#03121a] text-slate-200 p-2 font-sans flex flex-col overflow-hidden">
      <div className="max-w-4xl mx-auto w-full h-full flex flex-col">
        {toast && <Toast {...toast} onClose={() => setToast(null)} />}

        <div className="shrink-0 mb-4">
          <Button
            variant="ghost"
            onClick={() => navigate(`/device/${id}`)}
            className="mb-4 pl-0 hover:pl-1 transition-all text-gray-400 hover:text-white hover:bg-transparent"
          >
            <ArrowLeft className="h-4 w-4 mr-2" />
            Back to Device
          </Button>

          <div className="flex justify-between items-end">
            <div>
              <h1 className="text-xl font-bold tracking-tight text-white">Push History</h1>
              <p className="text-sm text-gray-400">
                Command lifecycle for <span className="text-teal-400">{device?.name}</span>
                <span className="ml-2 text-[10px] text-slate-500 font-mono">
                  auto-refreshing every 5s
                </span>
              </p>
            </div>
            <Button
              onClick={() => navigate(`/device/${id}/push-review`)}
              className="bg-teal-600 hover:bg-teal-500 text-white h-9"
            >
              Compose New
            </Button>
          </div>
        </div>

        <div className="flex-1 overflow-y-auto pr-1 space-y-2">
          {history.length === 0 ? (
            <Card className="p-8 text-center bg-[#06181c] border-[#0e2f37] text-gray-400">
              <Clock className="h-12 w-12 mx-auto mb-4 opacity-20" />
              <p>No commands have been sent to this device yet.</p>
            </Card>
          ) : (
            history.map((cmd) => {
              const { meta } = lifecycleStages(cmd);
              const done =
                cmd.status === 'completed' || cmd.status === 'failed' || cmd.status === 'expired';
              const message = resultMessage(cmd.result);
              return (
                <Card
                  key={cmd.command_id}
                  className="p-3 bg-[#06181c] border-[#0e2f37] hover:border-teal-500/50 transition-colors group"
                >
                  <div className="flex items-start justify-between gap-4">
                    <div className="flex items-start gap-3 flex-1 min-w-0">
                      <div className="mt-1 shrink-0">
                        {done ? (
                          cmd.status === 'completed' ? (
                            <CheckCircle2 className="h-4 w-4 text-green-500" />
                          ) : (
                            <XCircle className="h-4 w-4 text-red-500" />
                          )
                        ) : cmd.status === 'sent' ? (
                          <Loader2 className="h-4 w-4 text-blue-400 animate-spin" />
                        ) : (
                          <Clock className="h-4 w-4 text-amber-400" />
                        )}
                      </div>
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center gap-2 min-w-0 flex-wrap">
                          <h3 className="text-sm font-medium text-white truncate min-w-0">
                            {formatCommandType(cmd.command_type)}
                          </h3>
                          <StatusBadge status={cmd.status} />
                          <span className="font-mono text-[10px] text-slate-500">
                            {cmd.command_id.substring(0, 8)}
                          </span>
                        </div>

                        <div className="flex items-center gap-3 mt-1.5 flex-wrap">
                          <StageStamp label="Queued" time={cmd.created_at} />
                          <StageStamp label="Acknowledged" time={cmd.sent_at} />
                          <StageStamp label="Executed" time={cmd.executed_at} />
                        </div>

                        {message && (
                          <div className="mt-1.5 text-[11px] font-mono text-slate-400 truncate max-w-lg">
                            {message}
                          </div>
                        )}
                        {!done && (
                          <div className="mt-1 text-[10px] text-amber-400/90">
                            {meta.description}
                          </div>
                        )}
                      </div>
                    </div>

                    <div className="flex items-center gap-1 shrink-0 opacity-0 group-hover:opacity-100 transition-opacity">
                      {cmd.payload && (
                        <Button
                          variant="outline"
                          size="sm"
                          onClick={() => handleReuse(cmd)}
                          className="h-7 px-2 border-gray-700 bg-transparent text-gray-300 hover:text-white hover:bg-gray-800 text-xs"
                          title="Reuse Command"
                        >
                          <RefreshCw className="h-3 w-3 mr-1" />
                          Reuse
                        </Button>
                      )}
                      <Button
                        variant="outline"
                        size="sm"
                        onClick={() => openDetails(cmd)}
                        className="h-7 px-2 border-gray-700 bg-transparent text-gray-300 hover:text-white hover:bg-gray-800 text-xs"
                        title="View Details"
                      >
                        <Eye className="h-3 w-3 mr-1" />
                        Details
                      </Button>
                    </div>
                  </div>
                </Card>
              );
            })
          )}
        </div>

        {/* Details Modal */}
        <Dialog open={isDetailsModalOpen} onOpenChange={setIsDetailsModalOpen}>
          <DialogContent className="max-w-2xl bg-card border-gray-800 text-white">
            <DialogHeader>
              <DialogTitle>Command Details</DialogTitle>
              <DialogDescription>
                Full payload, lifecycle timestamps, and execution result.
              </DialogDescription>
            </DialogHeader>

            {selectedCommand && (
              <div className="mt-4 space-y-4">
                <div className="grid grid-cols-2 gap-4 text-sm">
                  <div>
                    <span className="text-gray-500 block">Status</span>
                    <StatusBadge status={selectedCommand.status} />
                  </div>
                  <div>
                    <span className="text-gray-500 block">Command Type</span>
                    <span className="text-gray-300">
                      {formatCommandType(selectedCommand.command_type)}
                    </span>
                  </div>
                  <div>
                    <span className="text-gray-500 block">Queued</span>
                    <span className="text-gray-300">
                      {new Date(selectedCommand.created_at).toLocaleString()}
                    </span>
                  </div>
                  <div>
                    <span className="text-gray-500 block">Acknowledged</span>
                    <span className="text-gray-300">
                      {selectedCommand.sent_at
                        ? new Date(selectedCommand.sent_at).toLocaleString()
                        : '—'}
                    </span>
                  </div>
                  <div>
                    <span className="text-gray-500 block">Executed</span>
                    <span className="text-gray-300">
                      {selectedCommand.executed_at
                        ? new Date(selectedCommand.executed_at).toLocaleString()
                        : '—'}
                    </span>
                  </div>
                  <div>
                    <span className="text-gray-500 block">Command ID</span>
                    <span className="text-gray-300 font-mono text-xs">
                      {selectedCommand.command_id}
                    </span>
                  </div>
                </div>

                {selectedCommand.payload && (
                  <div>
                    <span className="text-gray-500 block mb-2 text-sm">Payload</span>
                    <div className="bg-black/50 rounded-md p-4 overflow-auto max-h-[200px]">
                      <pre className="text-xs font-mono text-green-400">
                        {JSON.stringify(selectedCommand.payload, null, 2)}
                      </pre>
                    </div>
                  </div>
                )}

                {selectedCommand.result && (
                  <div>
                    <span className="text-gray-500 block mb-2 text-sm">Result</span>
                    <div className="bg-black/50 rounded-md p-4 overflow-auto max-h-[200px]">
                      <pre className="text-xs font-mono text-blue-300">
                        {JSON.stringify(selectedCommand.result, null, 2)}
                      </pre>
                    </div>
                  </div>
                )}

                {!selectedCommand.result &&
                  !['completed', 'failed', 'expired'].includes(selectedCommand.status) && (
                    <div className="flex items-center gap-2 text-xs text-amber-400">
                      <AlertCircle className="h-4 w-4 shrink-0" />
                      {getStatusMeta(selectedCommand.status).description}
                    </div>
                  )}
              </div>
            )}
          </DialogContent>
        </Dialog>
      </div>
    </div>
  );
}
