import React, { useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import {
  ArrowLeft,
  Loader2,
  Clock,
  FileJson,
  CheckCircle,
  XCircle,
  Trash2,
  Eye,
  RefreshCw,
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
  DialogFooter,
} from '@/components/ui/dialog';
import { Toast } from '@/components/ui/Toast';

export default function DeviceHistory() {
  const { id } = useParams();
  const navigate = useNavigate();
  const [history, setHistory] = useState([]);
  const [loading, setLoading] = useState(true);
  const [device, setDevice] = useState(null);
  const [selectedTransaction, setSelectedTransaction] = useState(null);
  const [isDetailsModalOpen, setIsDetailsModalOpen] = useState(false);
  const [isDeleteModalOpen, setIsDeleteModalOpen] = useState(false);
  const [itemToDelete, setItemToDelete] = useState(null);
  const [toast, setToast] = useState(null);

  useEffect(() => {
    const fetchData = async () => {
      try {
        const [deviceData, historyData] = await Promise.all([
          api.devices.getDeviceById(id),
          api.devices.getHistory(id),
        ]);
        setDevice(deviceData);
        setHistory(historyData || []);
      } catch (err) {
        console.error('Failed to load history:', err);
        setToast({
          title: 'Error',
          message: 'Failed to load history data',
          type: 'error',
        });
      } finally {
        setLoading(false);
      }
    };
    fetchData();
  }, [id]);

  const confirmDelete = (item) => {
    setItemToDelete(item);
    setIsDeleteModalOpen(true);
  };

  const handleDelete = async () => {
    if (!itemToDelete) return;

    try {
      await api.devices.deleteHistoryItem(itemToDelete.id);
      setHistory(history.filter((h) => h.id !== itemToDelete.id));
      setToast({
        title: 'Success',
        message: 'History record deleted',
        type: 'success',
      });
      setIsDeleteModalOpen(false);
      setItemToDelete(null);
    } catch (err) {
      console.error('Failed to delete history item', err);
      setToast({
        title: 'Error',
        message: 'Failed to delete history record',
        type: 'error',
      });
    }
  };

  const openDetails = (item) => {
    setSelectedTransaction(item);
    setIsDetailsModalOpen(true);
  };

  const handleReuse = (item) => {
    // 1. Determine the Command Type (Action)
    // If the history item has a specific 'action' in its details (saved from full payload),
    // prefer that over the generic 'action_type' column (which is often just 'automated').
    let commandType = item.action_type || 'CUSTOM';
    if (item.details && item.details.action) {
      commandType = item.details.action;
    } else if (commandType === 'automated' || commandType === 'configuration_update') {
      // Fallback if specific action is missing but we have generic types
      commandType = 'CUSTOM';
    }

    // 2. Extract and Clean Data
    let reuseData = item.details;
    if (reuseData && typeof reuseData === 'object' && reuseData.data) {
      reuseData = { ...reuseData.data }; // Clone to avoid mutating original
    } else if (reuseData && typeof reuseData === 'object') {
      reuseData = { ...reuseData };
    }

    // Remove system-generated metadata fields so they don't clutter the editor
    if (reuseData) {
      delete reuseData.timestamp;
      delete reuseData.command;
      delete reuseData.message_id;
    }

    // Navigate to PushReview with initial data
    navigate(`/device/${id}/push-review`, {
      state: {
        initialCommand: commandType,
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
                History of push commands for <span className="text-teal-400">{device?.name}</span>
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
              <p>No push history found for this device.</p>
            </Card>
          ) : (
            history.map((item, index) => (
              <Card
                key={item.id || index}
                className="p-3 bg-[#06181c] border-[#0e2f37] hover:border-teal-500/50 transition-colors group"
              >
                <div className="flex items-start justify-between gap-4">
                  <div className="flex items-start gap-3 flex-1">
                    <div className="mt-1">
                      {item.status === 'success' ? (
                        <CheckCircle className="h-4 w-4 text-green-500" />
                      ) : item.status === 'failed' ? (
                        <XCircle className="h-4 w-4 text-red-500" />
                      ) : (
                        <Clock className="h-4 w-4 text-yellow-500" />
                      )}
                    </div>
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2">
                        <h3 className="text-sm font-medium text-white truncate">
                          {item.title || item.action_type || 'Push Command'}
                        </h3>
                        {item.config_version && (
                          <span className="text-[10px] px-1.5 py-0.5 rounded bg-teal-500/10 text-teal-400 border border-teal-500/20 whitespace-nowrap">
                            v{item.config_version}
                          </span>
                        )}
                      </div>
                      <p className="text-xs text-gray-400 mt-0.5">
                        {new Date(item.timestamp).toLocaleString()}
                      </p>

                      {/* Preview of details (truncated) */}
                      {item.details && (
                        <div className="mt-1.5 text-[10px] text-gray-500 font-mono truncate max-w-md">
                          {typeof item.details === 'string'
                            ? item.details
                            : JSON.stringify(item.details)}
                        </div>
                      )}
                    </div>
                  </div>

                  <div className="flex items-center gap-1 opacity-0 group-hover:opacity-100 transition-opacity">
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() => handleReuse(item)}
                      className="h-7 px-2 border-gray-700 bg-transparent text-gray-300 hover:text-white hover:bg-gray-800 text-xs"
                      title="Reuse Command"
                    >
                      <RefreshCw className="h-3 w-3 mr-1" />
                      Reuse
                    </Button>
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() => openDetails(item)}
                      className="h-7 px-2 border-gray-700 bg-transparent text-gray-300 hover:text-white hover:bg-gray-800 text-xs"
                      title="View Details"
                    >
                      <Eye className="h-3 w-3 mr-1" />
                      Details
                    </Button>
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() => confirmDelete(item)}
                      className="h-7 w-7 p-0 border-red-900/30 bg-transparent text-red-400 hover:text-red-300 hover:bg-red-900/20 hover:border-red-900/50"
                      title="Delete Record"
                    >
                      <Trash2 className="h-3 w-3" />
                    </Button>
                  </div>
                </div>
              </Card>
            ))
          )}
        </div>

        {/* Details Modal */}
        <Dialog open={isDetailsModalOpen} onOpenChange={setIsDetailsModalOpen}>
          <DialogContent className="max-w-2xl bg-card border-gray-800 text-white">
            <DialogHeader>
              <DialogTitle>Transaction Details</DialogTitle>
              <DialogDescription>
                Raw payload and execution details for this command.
              </DialogDescription>
            </DialogHeader>

            {selectedTransaction && (
              <div className="mt-4 space-y-4">
                <div className="grid grid-cols-2 gap-4 text-sm">
                  <div>
                    <span className="text-gray-500 block">Status</span>
                    <span
                      className={
                        selectedTransaction.status === 'success'
                          ? 'text-green-400'
                          : selectedTransaction.status === 'failed'
                            ? 'text-red-400'
                            : 'text-yellow-400'
                      }
                    >
                      {selectedTransaction.status?.toUpperCase()}
                    </span>
                  </div>
                  <div>
                    <span className="text-gray-500 block">Timestamp</span>
                    <span className="text-gray-300">
                      {new Date(selectedTransaction.timestamp).toLocaleString()}
                    </span>
                  </div>
                  <div>
                    <span className="text-gray-500 block">Command Type</span>
                    <span className="text-gray-300">{selectedTransaction.action_type}</span>
                  </div>
                  <div>
                    <span className="text-gray-500 block">Version</span>
                    <span className="text-gray-300">
                      {selectedTransaction.config_version || 'N/A'}
                    </span>
                  </div>
                </div>

                <div>
                  <span className="text-gray-500 block mb-2 text-sm">Payload / Details</span>
                  <div className="bg-black/50 rounded-md p-4 overflow-auto max-h-[300px]">
                    <pre className="text-xs font-mono text-green-400">
                      {typeof selectedTransaction.details === 'string'
                        ? selectedTransaction.details
                        : JSON.stringify(selectedTransaction.details, null, 2)}
                    </pre>
                  </div>
                </div>
              </div>
            )}
          </DialogContent>
        </Dialog>

        {/* Delete Confirmation Modal */}
        <Dialog open={isDeleteModalOpen} onOpenChange={setIsDeleteModalOpen}>
          <DialogContent className="max-w-md bg-card border-gray-800 text-white">
            <DialogHeader>
              <DialogTitle>Delete History Record</DialogTitle>
              <DialogDescription>
                Are you sure you want to delete this history record? This action cannot be undone.
              </DialogDescription>
            </DialogHeader>
            <DialogFooter className="mt-4 flex gap-2">
              <Button
                variant="outline"
                onClick={() => setIsDeleteModalOpen(false)}
                className="border-gray-700 text-gray-300 hover:bg-gray-800"
              >
                Cancel
              </Button>
              <Button
                variant="destructive"
                onClick={handleDelete}
                className="bg-red-900/50 hover:bg-red-900 text-red-100 border border-red-900"
              >
                Delete Record
              </Button>
            </DialogFooter>
          </DialogContent>
        </Dialog>
      </div>
    </div>
  );
}
