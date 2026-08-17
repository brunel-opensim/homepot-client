import React, { useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import {
  ArrowLeft,
  MapPin,
  Server,
  Activity,
  Loader2,
  Trash2,
  Edit,
  PlusCircle,
  LayoutDashboard,
  AlertTriangle,
  CheckCircle,
  KeyRound,
  RotateCcw,
  Archive,
} from 'lucide-react';
import api from '@/services/api';
import OsIcon from '@/components/common/OsIcon';
import { Button } from '@/components/ui/button';
import { Card } from '@/components/ui/card';
import DataTable from '@/components/ui/DataTable';
import DeviceDeleteDialog from '@/components/Devices/DeviceDeleteDialog';
import BootstrapKeyDialog from '@/components/Sites/BootstrapKeyDialog';

// Health buckets mirror the backend HealthState enum (healthy/warning/error/
// maintenance/unknown). Clickable dots filter the Associated Devices table.
const HEALTH_BUCKETS = [
  { key: 'healthy', label: 'Healthy', dotClass: 'text-green-400', ringClass: 'ring-green-500/40' },
  {
    key: 'warning',
    label: 'Warning',
    dotClass: 'text-yellow-400',
    ringClass: 'ring-yellow-500/40',
  },
  { key: 'error', label: 'Error', dotClass: 'text-red-400', ringClass: 'ring-red-500/40' },
  { key: 'maintenance', label: 'Maint.', dotClass: 'text-blue-400', ringClass: 'ring-blue-500/40' },
  { key: 'unknown', label: 'Unknown', dotClass: 'text-gray-400', ringClass: 'ring-gray-500/40' },
];

export default function SiteDetail() {
  const { id } = useParams();
  const navigate = useNavigate();
  const [site, setSite] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [devices, setDevices] = useState([]);
  const [stats, setStats] = useState(null);
  const [healthFilter, setHealthFilter] = useState('');

  // Device deletion state
  const [deviceToDelete, setDeviceToDelete] = useState(null);
  const [isDeletingDevice, setIsDeletingDevice] = useState(false);
  const [isRestoringDevice, setIsRestoringDevice] = useState(false);
  const [isRestoringSite, setIsRestoringSite] = useState(false);

  // Bootstrap key dialog state
  const [isBootstrapKeyOpen, setIsBootstrapKeyOpen] = useState(false);

  const isArchived = site ? site.is_active === false : false;

  useEffect(() => {
    const fetchSiteAndDevices = async () => {
      if (!id || id === 'undefined' || id === 'null') {
        console.error('Invalid ID:', id);
        // If we somehow got here with an invalid ID, go back to list
        navigate('/sites', { replace: true });
        return;
      }

      setLoading(true);

      let siteData = null;
      try {
        // Fetch Site
        siteData = await api.sites.get(id);
        setSite(siteData);
      } catch (err) {
        console.error('Failed to load site:', err);
        setError('Failed to load site details.');
        setLoading(false);
        return;
      }

      try {
        // Fetch Devices (include unpaired/suspended for archived sites)
        const devicesData = await api.devices.getSiteId(id, {
          includeUnpaired: siteData.is_active === false,
        });
        const devicesList = Array.isArray(devicesData) ? devicesData : devicesData.devices || [];

        // Sort alphabetically by name
        devicesList.sort((a, b) => (a.name || '').localeCompare(b.name || ''));

        setDevices(devicesList);

        try {
          const statsData = await api.sites.getDashboard(id);
          setStats(statsData);
        } catch (err) {
          console.error('Failed to load dashboard stats:', err);
        }
      } catch (err) {
        console.error('Failed to load devices:', err);
      } finally {
        setLoading(false);
      }
    };

    fetchSiteAndDevices();
  }, [id, navigate]);

  const handleToggleMonitor = async () => {
    try {
      const updatedSite = await api.sites.toggleMonitor(id, !site.is_monitored);
      setSite((prev) => ({ ...prev, is_monitored: updatedSite.is_monitored }));
    } catch (err) {
      console.error('Failed to toggle monitor:', err);
    }
  };

  const handleRestoreSite = async () => {
    try {
      setIsRestoringSite(true);
      await api.sites.restore(id);
      // Re-fetch site + devices in active mode
      const siteData = await api.sites.get(id);
      setSite(siteData);
      const devicesData = await api.devices.getSiteId(id);
      const devicesList = Array.isArray(devicesData) ? devicesData : devicesData.devices || [];
      devicesList.sort((a, b) => (a.name || '').localeCompare(b.name || ''));
      setDevices(devicesList);
    } catch (err) {
      console.error('Failed to restore site:', err);
      alert(`Failed to restore site: ${err.response?.data?.detail || err.message}`);
    } finally {
      setIsRestoringSite(false);
    }
  };

  const handleRestoreDevice = async (device) => {
    const deviceId = device.device_id || device.id;
    try {
      setIsRestoringDevice(true);
      await api.devices.resume(deviceId);
      // Remove from the archived list (it becomes active again)
      setDevices((prev) => prev.filter((d) => (d.device_id || d.id) !== deviceId));
    } catch (err) {
      console.error('Failed to restore device:', err);
      alert(`Failed to restore device: ${err.response?.data?.detail || err.message}`);
    } finally {
      setIsRestoringDevice(false);
    }
  };

  const handleDeleteDeviceClick = (device) => {
    setDeviceToDelete(device);
  };

  const handleConfirmDeleteDevice = async (mode) => {
    if (!deviceToDelete) return;

    try {
      setIsDeletingDevice(true);
      // Use device_id (string) if available, otherwise fallback to id (int) but convert to string if needed
      // The backend expects the string ID (e.g. "device-123")
      const idToDelete = deviceToDelete.device_id || deviceToDelete.id;
      await api.devices.delete(idToDelete, mode);

      // Remove from list
      setDevices((prev) => prev.filter((d) => (d.device_id || d.id) !== idToDelete));

      // Update total counts immediately
      setStats((prev) =>
        prev ? { ...prev, total_devices: Math.max(0, prev.total_devices - 1) } : null
      );
      setSite((prev) =>
        prev ? { ...prev, devices_count: Math.max(0, (prev.devices_count || 0) - 1) } : null
      );

      setDeviceToDelete(null);
    } catch (err) {
      console.error('Failed to delete device:', err);
      alert(`Failed to delete device: ${err.response?.data?.detail || err.message}`);
    } finally {
      setIsDeletingDevice(false);
    }
  };

  const filteredDevices = healthFilter
    ? devices.filter((d) => (d.health_state || 'unknown') === healthFilter)
    : devices;

  const toggleHealthFilter = (key) => {
    setHealthFilter((prev) => (prev === key ? '' : key));
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
        <Button onClick={() => navigate('/sites', { replace: true })}>Back to Sites</Button>
      </div>
    );
  }

  return (
    <div className="h-full flex flex-col overflow-hidden bg-[#0b0e13] p-2">
      <div className="container mx-auto max-w-7xl h-full flex flex-col">
        {/* Fixed Header Section */}
        <div className="shrink-0 mb-4 space-y-4">
          <Button
            variant="ghost"
            onClick={() => navigate('/sites', { replace: true })}
            className="pl-0 hover:pl-1 transition-all text-gray-400 hover:text-white hover:bg-transparent"
          >
            <ArrowLeft className="h-4 w-4 mr-2" />
            Back to Sites
          </Button>

          <div className="flex flex-col md:flex-row justify-between items-start md:items-center gap-4">
            <div>
              <h1 className="text-3xl font-bold tracking-tight mb-1 text-white">{site.name}</h1>
              <div className="flex items-center text-teal-400/80 font-mono text-sm mb-2">
                Site ID: {site.site_id || site.id}
              </div>
              <div className="flex items-center text-gray-400">
                <MapPin className="h-4 w-4 mr-1.5" />
                {site.location || 'No location specified'}
              </div>
              {isArchived && (
                <div className="flex items-center gap-1.5 mt-2 text-xs text-gray-400">
                  <Archive className="h-3.5 w-3.5" />
                  <span>
                    This site is <span className="text-gray-200">archived</span>. Its devices are
                    suspended and hidden from the Dashboard.
                  </span>
                </div>
              )}
            </div>
            <div className="flex gap-2">
              {isArchived ? (
                <Button
                  onClick={handleRestoreSite}
                  disabled={isRestoringSite}
                  className="bg-transparent border text-teal-400 border-teal-400 hover:bg-teal-400/10 disabled:opacity-50"
                >
                  <RotateCcw className="h-4 w-4 mr-2" />
                  {isRestoringSite ? 'Restoring...' : 'Restore Site'}
                </Button>
              ) : (
                <>
                  <Button
                    onClick={handleToggleMonitor}
                    className={`bg-transparent border ${
                      site.is_monitored
                        ? 'text-yellow-400 border-yellow-400 hover:bg-yellow-400/10'
                        : 'text-gray-400 border-gray-400 hover:bg-gray-400/10'
                    }`}
                  >
                    <Activity className="h-4 w-4 mr-2" />
                    {site.is_monitored ? 'Monitored' : 'Add to Dashboard'}
                  </Button>
                  <Button
                    onClick={() => navigate(`/sites/${site.site_id || site.id}/enrolment-intents`)}
                    className="bg-transparent border text-blue-400 border-blue-400 hover:bg-blue-400/10"
                  >
                    Enrolment Intents
                  </Button>
                  <Button
                    onClick={() => setIsBootstrapKeyOpen(true)}
                    className="bg-transparent border text-teal-400 border-teal-400 hover:bg-teal-400/10"
                  >
                    <KeyRound className="h-4 w-4 mr-2" />
                    Bootstrap Key
                  </Button>
                </>
              )}
              <Button
                onClick={() => navigate('/dashboard')}
                className="bg-transparent border text-gray-400 border-gray-400 hover:bg-gray-400/10"
              >
                <LayoutDashboard className="h-4 w-4 mr-2" />
                Exit
              </Button>
            </div>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
            <Card className="p-4 bg-card border-border">
              <div className="flex items-center gap-4">
                <div className="p-3 bg-teal-500/10 rounded-full">
                  <Server className="h-6 w-6 text-teal-500" />
                </div>
                <div>
                  <p className="text-sm text-gray-400 font-medium">Total Devices</p>
                  <h3 className="text-2xl font-bold text-white">
                    {stats ? stats.total_devices : site.devices_count || devices.length || 0}
                  </h3>
                  {stats && (
                    <div className="flex gap-2 text-xs text-slate-400 mt-1">
                      <span title="Online">● {stats.connectivity_counts?.online || 0} online</span>
                      <span title="Offline">
                        ○ {stats.connectivity_counts?.offline || 0} offline
                      </span>
                    </div>
                  )}
                </div>
              </div>
            </Card>

            <Card className="p-4 bg-card border-border">
              <div className="flex items-center gap-4">
                <div className="p-3 bg-green-500/10 rounded-full">
                  <Activity className="h-6 w-6 text-green-500" />
                </div>
                <div>
                  <p className="text-sm text-gray-400 font-medium">Devices by Health</p>
                  <h3 className="text-2xl font-bold text-white">
                    {stats?.health_counts
                      ? Object.values(stats.health_counts).reduce((a, b) => a + b, 0)
                      : 0}
                  </h3>
                  {stats?.health_counts && (
                    <div className="flex flex-wrap gap-2 text-xs mt-1.5">
                      {HEALTH_BUCKETS.map((bucket) => (
                        <button
                          key={bucket.key}
                          type="button"
                          title={`Filter to ${bucket.label} devices`}
                          onClick={() => toggleHealthFilter(bucket.key)}
                          className={`flex items-center gap-1.5 rounded-full px-2 py-0.5 text-slate-300 transition-all ring-1 ring-transparent focus:outline-none ${
                            healthFilter === bucket.key
                              ? `${bucket.ringClass} bg-white/5`
                              : 'hover:bg-white/5'
                          }`}
                        >
                          <span className={`${bucket.dotClass} font-bold`}>●</span>
                          <span>{stats.health_counts[bucket.key] || 0}</span>
                        </button>
                      ))}
                      {healthFilter && (
                        <button
                          type="button"
                          title="Clear health filter"
                          onClick={() => setHealthFilter('')}
                          className="text-gray-500 hover:text-white transition-colors"
                        >
                          ✕ Clear
                        </button>
                      )}
                    </div>
                  )}
                </div>
              </div>
            </Card>

            <Card className="p-4 bg-card border-border md:col-span-1 col-span-1">
              <h2 className="text-sm font-semibold mb-1 text-gray-400">Description</h2>
              <p className="text-gray-300 text-sm line-clamp-2">
                {site.description || 'No description provided for this site.'}
              </p>
            </Card>
          </div>
        </div>

        {/* Scrollable Devices Section */}
        <div className="flex-1 min-h-0 flex flex-col">
          <div className="shrink-0 flex items-center justify-between mb-4">
            <h2 className="text-xl font-semibold text-white">
              {isArchived ? 'Suspended Devices' : 'Associated Devices'}
            </h2>
            {isArchived && (
              <span className="text-sm text-gray-400">
                Suspended by the site archive. Restore to re-activate.
              </span>
            )}
            {!isArchived && healthFilter && (
              <span className="text-sm text-gray-400">
                Showing <span className="text-teal-400">{filteredDevices.length}</span>{' '}
                {healthFilter} device{filteredDevices.length === 1 ? '' : 's'}
              </span>
            )}
          </div>
          {devices.length > 0 ? (
            <DataTable
              columns={[
                { key: 'name', label: 'Name' },
                { key: 'type', label: 'Type' },
                { key: 'status', label: 'Status' },
                { key: 'enrollment', label: 'Enrollment' },
                { key: 'alerts', label: 'Alerts' },
                { key: 'last_seen', label: 'Last Seen' },
                { key: 'actions', label: 'Actions', align: 'right' },
              ]}
            >
              {filteredDevices.map((device) => (
                <tr
                  key={device.id}
                  className="border-b border-border transition-colors hover:bg-muted/50"
                >
                  <td
                    className="p-4 align-middle font-medium text-white cursor-pointer hover:underline"
                    onClick={() =>
                      navigate(`/device/${device.device_id || device.id}`, {
                        state: { from: 'site', siteId: id },
                      })
                    }
                  >
                    {device.name}
                  </td>
                  <td className="p-4 align-middle text-gray-300">
                    <div className="uppercase">
                      {device.device_type?.replace(/_/g, ' ') || 'Unknown'}
                    </div>
                    {device.os_details && device.os_family && (
                      <div className="flex items-center gap-1.5 text-xs text-gray-400 normal-case mt-0.5">
                        <OsIcon type={device.os_family} size="w-3.5 h-3.5" />
                        <span>{device.os_details}</span>
                      </div>
                    )}
                  </td>
                  <td className="p-4 align-middle">
                    <div className="flex items-center gap-2">
                      <span
                        className={`inline-flex items-center gap-1.5 rounded-full px-2.5 py-0.5 text-xs font-medium ${
                          device.lifecycle_state === 'active'
                            ? 'bg-green-500/10 text-green-500'
                            : device.lifecycle_state === 'suspended'
                              ? 'bg-orange-500/10 text-orange-500'
                              : device.lifecycle_state === 'unpaired'
                                ? 'bg-gray-500/10 text-gray-500'
                                : 'bg-yellow-500/10 text-yellow-500'
                        }`}
                      >
                        <span
                          className={`w-1.5 h-1.5 rounded-full ${
                            device.connectivity_state === 'online'
                              ? 'bg-green-500'
                              : device.connectivity_state === 'offline'
                                ? 'bg-gray-500'
                                : 'bg-yellow-500'
                          }`}
                        />
                        {device.lifecycle_state || 'Unknown'}
                      </span>
                      {device.enrollment_method === 'emulated' ||
                      device.device_source === 'emulator' ? (
                        <span className="inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-[10px] font-medium bg-cyan-500/10 text-cyan-400 border border-cyan-500/20">
                          EMU
                        </span>
                      ) : device.is_simulated ? (
                        <span className="inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-[10px] font-medium bg-purple-500/10 text-purple-400 border border-purple-500/20">
                          SIM
                        </span>
                      ) : null}
                      <span
                        className={`inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-[10px] font-medium ${
                          device.health_state === 'healthy'
                            ? 'bg-green-500/10 text-green-400'
                            : device.health_state === 'warning'
                              ? 'bg-yellow-500/10 text-yellow-400'
                              : device.health_state === 'error'
                                ? 'bg-red-500/10 text-red-400'
                                : device.health_state === 'maintenance'
                                  ? 'bg-blue-500/10 text-blue-400'
                                  : 'bg-gray-500/10 text-gray-400'
                        }`}
                      >
                        {device.health_state || 'unknown'}
                      </span>
                    </div>
                  </td>
                  <td className="p-4 align-middle">
                    <span
                      className={`inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium ${
                        device.enrollment_method === 'self-enrolled'
                          ? 'bg-purple-500/10 text-purple-400'
                          : 'bg-blue-500/10 text-blue-400'
                      }`}
                    >
                      {device.enrollment_method === 'self-enrolled'
                        ? 'Self-Enrolled'
                        : 'Pre-Provisioned'}
                    </span>
                  </td>
                  <td className="p-4 align-middle">
                    {device.active_alerts > 0 ? (
                      <div className="flex items-center text-orange-400 font-medium bg-orange-500/10 px-2 py-1 rounded w-fit">
                        <AlertTriangle className="h-3.5 w-3.5 mr-1.5" />
                        {device.active_alerts}
                      </div>
                    ) : (
                      <div className="flex items-center text-emerald-500 font-medium bg-emerald-500/10 px-2 py-1 rounded w-fit">
                        <CheckCircle className="h-3.5 w-3.5 mr-1.5" />0
                      </div>
                    )}
                  </td>
                  <td className="p-4 align-middle">
                    <div className="flex flex-col">
                      <span className="text-gray-300">
                        {device.last_seen ? new Date(device.last_seen).toLocaleString() : 'Never'}
                      </span>
                      {device.last_heartbeat_at && (
                        <span className="text-[10px] text-gray-500 font-mono">
                          HB: {new Date(device.last_heartbeat_at).toLocaleString()}
                        </span>
                      )}
                    </div>
                  </td>
                  <td className="p-4 align-middle text-right">
                    {isArchived ? (
                      <div className="flex justify-end gap-2">
                        <Button
                          variant="ghost"
                          size="icon"
                          onClick={(e) => {
                            e.stopPropagation();
                            handleRestoreDevice(device);
                          }}
                          disabled={isRestoringDevice}
                          title="Restore device"
                          className="h-8 w-8 text-gray-400 hover:text-teal-400 hover:bg-teal-400/10"
                        >
                          <RotateCcw className="h-4 w-4" />
                        </Button>
                      </div>
                    ) : (
                      <div className="flex justify-end gap-2">
                        <Button
                          variant="ghost"
                          size="icon"
                          onClick={(e) => {
                            e.stopPropagation();
                            navigate(`/device/${device.device_id || device.id}/settings`, {
                              state: {
                                mode: 'edit',
                                from: 'site',
                              },
                            });
                          }}
                          className="h-8 w-8 text-gray-400 hover:text-blue-400 hover:bg-blue-400/10"
                        >
                          <Edit className="h-4 w-4" />
                        </Button>
                        <Button
                          variant="ghost"
                          size="icon"
                          onClick={(e) => {
                            e.stopPropagation();
                            handleDeleteDeviceClick(device);
                          }}
                          className="h-8 w-8 text-gray-400 hover:text-red-500 hover:bg-red-500/10"
                        >
                          <Trash2 className="h-4 w-4" />
                        </Button>
                      </div>
                    )}
                  </td>
                </tr>
              ))}
            </DataTable>
          ) : (
            <Card className="p-8 text-center text-gray-400 border-dashed border-border bg-card">
              <Server className="h-8 w-8 mx-auto mb-3 opacity-50" />
              <p>
                {healthFilter
                  ? `No ${healthFilter} devices found for this site.`
                  : 'No devices found for this site.'}
              </p>
            </Card>
          )}
        </div>

        <DeviceDeleteDialog
          isOpen={!!deviceToDelete}
          onClose={() => setDeviceToDelete(null)}
          onConfirm={handleConfirmDeleteDevice}
          deviceName={deviceToDelete?.name}
          isDeleting={isDeletingDevice}
        />

        <BootstrapKeyDialog
          isOpen={isBootstrapKeyOpen}
          onClose={() => setIsBootstrapKeyOpen(false)}
          siteId={site.site_id || site.id}
          siteName={site.name}
        />
      </div>
    </div>
  );
}
