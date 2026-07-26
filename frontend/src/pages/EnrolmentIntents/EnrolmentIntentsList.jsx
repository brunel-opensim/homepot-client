import React, { useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import {
  ArrowLeft,
  Loader2,
  KeyRound,
  CheckCircle,
  XCircle,
  Clock,
  RotateCcw,
  Ban,
  Eye,
  PlusCircle,
  FileKey,
} from 'lucide-react';
import api from '@/services/api';
import { Button } from '@/components/ui/button';
import { Card, CardContent } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';

const STATUS_META = {
  pending: { label: 'Pending', color: 'bg-yellow-500/10 text-yellow-400' },
  approved: { label: 'Approved', color: 'bg-green-500/10 text-green-400' },
  rejected: { label: 'Rejected', color: 'bg-red-500/10 text-red-400' },
  consumed: { label: 'Consumed', color: 'bg-blue-500/10 text-blue-400' },
  expired: { label: 'Expired', color: 'bg-gray-500/10 text-gray-400' },
  revoked: { label: 'Revoked', color: 'bg-purple-500/10 text-purple-400' },
};

export default function EnrolmentIntentsList() {
  const { id: siteId } = useParams();
  const navigate = useNavigate();

  const [intents, setIntents] = useState([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [statusFilter, setStatusFilter] = useState('');
  const [showCreate, setShowCreate] = useState(false);
  const [createForm, setCreateForm] = useState({
    expected_device_identity: '',
    expires_in_hours: 48,
    idempotency_key: '',
  });
  const [createResult, setCreateResult] = useState(null);
  const [regenerating, setRegenerating] = useState(null);

  const fetchIntents = async () => {
    try {
      setLoading(true);
      const data = await api.enrolmentIntents.list(siteId, statusFilter || null, 100, 0);
      setIntents(data.intents || []);
      setTotal(data.total || 0);
    } catch (err) {
      console.error('Failed to load enrolment intents:', err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchIntents();
  }, [siteId, statusFilter]);

  const counts = {
    active: intents.filter((i) => i.status === 'pending' || i.status === 'approved').length,
    consumed: intents.filter((i) => i.status === 'consumed').length,
    expired: intents.filter((i) => i.status === 'expired').length,
    revoked: intents.filter((i) => i.status === 'revoked').length,
    rejected: intents.filter((i) => i.status === 'rejected').length,
  };

  const handleCreate = async (e) => {
    e.preventDefault();
    try {
      const payload = {
        enrolment_method: 'pre-provisioned',
        expires_in_hours: createForm.expires_in_hours,
      };
      if (createForm.expected_device_identity) {
        payload.expected_device_identity = createForm.expected_device_identity;
      }
      if (createForm.idempotency_key) {
        payload.idempotency_key = createForm.idempotency_key;
      }
      const result = await api.enrolmentIntents.create(siteId, payload);
      setCreateResult(result);
      setShowCreate(false);
      setCreateForm({ expected_device_identity: '', expires_in_hours: 48, idempotency_key: '' });
      fetchIntents();
    } catch (err) {
      console.error('Failed to create enrolment intent:', err);
      alert('Failed to create enrolment intent');
    }
  };

  const handleRevoke = async (intentId) => {
    if (!window.confirm('Revoke this enrolment intent? The current token will no longer work.'))
      return;
    try {
      await api.enrolmentIntents.updateStatus(siteId, intentId, { status: 'revoked' });
      fetchIntents();
    } catch (err) {
      console.error('Failed to revoke intent:', err);
    }
  };

  const handleRegenerate = async (intentId) => {
    try {
      setRegenerating(intentId);
      const result = await api.enrolmentIntents.regenerateToken(siteId, intentId);
      alert(
        `New claim token: ${result.claim_token}\n\nSave this token securely — it will not be shown again.`
      );
      fetchIntents();
    } catch (err) {
      console.error('Failed to regenerate token:', err);
      alert('Failed to regenerate token');
    } finally {
      setRegenerating(null);
    }
  };

  const handleApprove = async (intentId) => {
    try {
      await api.enrolmentIntents.updateStatus(siteId, intentId, { status: 'approved' });
      fetchIntents();
    } catch (err) {
      console.error('Failed to approve intent:', err);
    }
  };

  const handleReject = async (intentId) => {
    try {
      await api.enrolmentIntents.updateStatus(siteId, intentId, { status: 'rejected' });
      fetchIntents();
    } catch (err) {
      console.error('Failed to reject intent:', err);
    }
  };

  const isExpired = (expiresAt) => {
    return expiresAt && new Date(expiresAt) < new Date();
  };

  return (
    <div className="h-full flex flex-col overflow-hidden bg-[#0b0e13] p-2">
      <div className="container mx-auto max-w-7xl h-full flex flex-col">
        {/* Header */}
        <div className="shrink-0 mb-4 space-y-4">
          <Button
            variant="ghost"
            onClick={() => navigate(`/sites/${siteId}`)}
            className="pl-0 hover:pl-1 transition-all text-gray-400 hover:text-white hover:bg-transparent"
          >
            <ArrowLeft className="h-4 w-4 mr-2" />
            Back to Site
          </Button>

          <div className="flex flex-col md:flex-row justify-between items-start md:items-center gap-4">
            <div>
              <h1 className="text-3xl font-bold tracking-tight mb-1 text-white">
                Enrolment Intents
              </h1>
              <p className="text-gray-400 text-sm">
                Manage pre-provisioned device enrolment intents for this site
              </p>
            </div>
            <Button
              onClick={() => {
                setShowCreate(!showCreate);
                setCreateResult(null);
              }}
              className="bg-transparent border text-blue-400 border-blue-400 hover:bg-blue-400/10"
            >
              {showCreate ? (
                <>Cancel</>
              ) : (
                <>
                  <PlusCircle className="h-4 w-4 mr-2" />
                  Create Intent
                </>
              )}
            </Button>
          </div>

          {/* Stats Cards */}
          <div className="grid grid-cols-1 md:grid-cols-5 gap-3">
            <Card className="p-3 bg-card border-border">
              <div className="flex items-center gap-3">
                <div className="p-2 bg-yellow-500/10 rounded-full">
                  <Clock className="h-4 w-4 text-yellow-500" />
                </div>
                <div>
                  <p className="text-xs text-gray-400 font-medium">Active</p>
                  <h3 className="text-lg font-bold text-white">{counts.active}</h3>
                </div>
              </div>
            </Card>
            <Card className="p-3 bg-card border-border">
              <div className="flex items-center gap-3">
                <div className="p-2 bg-blue-500/10 rounded-full">
                  <CheckCircle className="h-4 w-4 text-blue-500" />
                </div>
                <div>
                  <p className="text-xs text-gray-400 font-medium">Consumed</p>
                  <h3 className="text-lg font-bold text-white">{counts.consumed}</h3>
                </div>
              </div>
            </Card>
            <Card className="p-3 bg-card border-border">
              <div className="flex items-center gap-3">
                <div className="p-2 bg-gray-500/10 rounded-full">
                  <Ban className="h-4 w-4 text-gray-500" />
                </div>
                <div>
                  <p className="text-xs text-gray-400 font-medium">Expired</p>
                  <h3 className="text-lg font-bold text-white">{counts.expired}</h3>
                </div>
              </div>
            </Card>
            <Card className="p-3 bg-card border-border">
              <div className="flex items-center gap-3">
                <div className="p-2 bg-purple-500/10 rounded-full">
                  <RotateCcw className="h-4 w-4 text-purple-500" />
                </div>
                <div>
                  <p className="text-xs text-gray-400 font-medium">Revoked</p>
                  <h3 className="text-lg font-bold text-white">{counts.revoked}</h3>
                </div>
              </div>
            </Card>
            <Card className="p-3 bg-card border-border">
              <div className="flex items-center gap-3">
                <div className="p-2 bg-red-500/10 rounded-full">
                  <XCircle className="h-4 w-4 text-red-500" />
                </div>
                <div>
                  <p className="text-xs text-gray-400 font-medium">Rejected</p>
                  <h3 className="text-lg font-bold text-white">{counts.rejected}</h3>
                </div>
              </div>
            </Card>
          </div>
        </div>

        {/* Create Form */}
        {showCreate && (
          <Card className="mb-4 p-4 bg-card border-border shrink-0">
            <h3 className="font-semibold text-white mb-3 flex items-center gap-2">
              <PlusCircle className="h-4 w-4 text-blue-400" />
              Create New Enrolment Intent
            </h3>
            <form onSubmit={handleCreate} className="space-y-4">
              <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                <div className="space-y-1.5">
                  <Label htmlFor="expected_device_identity" className="text-gray-300">
                    Expected Device Identity <span className="text-gray-500">(optional)</span>
                  </Label>
                  <Input
                    id="expected_device_identity"
                    type="text"
                    value={createForm.expected_device_identity}
                    onChange={(e) =>
                      setCreateForm({ ...createForm, expected_device_identity: e.target.value })
                    }
                    placeholder="e.g. serial number or hardware ID"
                    className="bg-[#1a1f2e] border-gray-700 text-white placeholder:text-gray-500"
                  />
                </div>
                <div className="space-y-1.5">
                  <Label htmlFor="expires_in_hours" className="text-gray-300">
                    Expires In (hours)
                  </Label>
                  <Input
                    id="expires_in_hours"
                    type="number"
                    value={createForm.expires_in_hours}
                    onChange={(e) =>
                      setCreateForm({
                        ...createForm,
                        expires_in_hours: parseInt(e.target.value) || 48,
                      })
                    }
                    min={1}
                    max={8760}
                    className="bg-[#1a1f2e] border-gray-700 text-white placeholder:text-gray-500"
                  />
                </div>
                <div className="space-y-1.5">
                  <Label htmlFor="idempotency_key" className="text-gray-300">
                    Idempotency Key <span className="text-gray-500">(optional)</span>
                  </Label>
                  <Input
                    id="idempotency_key"
                    type="text"
                    value={createForm.idempotency_key}
                    onChange={(e) =>
                      setCreateForm({ ...createForm, idempotency_key: e.target.value })
                    }
                    placeholder="e.g. req-abc-123"
                    className="bg-[#1a1f2e] border-gray-700 text-white placeholder:text-gray-500"
                  />
                </div>
              </div>
              <div className="flex gap-2">
                <Button type="submit" className="bg-blue-600 text-white hover:bg-blue-700">
                  <KeyRound className="h-4 w-4 mr-2" />
                  Create Intent
                </Button>
                <Button
                  type="button"
                  variant="ghost"
                  onClick={() => setShowCreate(false)}
                  className="text-gray-400 hover:text-white"
                >
                  Cancel
                </Button>
              </div>
            </form>
          </Card>
        )}

        {/* Token Result */}
        {createResult && (
          <Card className="mb-4 p-4 border border-yellow-500/30 bg-yellow-500/5 shrink-0">
            <div className="flex items-start gap-3">
              <FileKey className="h-5 w-5 text-yellow-400 mt-0.5 shrink-0" />
              <div>
                <h3 className="font-semibold text-yellow-400 mb-2">Intent Created Successfully</h3>
                <p className="text-sm text-yellow-300/80 mb-2">
                  Share this one-time claim token with the installer. It will not be shown again.
                </p>
                <div className="bg-yellow-500/10 border border-yellow-500/20 rounded-md px-4 py-2.5">
                  <code className="text-sm text-yellow-200 font-mono break-all">
                    {createResult.claim_token}
                  </code>
                </div>
              </div>
            </div>
          </Card>
        )}

        {/* Filter */}
        <div className="flex items-center gap-3 mb-4 shrink-0">
          <select
            value={statusFilter}
            onChange={(e) => setStatusFilter(e.target.value)}
            className="h-9 rounded-md border border-gray-700 bg-[#1a1f2e] text-gray-300 px-3 py-1 text-sm focus:outline-none focus:ring-1 focus:ring-ring"
          >
            <option value="">All Statuses</option>
            <option value="pending">Pending</option>
            <option value="approved">Approved</option>
            <option value="rejected">Rejected</option>
            <option value="consumed">Consumed</option>
            <option value="expired">Expired</option>
            <option value="revoked">Revoked</option>
          </select>
          <span className="text-sm text-gray-500">{total} total</span>
        </div>

        {/* Table */}
        <div className="flex-1 min-h-0 flex flex-col">
          {loading ? (
            <div className="flex justify-center items-center h-64">
              <Loader2 className="h-8 w-8 animate-spin text-primary" />
            </div>
          ) : intents.length === 0 ? (
            <Card className="p-8 text-center text-gray-400 border-dashed border-border bg-card">
              <KeyRound className="h-8 w-8 mx-auto mb-3 opacity-50" />
              <p className="mb-1">No enrolment intents found</p>
              <p className="text-sm text-gray-500">
                Create one to get started with pre-provisioned device enrolment.
              </p>
              <Button
                onClick={() => {
                  setShowCreate(true);
                  setCreateResult(null);
                }}
                className="mt-4 bg-transparent border text-blue-400 border-blue-400 hover:bg-blue-400/10"
              >
                <PlusCircle className="h-4 w-4 mr-2" />
                Create Intent
              </Button>
            </Card>
          ) : (
            <div className="rounded-md border border-border bg-card flex-1 overflow-hidden relative">
              <div className="absolute inset-0 overflow-auto">
                <table className="w-full caption-bottom text-sm text-left">
                  <thead className="[&_tr]:border-b border-border sticky top-0 bg-card z-10">
                    <tr className="border-b border-border transition-colors hover:bg-muted/50">
                      <th className="h-12 px-4 align-middle font-medium text-gray-400">
                        Intent ID
                      </th>
                      <th className="h-12 px-4 align-middle font-medium text-gray-400">Status</th>
                      <th className="h-12 px-4 align-middle font-medium text-gray-400">Expires</th>
                      <th className="h-12 px-4 align-middle font-medium text-gray-400">
                        Device Identity
                      </th>
                      <th className="h-12 px-4 align-middle font-medium text-gray-400">Created</th>
                      <th className="h-12 px-4 align-middle font-medium text-gray-400 text-right">
                        Actions
                      </th>
                    </tr>
                  </thead>
                  <tbody className="[&_tr:last-child]:border-0">
                    {intents.map((intent) => {
                      const meta = STATUS_META[intent.status] || STATUS_META.pending;
                      const expired = isExpired(intent.expires_at);
                      return (
                        <tr
                          key={intent.id}
                          className="border-b border-border transition-colors hover:bg-muted/50"
                        >
                          <td className="p-4 align-middle font-mono text-xs text-gray-300">
                            {intent.intent_id}
                          </td>
                          <td className="p-4 align-middle">
                            <span
                              className={`inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium ${meta.color}`}
                            >
                              {meta.label}
                            </span>
                          </td>
                          <td className="p-4 align-middle">
                            <div className="flex flex-col">
                              <span
                                className={`text-sm ${expired ? 'text-red-400' : 'text-gray-300'}`}
                              >
                                {intent.expires_at
                                  ? new Date(intent.expires_at).toLocaleString()
                                  : '-'}
                              </span>
                              {expired && (
                                <span className="text-[10px] text-red-500 font-medium">
                                  Expired
                                </span>
                              )}
                            </div>
                          </td>
                          <td className="p-4 align-middle text-sm text-gray-300">
                            {intent.expected_device_identity || (
                              <span className="text-gray-500 italic">Not specified</span>
                            )}
                          </td>
                          <td className="p-4 align-middle text-sm text-gray-300">
                            {intent.created_at ? new Date(intent.created_at).toLocaleString() : '-'}
                          </td>
                          <td className="p-4 align-middle text-right">
                            <div className="flex justify-end gap-1.5">
                              {intent.status === 'pending' && (
                                <>
                                  <Button
                                    variant="ghost"
                                    size="sm"
                                    onClick={() => handleApprove(intent.intent_id)}
                                    className="h-7 px-2 text-green-400 hover:text-green-300 hover:bg-green-500/10"
                                  >
                                    <CheckCircle className="h-3.5 w-3.5 mr-1" />
                                    Approve
                                  </Button>
                                  <Button
                                    variant="ghost"
                                    size="sm"
                                    onClick={() => handleReject(intent.intent_id)}
                                    className="h-7 px-2 text-red-400 hover:text-red-300 hover:bg-red-500/10"
                                  >
                                    <XCircle className="h-3.5 w-3.5 mr-1" />
                                    Reject
                                  </Button>
                                </>
                              )}
                              {(intent.status === 'pending' || intent.status === 'approved') && (
                                <>
                                  <Button
                                    variant="ghost"
                                    size="sm"
                                    onClick={() => handleRegenerate(intent.intent_id)}
                                    disabled={regenerating === intent.intent_id}
                                    className="h-7 px-2 text-yellow-400 hover:text-yellow-300 hover:bg-yellow-500/10 disabled:opacity-50"
                                  >
                                    <RotateCcw className="h-3.5 w-3.5 mr-1" />
                                    {regenerating === intent.intent_id ? '...' : 'Regen Token'}
                                  </Button>
                                  <Button
                                    variant="ghost"
                                    size="sm"
                                    onClick={() => handleRevoke(intent.intent_id)}
                                    className="h-7 px-2 text-purple-400 hover:text-purple-300 hover:bg-purple-500/10"
                                  >
                                    <Ban className="h-3.5 w-3.5 mr-1" />
                                    Revoke
                                  </Button>
                                </>
                              )}
                              {intent.status === 'consumed' && (
                                <span className="text-xs text-gray-500 italic flex items-center gap-1 px-2">
                                  <CheckCircle className="h-3 w-3 text-blue-400" />
                                  Consumed
                                </span>
                              )}
                            </div>
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
