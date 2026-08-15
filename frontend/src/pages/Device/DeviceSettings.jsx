import React, { useState, useEffect } from 'react';
import { useNavigate, useParams, useLocation } from 'react-router-dom';
import { ArrowLeft, Loader2 } from 'lucide-react';
import api from '@/services/api';
import { Button } from '@/components/ui/button';
import { Card } from '@/components/ui/card';
import { Toast } from '@/components/ui/Toast';
import DeviceFormFields from '@/components/Devices/DeviceFormFields';
import useFormData from '@/hooks/useFormData';

export default function DeviceSettings() {
  const { id } = useParams();
  const navigate = useNavigate();
  const location = useLocation();

  const [formData, setFormData, handleChange] = useFormData({
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
  }, [id, setFormData]);

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
            <DeviceFormFields
              formData={formData}
              handleChange={handleChange}
              sites={sites}
              readOnly
            />

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
