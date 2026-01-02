import { Button } from '@/components/ui/button';
import api from '@/services/api';
import {
  ArrowLeft,
  Plus,
  History,
  CheckCircle2,
  XCircle,
  Clock,
  FileJson,
  ChevronRight,
  X,
  Eye,
  Shield,
  Trash2,
} from 'lucide-react';
import React, { useEffect, useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import { Toast } from '@/components/ui/Toast';

// Mock history data with full payloads
const MOCK_HISTORY = [
  {
    id: 'job-1003',
    date: '2024-01-15T14:30:00Z',
    status: 'success',
    user: 'admin@homepot.io',
    summary: 'Updated volume and brightness',
    changes: 2,
    version: 'v12',
    payload: {
      title: 'Configuration Update',
      body: 'Executing APPLY_CONFIG on POS-01',
      data: {
        command: 'APPLY_CONFIG',
        timestamp: '2024-01-15T14:30:00Z',
        volume: 50,
        brightness: 75,
      },
      priority: 'high',
      ttl_seconds: 300,
      collapse_key: 'apply_config',
    },
  },
  {
    id: 'job-1002',
    date: '2024-01-10T09:15:00Z',
    status: 'success',
    user: 'admin@homepot.io',
    summary: 'Security patch application',
    changes: 1,
    version: 'v11',
    payload: {
      title: 'Security Update',
      body: 'Executing UPDATE_FIRMWARE on POS-01',
      data: {
        command: 'UPDATE_FIRMWARE',
        timestamp: '2024-01-10T09:15:00Z',
        version: '2.4.1',
        url: 'https://firmware.homepot.io/v2.4.1.bin',
      },
      priority: 'high',
      ttl_seconds: 3600,
      collapse_key: 'update_firmware',
    },
  },
  {
    id: 'job-1001',
    date: '2024-01-05T16:45:00Z',
    status: 'failed',
    user: 'system',
    summary: 'Auto-update attempt',
    changes: 1,
    version: 'v10',
    payload: {
      title: 'Auto Update',
      body: 'Executing APPLY_CONFIG on POS-01',
      data: {
        command: 'APPLY_CONFIG',
        timestamp: '2024-01-05T16:45:00Z',
        auto_update: true,
      },
      priority: 'normal',
      ttl_seconds: 300,
      collapse_key: 'apply_config',
    },
  },
];

export default function DeviceSettings() {
  const { id } = useParams();
  const navigate = useNavigate();
  const [loading, setLoading] = useState(true);
  const [device, setDevice] = useState(null);
  const [history, setHistory] = useState([]);
  const [viewingPayload, setViewingPayload] = useState(null);
  const [toast, setToast] = useState(null);
  const [deleteConfirm, setDeleteConfirm] = useState(null); // Stores ID of item to delete

  const confirmDelete = (e, historyId) => {
    e.stopPropagation();
    setDeleteConfirm(historyId);
  };

  const handleDelete = async () => {
    if (!deleteConfirm) return;
    const historyId = deleteConfirm;

    try {
      // Extract ID number from "job-123" string
      const idNumber = historyId.replace('job-', '');
      await api.devices.deleteHistoryItem(idNumber);

      // Remove from local state
      setHistory((prev) => prev.filter((item) => item.id !== historyId));
      setToast({
        title: 'Success',
        message: 'History record deleted',
        type: 'success',
      });
    } catch (err) {
      console.error('Failed to delete history:', err);
      setToast({
        title: 'Error',
        message: 'Failed to delete history record',
        type: 'error',
      });
    } finally {
      setDeleteConfirm(null);
    }
  };

  useEffect(() => {
    const fetchDeviceAndHistory = async () => {
      try {
        const deviceData = await api.devices.getDeviceById(id);
        setDevice(deviceData);

        try {
          const historyData = await api.devices.getHistory(id);
          setHistory(historyData && historyData.length > 0 ? historyData : []);
        } catch (histErr) {
          console.warn('Failed to fetch history, falling back to empty:', histErr);
          setHistory([]);
        }
      } catch (err) {
        console.error('Failed to load device data:', err);
      } finally {
        setLoading(false);
      }
    };

    fetchDeviceAndHistory();
  }, [id]);

  if (loading) {
    return <div className="p-10 text-center text-slate-400">Loading history...</div>;
  }

  return (
    <div className="min-h-screen bg-gradient-to-b from-[#041014] to-[#03121a] text-slate-200 p-6 sm:p-10 font-sans">
      <div className="max-w-5xl mx-auto">
        {/* Header */}
        <div className="flex items-center justify-between mb-8">
          <div className="flex items-center gap-4">
            <Button
              variant="ghost"
              onClick={() => navigate(`/device/${id}`)}
              className="pl-0 hover:pl-1 transition-all text-gray-400 hover:text-white hover:bg-transparent"
            >
              <ArrowLeft className="h-4 w-4 mr-2" />
              Back to Device
            </Button>
            <div>
              <h1 className="text-2xl font-semibold tracking-tight">Configuration History</h1>
              <div className="text-sm text-slate-400">
                {device?.name || 'Unknown Device'} ({id})
              </div>
            </div>
          </div>
          <div className="flex items-center gap-4">
            <Button
              onClick={() => navigate(`/device/${id}/push-review`)}
              className="bg-teal-600 hover:bg-teal-500 text-white"
            >
              <Plus className="h-4 w-4 mr-2" />
              New Configuration
            </Button>
          </div>
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
          {/* Left Column: History List */}
          <div className="lg:col-span-2 space-y-6">
            <div className="bg-[#06181c] border border-[#0e2f37] rounded-xl overflow-hidden">
              <div className="p-6 border-b border-[#0e2f37] flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <History className="h-5 w-5 text-teal-400" />
                  <h2 className="text-lg font-medium text-teal-100">Push History</h2>
                </div>
                <span className="text-xs text-slate-500 uppercase tracking-wider">
                  Last 30 Days
                </span>
              </div>

              <div className="divide-y divide-[#0e2f37]">
                {history.map((item) => (
                  <div
                    key={item.id}
                    onClick={() => setViewingPayload(item)}
                    className="p-4 hover:bg-[#0a272e]/50 transition-colors group cursor-pointer"
                  >
                    <div className="flex items-center justify-between">
                      <div className="flex items-center gap-4">
                        <div
                          className={`p-2 rounded-full ${
                            item.status === 'success'
                              ? 'bg-teal-900/30 text-teal-400'
                              : 'bg-red-900/30 text-red-400'
                          }`}
                        >
                          {item.status === 'success' ? (
                            <CheckCircle2 className="h-5 w-5" />
                          ) : (
                            <XCircle className="h-5 w-5" />
                          )}
                        </div>
                        <div>
                          <div className="flex items-center gap-2">
                            <span className="text-sm font-medium text-slate-200">
                              {item.summary}
                            </span>
                            <span className="text-xs px-2 py-0.5 rounded-full bg-[#0e2f37] text-slate-400 border border-[#133b45]">
                              {item.version}
                            </span>
                          </div>
                          <div className="flex items-center gap-3 mt-1 text-xs text-slate-500">
                            <span className="flex items-center gap-1">
                              <Clock className="h-3 w-3" />
                              {new Date(item.date).toLocaleString()}
                            </span>
                            <span>•</span>
                            <span>{item.user}</span>
                          </div>
                        </div>
                      </div>
                      <div className="flex items-center gap-2 text-slate-600 group-hover:text-teal-400 transition-colors">
                        <span className="text-xs hidden group-hover:inline-block">
                          View Details
                        </span>
                        <ChevronRight className="h-4 w-4" />
                        <button
                          onClick={(e) => confirmDelete(e, item.id)}
                          className="p-1 hover:bg-red-900/30 hover:text-red-400 rounded-full transition-colors ml-2"
                          title="Delete Record"
                        >
                          <Trash2 className="h-4 w-4" />
                        </button>
                      </div>
                    </div>
                  </div>
                ))}
              </div>

              {history.length === 0 && (
                <div className="p-10 text-center text-slate-500">
                  No configuration history found.
                </div>
              )}
            </div>
          </div>

          {/* Right Column: System Information */}
          <div className="lg:col-span-1 space-y-6">
            <div className="bg-[#06181c]/50 border border-[#0e2f37]/50 rounded-xl p-6">
              <div className="flex items-center gap-2 mb-6">
                <Shield className="h-5 w-5 text-slate-400" />
                <h3 className="text-lg font-medium text-slate-200">System Information</h3>
              </div>

              <div className="space-y-6">
                <div>
                  <div className="text-xs text-slate-500 uppercase tracking-wider mb-1">
                    Serial Number
                  </div>
                  <div className="text-sm text-slate-200 font-mono">
                    {device?.serial_number || 'SN-12345678'}
                  </div>
                </div>

                <div>
                  <div className="text-xs text-slate-500 uppercase tracking-wider mb-1">
                    MAC Address
                  </div>
                  <div className="text-sm text-slate-200 font-mono">
                    {device?.mac_address || '00:1A:2B:3C:4D:5E'}
                  </div>
                </div>

                <div>
                  <div className="text-xs text-slate-500 uppercase tracking-wider mb-1">
                    Firmware Version
                  </div>
                  <div className="text-sm text-slate-200 font-mono">
                    {device?.firmware_version || 'v2.4.1'}
                  </div>
                </div>

                <div>
                  <div className="text-xs text-slate-500 uppercase tracking-wider mb-1">
                    Last Boot
                  </div>
                  <div className="text-sm text-slate-200 font-mono">
                    {device?.last_boot || '2024-01-15 08:30:00'}
                  </div>
                </div>

                <div>
                  <div className="text-xs text-slate-500 uppercase tracking-wider mb-1">
                    IP Address
                  </div>
                  <div className="text-sm text-slate-200 font-mono">
                    {device?.ip_address || '192.168.1.105'}
                  </div>
                </div>
              </div>

              <div className="mt-8 p-4 bg-[#0a272e]/30 rounded-lg border border-[#0e2f37] text-xs text-slate-400 leading-relaxed">
                These settings are managed by the system administrator and cannot be modified
                directly. Contact support for assistance.
              </div>
            </div>
          </div>
        </div>

        {/* Delete Confirmation Modal */}
        {deleteConfirm && (
          <div className="fixed inset-0 bg-black/80 backdrop-blur-sm z-50 flex items-center justify-center p-4">
            <div className="bg-[#020817] border border-[#1e293b] rounded-xl w-full max-w-md shadow-2xl animate-in fade-in zoom-in-95 duration-200">
              <div className="p-6">
                <div className="flex items-center gap-4 mb-4">
                  <div className="p-3 bg-red-900/20 rounded-full">
                    <Trash2 className="h-6 w-6 text-red-500" />
                  </div>
                  <div>
                    <h3 className="text-lg font-semibold text-slate-200">Delete History Record</h3>
                    <p className="text-sm text-slate-400">
                      Are you sure you want to delete this record?
                    </p>
                  </div>
                </div>
                <p className="text-sm text-slate-500 mb-6 ml-16">
                  This action cannot be undone. The configuration history log will be permanently
                  removed.
                </p>
                <div className="flex justify-end gap-3">
                  <Button
                    variant="ghost"
                    onClick={() => setDeleteConfirm(null)}
                    className="text-slate-400 hover:text-white hover:bg-slate-800"
                  >
                    Cancel
                  </Button>
                  <Button onClick={handleDelete} className="bg-red-600 hover:bg-red-700 text-white">
                    Delete Record
                  </Button>
                </div>
              </div>
            </div>
          </div>
        )}

        {/* Payload Modal */}
        {viewingPayload && (
          <div className="fixed inset-0 bg-black/80 backdrop-blur-sm z-50 flex items-center justify-center p-4">
            <div className="bg-[#020817] border border-[#1e293b] rounded-xl w-full max-w-2xl max-h-[80vh] flex flex-col shadow-2xl animate-in fade-in zoom-in-95 duration-200">
              <div className="flex items-center justify-between p-4 border-b border-[#1e293b] bg-[#0f172a] rounded-t-xl">
                <div className="flex items-center gap-2">
                  <FileJson className="h-5 w-5 text-teal-400" />
                  <h3 className="text-lg font-medium text-slate-200">Transaction Details</h3>
                </div>
                <Button
                  variant="ghost"
                  size="icon"
                  onClick={() => setViewingPayload(null)}
                  className="text-slate-400 hover:text-white hover:bg-slate-800"
                >
                  <X className="h-5 w-5" />
                </Button>
              </div>
              <div className="p-0 overflow-auto flex-1 bg-[#020817]">
                <pre className="p-6 font-mono text-xs text-blue-300 leading-relaxed">
                  {JSON.stringify(viewingPayload, null, 2)}
                </pre>
              </div>
              <div className="p-4 border-t border-[#1e293b] bg-[#0f172a] flex justify-end rounded-b-xl">
                <Button
                  onClick={() => setViewingPayload(null)}
                  className="bg-slate-700 hover:bg-slate-600 text-white"
                >
                  Close
                </Button>
              </div>
            </div>
          </div>
        )}
      </div>
      {toast && (
        <Toast
          title={toast.title}
          message={toast.message}
          type={toast.type}
          onClose={() => setToast(null)}
        />
      )}
    </div>
  );
}
