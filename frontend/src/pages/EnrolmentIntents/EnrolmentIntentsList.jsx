import React, { useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import api from '../../services/api';

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
      const data = await api.enrolmentIntents.list(
        siteId,
        statusFilter || null,
        100,
        0
      );
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

  const statusColors = {
    pending: 'bg-yellow-100 text-yellow-800',
    approved: 'bg-green-100 text-green-800',
    rejected: 'bg-red-100 text-red-800',
    consumed: 'bg-blue-100 text-blue-800',
    expired: 'bg-gray-100 text-gray-800',
    revoked: 'bg-purple-100 text-purple-800',
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
    if (!window.confirm('Revoke this enrolment intent? The current token will no longer work.')) return;
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
      alert(`New claim token: ${result.claim_token}\n\nSave this token securely — it will not be shown again.`);
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

  return (
    <div className="p-6">
      <div className="flex justify-between items-center mb-6">
        <div>
          <h1 className="text-2xl font-bold">Enrolment Intents</h1>
          <p className="text-gray-600 text-sm">
            Manage pre-provisioned device enrolment intents for this site
          </p>
        </div>
        <div className="flex gap-3">
          <button
            onClick={() => navigate(`/sites/${siteId}`)}
            className="px-4 py-2 border border-gray-300 rounded-lg text-sm hover:bg-gray-50"
          >
            Back to Site
          </button>
          <button
            onClick={() => { setShowCreate(!showCreate); setCreateResult(null); }}
            className="px-4 py-2 bg-blue-600 text-white rounded-lg text-sm hover:bg-blue-700"
          >
            {showCreate ? 'Cancel' : 'Create Intent'}
          </button>
        </div>
      </div>

      {showCreate && (
        <div className="mb-6 p-4 border border-gray-200 rounded-lg bg-gray-50">
          <h3 className="font-semibold mb-3">Create New Enrolment Intent</h3>
          <form onSubmit={handleCreate} className="space-y-3">
            <div>
              <label className="block text-sm font-medium text-gray-700">
                Expected Device Identity (optional)
              </label>
              <input
                type="text"
                value={createForm.expected_device_identity}
                onChange={(e) => setCreateForm({ ...createForm, expected_device_identity: e.target.value })}
                placeholder="e.g. serial number or hardware ID"
                className="mt-1 block w-full border border-gray-300 rounded-md p-2 text-sm"
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700">
                Expires In (hours)
              </label>
              <input
                type="number"
                value={createForm.expires_in_hours}
                onChange={(e) => setCreateForm({ ...createForm, expires_in_hours: parseInt(e.target.value) || 48 })}
                min={1}
                max={8760}
                className="mt-1 block w-full border border-gray-300 rounded-md p-2 text-sm"
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700">
                Idempotency Key (optional)
              </label>
              <input
                type="text"
                value={createForm.idempotency_key}
                onChange={(e) => setCreateForm({ ...createForm, idempotency_key: e.target.value })}
                placeholder="e.g. req-abc-123"
                className="mt-1 block w-full border border-gray-300 rounded-md p-2 text-sm"
              />
            </div>
            <button
              type="submit"
              className="px-4 py-2 bg-blue-600 text-white rounded-lg text-sm hover:bg-blue-700"
            >
              Create Intent
            </button>
          </form>
        </div>
      )}

      {createResult && (
        <div className="mb-6 p-4 border border-yellow-300 rounded-lg bg-yellow-50">
          <h3 className="font-semibold text-yellow-800 mb-2">Intent Created!</h3>
          <p className="text-sm text-yellow-700 mb-1">
            <strong>Claim Token:</strong>{' '}
            <span className="font-mono bg-yellow-100 px-2 py-1 rounded">
              {createResult.claim_token}
            </span>
          </p>
          <p className="text-xs text-yellow-600">
            Save this token securely. It will not be shown again.
          </p>
        </div>
      )}

      <div className="mb-4">
        <select
          value={statusFilter}
          onChange={(e) => setStatusFilter(e.target.value)}
          className="border border-gray-300 rounded-md p-2 text-sm"
        >
          <option value="">All Statuses</option>
          <option value="pending">Pending</option>
          <option value="approved">Approved</option>
          <option value="rejected">Rejected</option>
          <option value="consumed">Consumed</option>
          <option value="expired">Expired</option>
          <option value="revoked">Revoked</option>
        </select>
        <span className="ml-3 text-sm text-gray-500">{total} total</span>
      </div>

      {loading ? (
        <div className="text-center py-10 text-gray-500">Loading...</div>
      ) : intents.length === 0 ? (
        <div className="text-center py-10 text-gray-500">
          No enrolment intents found. Create one to get started.
        </div>
      ) : (
        <div className="overflow-x-auto">
          <table className="min-w-full bg-white border border-gray-200 rounded-lg">
            <thead>
              <tr className="bg-gray-50 border-b">
                <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Intent ID</th>
                <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Status</th>
                <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Expires</th>
                <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Device Identity</th>
                <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Created</th>
                <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Actions</th>
              </tr>
            </thead>
            <tbody>
              {intents.map((intent) => (
                <tr key={intent.id} className="border-b hover:bg-gray-50">
                  <td className="px-4 py-3 text-sm font-mono">{intent.intent_id}</td>
                  <td className="px-4 py-3">
                    <span
                      className={`px-2 py-1 rounded-full text-xs font-medium ${
                        statusColors[intent.status] || 'bg-gray-100 text-gray-800'
                      }`}
                    >
                      {intent.status}
                    </span>
                  </td>
                  <td className="px-4 py-3 text-sm">
                    {intent.expires_at ? (
                      <span className={new Date(intent.expires_at) < new Date() ? 'text-red-600' : ''}>
                        {new Date(intent.expires_at).toLocaleString()}
                      </span>
                    ) : '-'}
                  </td>
                  <td className="px-4 py-3 text-sm">
                    {intent.expected_device_identity || '-'}
                  </td>
                  <td className="px-4 py-3 text-sm">
                    {intent.created_at ? new Date(intent.created_at).toLocaleString() : '-'}
                  </td>
                  <td className="px-4 py-3 text-sm">
                    <div className="flex gap-2">
                      {intent.status === 'pending' && (
                        <>
                          <button
                            onClick={() => handleApprove(intent.intent_id)}
                            className="px-3 py-1 bg-green-600 text-white rounded text-xs hover:bg-green-700"
                          >
                            Approve
                          </button>
                          <button
                            onClick={() => handleReject(intent.intent_id)}
                            className="px-3 py-1 bg-red-600 text-white rounded text-xs hover:bg-red-700"
                          >
                            Reject
                          </button>
                        </>
                      )}
                      {(intent.status === 'pending' || intent.status === 'approved') && (
                        <>
                          <button
                            onClick={() => handleRegenerate(intent.intent_id)}
                            disabled={regenerating === intent.intent_id}
                            className="px-3 py-1 bg-yellow-600 text-white rounded text-xs hover:bg-yellow-700 disabled:opacity-50"
                          >
                            {regenerating === intent.intent_id ? '...' : 'Regen Token'}
                          </button>
                          <button
                            onClick={() => handleRevoke(intent.intent_id)}
                            className="px-3 py-1 bg-purple-600 text-white rounded text-xs hover:bg-purple-700"
                          >
                            Revoke
                          </button>
                        </>
                      )}
                      {intent.status === 'consumed' && (
                        <span className="text-xs text-gray-400 italic">Consumed</span>
                      )}
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
