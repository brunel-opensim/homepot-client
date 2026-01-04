import React, { useState, useEffect } from 'react';
import { useNavigate, useParams, useLocation } from 'react-router-dom';
import { ArrowLeft, Loader2 } from 'lucide-react';
import api from '@/services/api';
import { Button } from '@/components/ui/button';
import { Card } from '@/components/ui/card';
import { Toast } from '@/components/ui/Toast';

export default function DeviceSettings() {
  const { id } = useParams();
  const navigate = useNavigate();
  const location = useLocation();

  const [formData, setFormData] = useState({
    name: '',
    device_id: '',
    device_type: '',
    site_id: '',
    ip_address: '',
    mac_address: '',
    firmware_version: '',
  });

  const [sites, setSites] = useState([]);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState(null);
  const [toast, setToast] = useState(null);

  useEffect(() => {
    const fetchData = async () => {
      try {
        // Fetch device details and sites list in parallel
        const [deviceData, sitesResponse] = await Promise.all([
          api.devices.getDeviceById(id),
          api.sites.list(),
        ]);

        setFormData({
          name: deviceData.name || '',
          device_id: deviceData.device_id || '',
          device_type: deviceData.device_type || 'pos_terminal',
          site_id: deviceData.site_id || '',
          ip_address: deviceData.ip_address || '',
          mac_address: deviceData.mac_address || '',
          firmware_version: deviceData.firmware_version || '',
        });

        setSites(sitesResponse.sites || []);
      } catch (err) {
        console.error('Failed to load data:', err);
        setError('Failed to load device details.');
      } finally {
        setLoading(false);
      }
    };

    fetchData();
  }, [id]);

  const handleChange = (e) => {
    const { name, value } = e.target;
    setFormData((prev) => ({ ...prev, [name]: value }));
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setSaving(true);
    setError(null);

    try {
      await api.devices.update(id, formData);
      setToast({
        title: 'Success',
        message: 'Device updated successfully',
        type: 'success',
      });
    } catch (err) {
      console.error('Failed to update device:', err);
      setToast({
        title: 'Error',
        message: 'Failed to update device',
        type: 'error',
      });
    } finally {
      setSaving(false);
    }
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
      <div className="container mx-auto max-w-2xl">
        <Button
          variant="ghost"
          onClick={() => navigate(-1)}
          className="mb-4 pl-0 hover:pl-1 transition-all text-gray-400 hover:text-white hover:bg-transparent"
        >
          <ArrowLeft className="h-4 w-4 mr-2" />
          {location.state?.from === 'site' ? 'Back to Site' : 'Back'}
        </Button>

        <div className="mb-6">
          <h1 className="text-2xl font-bold tracking-tight text-white">Device Settings</h1>
          <p className="text-gray-400">Update device configuration and details.</p>
        </div>

        {error && (
          <div className="bg-red-500/10 border border-red-500/20 text-red-400 px-4 py-3 rounded-md mb-6 text-sm">
            {error}
          </div>
        )}

        <Card className="p-6 bg-card border-border">
          <form onSubmit={handleSubmit} className="space-y-6">
            {/* Site Selection - Read Only */}
            <div className="space-y-2">
              <label htmlFor="site_id" className="text-sm font-medium leading-none text-gray-300">
                Assigned Site
              </label>
              <select
                id="site_id"
                name="site_id"
                disabled
                className="flex h-10 w-full rounded-md border border-border bg-background/50 px-3 py-2 text-sm text-gray-500 shadow-sm transition-colors focus-visible:outline-none disabled:cursor-not-allowed"
                value={formData.site_id}
                onChange={handleChange}
              >
                <option value="" disabled>
                  Select a site
                </option>
                {sites.map((site) => (
                  <option key={site.id} value={site.site_id}>
                    {site.name} ({site.site_id})
                  </option>
                ))}
              </select>
            </div>

            {/* Device Basic Info */}
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div className="space-y-2">
                <label htmlFor="name" className="text-sm font-medium leading-none text-gray-300">
                  Device Name <span className="text-red-400">*</span>
                </label>
                <input
                  id="name"
                  name="name"
                  type="text"
                  required
                  className="flex h-10 w-full rounded-md border border-border bg-background px-3 py-2 text-sm text-foreground shadow-sm transition-colors file:border-0 file:bg-transparent file:text-sm file:font-medium placeholder:text-muted-foreground focus-visible:outline-none focus-visible:border-primary disabled:cursor-not-allowed disabled:opacity-50"
                  placeholder="e.g. Front Desk POS"
                  value={formData.name}
                  onChange={handleChange}
                />
              </div>

              <div className="space-y-2">
                <label
                  htmlFor="device_id"
                  className="text-sm font-medium leading-none text-gray-300"
                >
                  Device ID
                </label>
                <input
                  id="device_id"
                  name="device_id"
                  type="text"
                  disabled
                  className="flex h-10 w-full rounded-md border border-border bg-background/50 px-3 py-2 text-sm text-gray-500 shadow-sm transition-colors file:border-0 file:bg-transparent file:text-sm file:font-medium placeholder:text-muted-foreground focus-visible:outline-none disabled:cursor-not-allowed"
                  value={formData.device_id}
                  onChange={handleChange}
                />
              </div>
            </div>

            <div className="space-y-2">
              <label
                htmlFor="device_type"
                className="text-sm font-medium leading-none text-gray-300"
              >
                Device Type <span className="text-red-400">*</span>
              </label>
              <select
                id="device_type"
                name="device_type"
                required
                className="flex h-10 w-full rounded-md border border-border bg-background px-3 py-2 text-sm text-foreground shadow-sm transition-colors focus-visible:outline-none focus-visible:border-primary disabled:cursor-not-allowed disabled:opacity-50"
                value={formData.device_type}
                onChange={handleChange}
              >
                <option value="pos_terminal">POS Terminal</option>
                <option value="iot_sensor">IoT Sensor</option>
                <option value="industrial_controller">Industrial Controller</option>
                <option value="gateway">Gateway</option>
                <option value="unknown">Other</option>
              </select>
            </div>

            {/* Optional Details */}
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div className="space-y-2">
                <label
                  htmlFor="ip_address"
                  className="text-sm font-medium leading-none text-gray-300"
                >
                  IP Address
                </label>
                <input
                  id="ip_address"
                  name="ip_address"
                  type="text"
                  className="flex h-10 w-full rounded-md border border-border bg-background px-3 py-2 text-sm text-foreground shadow-sm transition-colors file:border-0 file:bg-transparent file:text-sm file:font-medium placeholder:text-muted-foreground focus-visible:outline-none focus-visible:border-primary disabled:cursor-not-allowed disabled:opacity-50"
                  placeholder="e.g. 192.168.1.100"
                  value={formData.ip_address}
                  onChange={handleChange}
                />
              </div>
              <div className="space-y-2">
                <label
                  htmlFor="mac_address"
                  className="text-sm font-medium leading-none text-gray-300"
                >
                  MAC Address
                </label>
                <input
                  id="mac_address"
                  name="mac_address"
                  type="text"
                  className="flex h-10 w-full rounded-md border border-border bg-background px-3 py-2 text-sm text-foreground shadow-sm transition-colors file:border-0 file:bg-transparent file:text-sm file:font-medium placeholder:text-muted-foreground focus-visible:outline-none focus-visible:border-primary disabled:cursor-not-allowed disabled:opacity-50"
                  placeholder="e.g. 00:1A:2B:3C:4D:5E"
                  value={formData.mac_address}
                  onChange={handleChange}
                />
              </div>
            </div>

            <div className="space-y-2">
              <label
                htmlFor="firmware_version"
                className="text-sm font-medium leading-none text-gray-300"
              >
                Firmware Version
              </label>
              <input
                id="firmware_version"
                name="firmware_version"
                type="text"
                className="flex h-10 w-full rounded-md border border-border bg-background px-3 py-2 text-sm text-foreground shadow-sm transition-colors file:border-0 file:bg-transparent file:text-sm file:font-medium placeholder:text-muted-foreground focus-visible:outline-none focus-visible:border-primary disabled:cursor-not-allowed disabled:opacity-50"
                placeholder="e.g. v1.2.3"
                value={formData.firmware_version}
                onChange={handleChange}
              />
            </div>

            <div className="flex justify-end gap-4 pt-4">
              <Button
                type="button"
                variant="outline"
                onClick={() => navigate(-1)}
                className="border-[#1f2735] bg-transparent text-gray-300 hover:bg-[#1f2735] hover:text-white"
              >
                Cancel
              </Button>
              <Button
                type="submit"
                disabled={saving}
                className="bg-teal-600 hover:bg-teal-700 text-white"
              >
                {saving && <Loader2 className="h-4 w-4 mr-2 animate-spin" />}
                Update Device
              </Button>
            </div>
          </form>
        </Card>
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
