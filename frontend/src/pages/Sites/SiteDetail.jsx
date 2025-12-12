import React, { useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import {
  ArrowLeft,
  MapPin,
  Server,
  Activity,
  Loader2,
  Edit,
  Trash2,
  Plus,
  Briefcase,
} from 'lucide-react';
import api from '@/services/api';
import { Button } from '@/components/ui/button';
import { Card } from '@/components/ui/card';
import SiteDeleteDialog from '@/components/Sites/SiteDeleteDialog';
import DeviceAddDialog from '@/components/Devices/DeviceAddDialog';

export default function SiteDetail() {
  const { id } = useParams();
  const navigate = useNavigate();
  const [site, setSite] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [deleteDialogOpen, setDeleteDialogOpen] = useState(false);
  const [addDeviceOpen, setAddDeviceOpen] = useState(false);
  const [isDeleting, setIsDeleting] = useState(false);
  const [isAddingDevice, setIsAddingDevice] = useState(false);
  const [devices, setDevices] = useState([]);

  console.log('devices', devices);

  useEffect(() => {
    const fetchSiteAndDevices = async () => {
      console.log('fetchSiteAndDevices called with id:', id);
      if (!id) {
        console.error('No ID provided to fetch');
        return;
      }

      setLoading(true);

      try {
        // Fetch Site
        const siteData = await api.sites.get(id);
        setSite(siteData);
      } catch (err) {
        console.error('Failed to load site:', err);
        setError('Failed to load site details.');
        setLoading(false);
        return;
      }

      try {
        // Fetch Devices
        const devicesData = await api.devices.getSiteId(id);
        const devicesList = Array.isArray(devicesData) ? devicesData : devicesData.devices || [];

        setDevices(devicesList);
      } catch (err) {
        console.error('Failed to load devices:', err);
      } finally {
        setLoading(false);
      }
    };

    fetchSiteAndDevices();
  }, [id]);

  const handleDelete = async () => {
    try {
      setIsDeleting(true);
      await api.sites.delete(id);
      navigate('/sites');
    } catch (err) {
      console.error('Failed to delete site:', err);
      alert('Failed to delete site');
    } finally {
      setIsDeleting(false);
    }
  };

  const handleAddDevice = async (deviceData) => {
    try {
      setIsAddingDevice(true);
      await api.devices.create(id, deviceData);

      // Refresh devices
      const devicesData = await api.devices.getSiteId(id);
      const devicesList = Array.isArray(devicesData) ? devicesData : devicesData.devices || [];
      setDevices(devicesList);

      setAddDeviceOpen(false);
    } catch (err) {
      console.error('Failed to add device:', err);
      throw new Error(api.apiHelpers?.formatError(err) || 'Failed to add device');
    } finally {
      setIsAddingDevice(false);
    }
  };

  // ====== New Function for Creating Job ======
  const handleCreateJob = async () => {
    try {
      const defaultJob = {
        name: `Job for ${site.name}`,
        description: 'Automatically created job',
      };
      console.log('id', id);

      await api.jobs.create(id, defaultJob);
      // toast({
      //   title: 'Job Created',
      //   description: `Job created successfully for site ${site.name}`,
      //   variant: 'success',
      // });
    } catch (err) {
      console.error('Failed to create job:', err);
      const message = err.response?.data?.detail || err.message || 'Failed to create job';
      // TODO: Add toast notification
      alert(`Error: ${message}`);
    }
  };

  if (loading) {
    return (
      <div className="flex justify-center items-center h-64">
        <Loader2 className="h-8 w-8 animate-spin text-primary" />
      </div>
    );
  }

  if (error || !site) {
    return (
      <div className="container mx-auto py-12 px-4 text-center">
        <h2 className="text-lg font-semibold text-destructive mb-2">Error</h2>
        <p className="text-muted-foreground mb-4">{error || 'Site not found'}</p>
        <Button onClick={() => navigate('/sites')}>Back to Sites</Button>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-background text-foreground py-6 px-4">
      <div className="container mx-auto max-w-7xl">
        <Button
          variant="ghost"
          onClick={() => navigate('/sites')}
          className="mb-4 pl-0 hover:pl-1 transition-all text-gray-400 hover:text-white hover:bg-transparent"
        >
          <ArrowLeft className="h-4 w-4 mr-2" />
          Back to Sites
        </Button>

        <div className="flex flex-col md:flex-row justify-between items-start md:items-center mb-8 gap-4">
          <div>
            <h1 className="text-3xl font-bold tracking-tight mb-2 text-white">{site.name}</h1>
            <div className="flex items-center text-gray-400">
              <MapPin className="h-4 w-4 mr-1.5" />
              {site.location || 'No location specified'}
            </div>
          </div>
          <div className="flex gap-2">
            <Button
              onClick={() => setAddDeviceOpen(true)}
              className="bg-transparent text-teal-400 border border-teal-400 hover:bg-teal-400/10"
            >
              <Plus className="h-4 w-4 mr-2" />
              Add Device
            </Button>

            {/* Create Job */}
            <Button
              onClick={handleCreateJob}
              className="bg-transparent text-blue-400 border border-blue-400 hover:bg-blue-400/10"
            >
              <Briefcase className="h-4 w-4 mr-2" />
              Create Job
            </Button>

            <Button
              variant="outline"
              onClick={() => navigate(`/sites/${id}/edit`)}
              className="border-[#1f2735] bg-transparent text-gray-300 hover:bg-[#1f2735] hover:text-white"
            >
              <Edit className="h-4 w-4 mr-2" />
              Edit Site
            </Button>
            <Button
              variant="destructive"
              onClick={() => setDeleteDialogOpen(true)}
              className="bg-transparent text-red-500 border border-red-500 hover:bg-red-500/10"
            >
              <Trash2 className="h-4 w-4 mr-2" />
              Delete
            </Button>
          </div>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-6 mb-8">
          <Card className="p-6 bg-card border-border">
            <div className="flex items-center gap-4">
              <div className="p-3 bg-teal-500/10 rounded-full">
                <Server className="h-6 w-6 text-teal-500" />
              </div>
              <div>
                <p className="text-sm text-gray-400 font-medium">Total Devices</p>
                <h3 className="text-2xl font-bold text-white">
                  {site.devices_count || devices.length || 0}
                </h3>
              </div>
            </div>
          </Card>

          <Card className="p-6 bg-card border-border">
            <div className="flex items-center gap-4">
              <div className="p-3 bg-green-500/10 rounded-full">
                <Activity className="h-6 w-6 text-green-500" />
              </div>
              <div>
                <p className="text-sm text-gray-400 font-medium">Status</p>
                <h3 className="text-2xl font-bold text-green-500">Active</h3>
              </div>
            </div>
          </Card>
        </div>

        <div className="mb-8">
          <h2 className="text-xl font-semibold mb-4 text-white">Description</h2>
          <Card className="p-6 bg-card border-border">
            <p className="text-gray-300">
              {site.description || 'No description provided for this site.'}
            </p>
          </Card>
        </div>

        <div>
          <h2 className="text-xl font-semibold mb-4 text-white">Associated Devices</h2>
          {devices.length > 0 ? (
            <div className="rounded-md border border-border bg-card">
              <div className="relative w-full overflow-auto">
                <table className="w-full caption-bottom text-sm text-left">
                  <thead className="[&_tr]:border-b border-border">
                    <tr className="border-b border-border transition-colors hover:bg-muted/50">
                      <th className="h-12 px-4 align-middle font-medium text-gray-400">Name</th>
                      <th className="h-12 px-4 align-middle font-medium text-gray-400">Type</th>
                      <th className="h-12 px-4 align-middle font-medium text-gray-400">Status</th>
                      <th className="h-12 px-4 align-middle font-medium text-gray-400">
                        Last Seen
                      </th>
                    </tr>
                  </thead>
                  <tbody className="[&_tr:last-child]:border-0">
                    {devices.map((device) => (
                      <tr
                        key={device.id}
                        className="border-b border-border transition-colors hover:bg-muted/50"
                      >
                        <td
                          className="p-4 align-middle font-medium text-white cursor-pointer hover:underline"
                          // onClick={() => navigate(`/device/${device.device_id}`)}
                          onClick={() => navigate(`/device/${device.id || device.device_id}`)}
                        >
                          {device.name}
                        </td>
                        <td className="p-4 align-middle text-gray-300">
                          {device.type || 'Unknown'}
                        </td>
                        <td className="p-4 align-middle">
                          <span
                            className={`inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium ${
                              device.status === 'online'
                                ? 'bg-green-500/10 text-green-500'
                                : 'bg-red-500/10 text-red-500'
                            }`}
                          >
                            {device.status || 'Offline'}
                          </span>
                        </td>
                        <td className="p-4 align-middle text-gray-300">
                          {device.last_seen ? new Date(device.last_seen).toLocaleString() : 'Never'}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          ) : (
            <Card className="p-8 text-center text-gray-400 border-dashed border-border bg-card">
              <Server className="h-8 w-8 mx-auto mb-3 opacity-50" />
              <p>No devices found for this site.</p>
            </Card>
          )}
        </div>

        <SiteDeleteDialog
          isOpen={deleteDialogOpen}
          onClose={() => setDeleteDialogOpen(false)}
          onConfirm={handleDelete}
          siteName={site.name}
          isDeleting={isDeleting}
        />

        <DeviceAddDialog
          isOpen={addDeviceOpen}
          onClose={() => setAddDeviceOpen(false)}
          onAdd={handleAddDevice}
          isAdding={isAddingDevice}
        />
      </div>
    </div>
  );
}
