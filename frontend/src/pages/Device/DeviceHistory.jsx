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
    // Navigate to PushReview with initial data
    navigate(`/device/${id}/push-review`, {
      state: {
        initialCommand: item.action_type || 'CUSTOM',
        initialData: item.details,
      },
    });
  };

  if (loading) {
    return (
      <div className="flex justify-center items-center h-64">
        <Loader2 className="h-8 w-8 animate-spin text-primary" />
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-background text-foreground py-6 px-4">
      <div className="container mx-auto max-w-4xl">
        {toast && <Toast {...toast} onClose={() => setToast(null)} />}

        <Button
          variant="ghost"
          onClick={() => navigate(`/device/${id}`)}
          className="mb-4 pl-0 hover:pl-1 transition-all text-gray-400 hover:text-white hover:bg-transparent"
        >
          <ArrowLeft className="h-4 w-4 mr-2" />
          Back to Device
        </Button>

        <div className="mb-8">
          <h1 className="text-2xl font-bold tracking-tight text-white">Push History</h1>
          <p className="text-gray-400">
            History of push commands for <span className="text-teal-400">{device?.name}</span>
          </p>
        </div>

        <div className="space-y-4">
          {history.length === 0 ? (
            <Card className="p-8 text-center bg-card border-border text-gray-400">
              <Clock className="h-12 w-12 mx-auto mb-4 opacity-20" />
              <p>No push history found for this device.</p>
            </Card>
          ) : (
            history.map((item, index) => (
              <Card
                key={item.id || index}
                className="p-4 bg-card border-border hover:border-teal-500/50 transition-colors group"
              >
                <div className="flex items-start justify-between gap-4">
                  <div className="flex items-start gap-4 flex-1">
                    <div className="mt-1">
                      {item.status === 'success' ? (
                        <CheckCircle className="h-5 w-5 text-green-500" />
                      ) : item.status === 'failed' ? (
                        <XCircle className="h-5 w-5 text-red-500" />
                      ) : (
                        <Clock className="h-5 w-5 text-yellow-500" />
                      )}
                    </div>
                    <div className="flex-1">
                      <div className="flex items-center gap-2">
                        <h3 className="font-medium text-white">
                          {item.title || item.action_type || 'Push Command'}
                        </h3>
                        {item.config_version && (
                          <span className="text-xs px-2 py-0.5 rounded bg-teal-500/10 text-teal-400 border border-teal-500/20">
                            v{item.config_version}
                          </span>
                        )}
                      </div>
                      <p className="text-sm text-gray-400 mt-1">
                        {new Date(item.timestamp).toLocaleString()}
                      </p>

                      {/* Preview of details (truncated) */}
                      {item.details && (
                        <div className="mt-2 text-xs text-gray-500 font-mono truncate max-w-md">
                          {typeof item.details === 'string'
                            ? item.details
                            : JSON.stringify(item.details)}
                        </div>
                      )}
                    </div>
                  </div>

                  <div className="flex items-center gap-2 opacity-0 group-hover:opacity-100 transition-opacity">
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() => handleReuse(item)}
                      className="h-8 border-gray-700 text-gray-300 hover:text-white hover:bg-gray-800"
                      title="Reuse Command"
                    >
                      <RefreshCw className="h-4 w-4 mr-2" />
                      Reuse
                    </Button>
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() => openDetails(item)}
                      className="h-8 border-gray-700 text-gray-300 hover:text-white hover:bg-gray-800"
                      title="View Details"
                    >
                      <Eye className="h-4 w-4 mr-2" />
                      Details
                    </Button>
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() => confirmDelete(item)}
                      className="h-8 border-red-900/30 text-red-400 hover:text-red-300 hover:bg-red-900/20 hover:border-red-900/50"
                      title="Delete Record"
                    >
                      <Trash2 className="h-4 w-4" />
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
