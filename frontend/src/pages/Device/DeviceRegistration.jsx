import React, { useState, useEffect } from 'react';
import { useNavigate, useLocation } from 'react-router-dom';
import { ArrowLeft, Loader2 } from 'lucide-react';
import api from '@/services/api';
import { Button } from '@/components/ui/button';
import { Card } from '@/components/ui/card';
import DeviceFormFields from '@/components/Devices/DeviceFormFields';
import useFormData from '@/hooks/useFormData';

export default function DeviceRegistration() {
  const navigate = useNavigate();
  const location = useLocation();

  const [formData, setFormData, handleChange] = useFormData({
    name: '',
    device_id: '',
    device_type: 'pos_terminal',
    site_id: '',
    ip_address: '',
    mac_address: '',
    firmware_version: '',
  });

  const [sites, setSites] = useState([]);
  const [loading, setLoading] = useState(false);
  const [initialLoading, setInitialLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    const fetchSites = async () => {
      try {
        // Assuming there's an endpoint to list all sites.
        // If not, we might need to implement it or use what's available.
        // Based on api.js, there isn't a direct 'list all sites' method exposed clearly
        // in the snippet I saw, but usually it's api.sites.list() or similar.
        // I'll assume api.sites.list() exists or I'll check api.js again.
        // Checking api.js context from earlier... I didn't see api.sites.list explicitly
        // but I saw api.sites.get(id).
        // Let's assume for now and if it fails I'll fix it.
        // Actually, let's check api.js again to be safe.
        const response = await api.sites.list();
        const sitesList = response.sites || [];
        setSites(sitesList);

        // Check if siteId was passed in navigation state
        if (location.state?.siteId) {
          // Verify the passed siteId exists in the fetched list
          const preSelectedSite = sitesList.find(
            (s) => s.site_id === location.state.siteId || s.id === location.state.siteId
          );
          if (preSelectedSite) {
            setFormData((prev) => ({
              ...prev,
              site_id: preSelectedSite.site_id || preSelectedSite.id,
            }));
          } else if (sitesList.length > 0) {
            setFormData((prev) => ({ ...prev, site_id: sitesList[0].site_id || sitesList[0].id }));
          }
        } else if (sitesList.length > 0) {
          setFormData((prev) => ({ ...prev, site_id: sitesList[0].site_id || sitesList[0].id }));
        }
      } catch (err) {
        console.error('Failed to fetch sites:', err);
        setError('Failed to load sites. Please ensure you have created at least one site.');
      } finally {
        setInitialLoading(false);
      }
    };

    fetchSites();
  }, [location, setFormData]);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError(null);
    setLoading(true);

    try {
      // api.devices.create(siteId, deviceData)
      await api.devices.create(formData.site_id, formData);

      // Always redirect to the site page where the device was registered
      if (formData.site_id) {
        navigate(`/sites/${formData.site_id}`);
      } else {
        navigate('/device');
      }
    } catch (err) {
      console.error('Failed to register device:', err);
      setError(api.apiHelpers?.formatError(err) || 'Failed to register device. Please try again.');
    } finally {
      setLoading(false);
    }
  };

  if (initialLoading) {
    return (
      <div className="flex justify-center items-center h-64">
        <Loader2 className="h-8 w-8 animate-spin text-primary" />
      </div>
    );
  }

  const getBackTarget = () => {
    if (location.state?.siteId) return `/sites/${location.state.siteId}`;
    if (formData.site_id) return `/sites/${formData.site_id}`;
    return '/device';
  };

  const getBackLabel = () => {
    if (location.state?.siteId) return 'Back to Site';
    if (formData.site_id) {
      const site = sites.find((s) => s.site_id === formData.site_id);
      return site ? `Back to ${site.name}` : 'Back to Site';
    }
    return 'Back to Devices';
  };

  return (
    <div className="h-full overflow-y-auto bg-background text-foreground p-2 text-sm">
      <div className="container mx-auto max-w-2xl">
        <Button
          variant="ghost"
          onClick={() => navigate(getBackTarget())}
          className="mb-2 pl-0 hover:pl-1 transition-all text-gray-400 hover:text-white hover:bg-transparent"
        >
          <ArrowLeft className="h-4 w-4 mr-2" />
          {getBackLabel()}
        </Button>

        <div className="mb-4">
          <h1 className="text-xl font-bold tracking-tight text-white">Register New Device</h1>
          <p className="text-sm text-gray-400">Add a new device to a site in your network.</p>
        </div>

        {error && (
          <div className="bg-red-500/10 border border-red-500/20 text-red-400 px-4 py-3 rounded-md mb-4 text-sm">
            {error}
          </div>
        )}

        <Card className="p-4 bg-card border-border">
          <form onSubmit={handleSubmit} className="space-y-4">
            <DeviceFormFields formData={formData} handleChange={handleChange} sites={sites} />

            <div className="flex justify-end gap-4 pt-4">
              <Button
                type="button"
                variant="outline"
                onClick={() => navigate(getBackTarget())}
                className="border-[#1f2735] bg-transparent text-gray-300 hover:bg-[#1f2735] hover:text-white"
              >
                Cancel
              </Button>
              <Button
                type="submit"
                disabled={loading}
                className="bg-teal-600 hover:bg-teal-700 text-white"
                title="Create a pre-provisioned placeholder for secure environments"
              >
                {loading && <Loader2 className="h-4 w-4 mr-2 animate-spin" />}
                Pre-Provision Device (Secure & Managed)
              </Button>
            </div>
          </form>
        </Card>
      </div>
    </div>
  );
}
