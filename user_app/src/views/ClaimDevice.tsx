import React, { useState } from 'react';
import { useApp } from '../context/AppContext';
import { apiBaseUrl } from '../config/api';

export default function ClaimDevice() {
  const { setCurrentView, setDeviceInfo, setIsProvisioned } = useApp();
  const [step, setStep] = useState(1);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [form, setForm] = useState({
    intentId: '',
    claimToken: '',
    deviceName: '',
    deviceType: 'pos_terminal',
    deviceOs: '',
  });

  const deviceTypes = [
    'pos_terminal',
    'virtual_terminal',
    'kiosk',
    'tablet',
    'mobile_scanner',
    'printer',
    'scanner',
    'signage',
  ];

  const osOptions = [
    'Android',
    'iOS',
    'Windows',
    'Linux',
    'macOS',
    'Other',
  ];

  const handleChange = (field, value) => {
    setForm((prev) => ({ ...prev, [field]: value }));
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setLoading(true);
    setError('');

    try {
      const deviceOs = form.deviceOs || navigator.platform || 'Unknown';
      const deviceName = form.deviceName || `Device-${Math.random().toString(36).slice(2, 8)}`;

      const response = await fetch(
        `${apiBaseUrl}/enrolment-intents/${form.intentId}/claim`,
        {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            claim_token: form.claimToken,
            device_name: deviceName,
            device_type: form.deviceType,
            os_details: deviceOs,
          }),
        }
      );

      if (!response.ok) {
        const errData = await response.json().catch(() => ({}));
        throw new Error(errData.detail || `Claim failed (${response.status})`);
      }

      const result = await response.json();

      localStorage.setItem('homepot_token', result.device_id);
      localStorage.setItem('homepot_device_id', result.device_id);
      localStorage.setItem('homepot_device_name', deviceName);
      localStorage.setItem('homepot_device_type', form.deviceType);
      localStorage.setItem('homepot_device_os', deviceOs);
      localStorage.setItem('homepot_enrollment_method', 'pre-provisioned');
      sessionStorage.setItem('homepot_api_key', result.api_key);

      setDeviceInfo({
        deviceId: result.device_id,
        siteId: result.site_id,
        deviceName,
        token: result.api_key,
      });
      setIsProvisioned(true);
      setCurrentView('home');
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  const handleBackToSetup = () => {
    setCurrentView('setup');
  };

  return (
    <div className="min-h-screen bg-gradient-to-br from-gray-900 to-gray-800 text-white flex flex-col">
      <div className="flex-1 p-6 flex flex-col justify-center max-w-md mx-auto w-full">
        <div className="text-center mb-8">
          <div className="text-5xl mb-3">🔗</div>
          <h1 className="text-2xl font-bold">Claim Device</h1>
          <p className="text-gray-400 mt-2">
            Enter the claim token provided by your administrator
          </p>
        </div>

        {error && (
          <div className="mb-4 p-3 bg-red-900/50 border border-red-700 rounded-lg text-sm text-red-200">
            {error}
          </div>
        )}

        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label className="block text-sm font-medium text-gray-300 mb-1">
              Intent ID *
            </label>
            <input
              type="text"
              value={form.intentId}
              onChange={(e) => handleChange('intentId', e.target.value)}
              placeholder="Intent ID from administrator"
              required
              disabled={loading}
              className="w-full px-4 py-3 bg-gray-700 border border-gray-600 rounded-lg text-white placeholder-gray-500 focus:outline-none focus:ring-2 focus:ring-blue-500"
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-300 mb-1">
              Claim Token *
            </label>
            <input
              type="text"
              value={form.claimToken}
              onChange={(e) => handleChange('claimToken', e.target.value)}
              placeholder="Claim token from administrator"
              required
              disabled={loading}
              className="w-full px-4 py-3 bg-gray-700 border border-gray-600 rounded-lg text-white placeholder-gray-500 focus:outline-none focus:ring-2 focus:ring-blue-500"
            />
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-300 mb-1">
              Device Name
            </label>
            <input
              type="text"
              value={form.deviceName}
              onChange={(e) => handleChange('deviceName', e.target.value)}
              placeholder="e.g. Kitchen POS A"
              disabled={loading}
              className="w-full px-4 py-3 bg-gray-700 border border-gray-600 rounded-lg text-white placeholder-gray-500 focus:outline-none focus:ring-2 focus:ring-blue-500"
            />
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-300 mb-1">
              Device Type *
            </label>
            <select
              value={form.deviceType}
              onChange={(e) => handleChange('deviceType', e.target.value)}
              required
              disabled={loading}
              className="w-full px-4 py-3 bg-gray-700 border border-gray-600 rounded-lg text-white focus:outline-none focus:ring-2 focus:ring-blue-500"
            >
              {deviceTypes.map((dt) => (
                <option key={dt} value={dt}>
                  {dt.replace(/_/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase())}
                </option>
              ))}
            </select>
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-300 mb-1">
              Operating System
            </label>
            <select
              value={form.deviceOs}
              onChange={(e) => handleChange('deviceOs', e.target.value)}
              disabled={loading}
              className="w-full px-4 py-3 bg-gray-700 border border-gray-600 rounded-lg text-white focus:outline-none focus:ring-2 focus:ring-blue-500"
            >
              <option value="">Auto-detect</option>
              {osOptions.map((os) => (
                <option key={os} value={os}>
                  {os}
                </option>
              ))}
            </select>
          </div>

          <button
            type="submit"
            disabled={loading || !form.intentId || !form.claimToken}
            className="w-full py-3 bg-blue-600 hover:bg-blue-700 disabled:bg-gray-600 disabled:cursor-not-allowed rounded-lg font-semibold transition-colors"
          >
            {loading ? 'Claiming...' : 'Claim Device'}
          </button>
        </form>

        <div className="mt-6 text-center">
          <button
            onClick={handleBackToSetup}
            disabled={loading}
            className="text-gray-400 hover:text-white text-sm underline disabled:opacity-50"
          >
            Back to setup options
          </button>
        </div>
      </div>
    </div>
  );
}
