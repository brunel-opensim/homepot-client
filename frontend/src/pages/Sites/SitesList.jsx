import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  AlertTriangle,
  Search,
  Edit,
  Trash2,
  ArrowLeft,
  Copy,
  Check,
  RotateCcw,
} from 'lucide-react';
import { Button } from '@/components/ui/button';
import OsIcon from '@/components/common/OsIcon';
import api from '@/services/api';
import SiteDeleteDialog from '@/components/Sites/SiteDeleteDialog';
import { trackActivity, trackSearch } from '@/utils/analytics';

export default function SitesList() {
  const navigate = useNavigate();
  const [sites, setSites] = useState([]);
  const [loading, setLoading] = useState(true);
  const [searchTerm, setSearchTerm] = useState('');
  const [locationFilter, setLocationFilter] = useState('');
  const [deleteDialogOpen, setDeleteDialogOpen] = useState(false);
  const [siteToDelete, setSiteToDelete] = useState(null);
  const [isDeleting, setIsDeleting] = useState(false);
  const [isRestoring, setIsRestoring] = useState(false);
  const [copiedSiteId, setCopiedSiteId] = useState(null);
  const [activeTab, setActiveTab] = useState('active');
  const [notice, setNotice] = useState(null);

  useEffect(() => {
    fetchSites();

    // Track PAGE VIEW
    trackActivity(
      'page_view',
      '/sites',
      {}, // extra_data
      null, // elementId
      null, // searchQuery
      0 // duration_ms (optional now)
    );
  }, []);

  const fetchSites = async (includeArchived = false) => {
    try {
      setLoading(true);
      const data = await api.sites.list({ includeArchived });
      const fetchedSites = Array.isArray(data) ? data : data.sites || [];

      // Add temporary static fields to match Site.jsx look if missing from API
      const withStaticValues = fetchedSites.map((site) => ({
        ...site,
        id: site.site_id || site.id,
        // Status is now provided by backend, fallback to Offline if missing
        status: site.status || 'Offline',
        alert: site.alert || null,
      }));

      // When viewing the Archived tab, only keep archived sites.
      const tabSites = includeArchived
        ? withStaticValues.filter((s) => s.is_active === false)
        : withStaticValues;

      // Sort alphabetically by name
      tabSites.sort((a, b) => (a.name || '').localeCompare(b.name || ''));

      setSites(tabSites);
    } catch (err) {
      console.error('Failed to fetch sites:', err);
    } finally {
      setLoading(false);
    }
  };

  const handleTabChange = (tab) => {
    setActiveTab(tab);
    setSearchTerm('');
    setLocationFilter('');
    setNotice(null);
    fetchSites(tab === 'archived');
  };

  const handleRestoreClick = async (e, site) => {
    e.stopPropagation();
    try {
      setIsRestoring(true);
      await api.sites.restore(site.id);
      setSites(sites.filter((s) => s.id !== site.id));
    } catch (err) {
      console.error('Failed to restore site:', err);
      alert('Failed to restore site');
    } finally {
      setIsRestoring(false);
    }
  };

  const handleDeleteClick = (e, site) => {
    e.stopPropagation();
    setSiteToDelete(site);
    setDeleteDialogOpen(true);
  };

  const handleEditClick = (e, site) => {
    e.stopPropagation();
    navigate(`/sites/${site.id}/edit`);
  };

  const handleCopySiteId = async (e, site) => {
    e.stopPropagation();
    const siteId = site.site_id || site.id;
    if (!siteId) return;
    try {
      await navigator.clipboard.writeText(siteId);
      setCopiedSiteId(siteId);
      setTimeout(() => setCopiedSiteId(null), 2000);
    } catch {
      console.error('Failed to copy site ID');
    }
  };

  const handleViewDetails = (e, site) => {
    e.stopPropagation();
    if (!site.id) return;

    trackActivity('click', '/sites', { site_id: site.id }, 'view_site_details_btn');

    if (site.is_active === false) {
      setNotice(`Details for "${site.name}" are not available until the site is restored.`);
      return;
    }

    navigate(`/sites/${site.id}`);
  };

  const handleConfirmDelete = async (mode) => {
    if (!siteToDelete) return;

    try {
      setIsDeleting(true);
      await api.sites.delete(siteToDelete.id, mode);
      setSites(sites.filter((s) => s.id !== siteToDelete.id));
      setDeleteDialogOpen(false);
      setSiteToDelete(null);
    } catch (err) {
      console.error('Failed to delete site:', err);
      alert('Failed to delete site');
    } finally {
      setIsDeleting(false);
    }
  };

  const filteredSites = sites.filter((site) => {
    const matchSearch =
      site.name.toLowerCase().includes(searchTerm.toLowerCase()) ||
      (site.id && site.id.toString().includes(searchTerm));
    const matchLocation = locationFilter ? site.location === locationFilter : true;
    return matchSearch && matchLocation;
  });

  if (loading) {
    return (
      <div className="min-h-screen bg-[#0b0e13] text-white flex items-center justify-center">
        <p className="text-teal-400 animate-pulse">Loading sites...</p>
      </div>
    );
  }

  return (
    <div className="h-full max-h-screen bg-[#0b0e13] text-white p-2 flex flex-col overflow-hidden">
      <div className="shrink-0 mb-2">
        <Button
          variant="ghost"
          onClick={() => navigate('/dashboard')}
          className="mb-2 pl-0 hover:pl-1 transition-all text-gray-400 hover:text-white hover:bg-transparent"
        >
          <ArrowLeft className="h-4 w-4 mr-2" />
          Back to Dashboard
        </Button>

        <div className="flex flex-col md:flex-row justify-between items-center mb-4 gap-3">
          <h1 className="text-xl font-semibold">Manage Sites</h1>
        </div>

        {/* Active / Archived tabs */}
        <div className="flex gap-1 mb-4 bg-[#141a24] border border-[#1f2735] rounded-lg p-1 w-fit">
          <button
            onClick={() => handleTabChange('active')}
            className={`px-4 py-1.5 text-sm rounded-md transition-colors ${
              activeTab === 'active'
                ? 'bg-teal-500/20 text-teal-400 border border-teal-500/30'
                : 'text-gray-400 hover:text-white hover:bg-[#1f2735]'
            }`}
          >
            Active
          </button>
          <button
            onClick={() => handleTabChange('archived')}
            className={`px-4 py-1.5 text-sm rounded-md transition-colors ${
              activeTab === 'archived'
                ? 'bg-teal-500/20 text-teal-400 border border-teal-500/30'
                : 'text-gray-400 hover:text-white hover:bg-[#1f2735]'
            }`}
          >
            Archived
          </button>
        </div>

        {notice && (
          <div className="flex items-center justify-between gap-3 mb-4 px-4 py-2.5 rounded-lg bg-[#1a1f2b] border border-yellow-500/30 text-yellow-300 text-sm">
            <span>{notice}</span>
            <button
              onClick={() => setNotice(null)}
              className="text-gray-400 hover:text-white transition-colors shrink-0"
              title="Dismiss"
            >
              ✕
            </button>
          </div>
        )}

        <div className="flex flex-col md:flex-row items-center gap-2 mb-4">
          {/* Search input */}
          <div className="relative w-full md:w-1/2">
            <span className="absolute inset-y-0 left-0 flex items-center pl-3 pointer-events-none">
              <Search className="h-4 w-4 text-gray-400" />
            </span>
            <input
              type="text"
              placeholder="Search by site ID or name"
              className="bg-[#141a24] border border-[#1f2735] text-white px-9 py-1.5 text-sm rounded-lg w-full focus:outline-none focus:border-teal-500 transition-colors"
              value={searchTerm}
              // onChange={(e) => setSearchTerm(e.target.value)}
              onChange={(e) => {
                setSearchTerm(e.target.value);

                // Track Search
                trackSearch(e.target.value, '/sites', 0);
              }}
            />
          </div>

          {/* Location dropdown */}
          <select
            className="bg-[#141a24] border border-[#1f2735] text-white w-full md:w-64 px-3 py-[7px] text-sm rounded-lg focus:outline-none focus:border-teal-500 transition-colors"
            value={locationFilter}
            // onChange={(e) => setLocationFilter(e.target.value)}
            onChange={(e) => {
              setLocationFilter(e.target.value);

              trackActivity(
                'interaction',
                '/sites',
                { selected_location: e.target.value }, // extra_data
                'location_filter' // element id
              );
            }}
          >
            <option value="">All Locations</option>
            {/* Extract unique locations from sites */}
            {[...new Set(sites.map((s) => s.location).filter(Boolean))].map((loc) => (
              <option key={loc} value={loc}>
                {loc}
              </option>
            ))}
          </select>
        </div>
      </div>

      <div className="flex-1 overflow-y-auto min-h-0 pb-2 pr-1 custom-scrollbar">
        {filteredSites.length === 0 ? (
          <div className="flex items-center justify-center h-full text-gray-500 text-sm">
            {activeTab === 'archived'
              ? 'No archived sites. Archive a site from the Active tab to see it here.'
              : 'No sites found.'}
          </div>
        ) : (
          <div className="grid sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-3">
            {filteredSites.map((site) => (
              <div
                key={site.id}
                className="bg-[#141a24] border border-[#1f2735] rounded-xl p-5 hover:border-teal-400 transition-all flex flex-col group relative"
              >
                {/* Edit/Delete Actions - Always visible */}
                <div className="absolute top-4 right-4 flex gap-2">
                  {activeTab === 'archived' ? (
                    <button
                      onClick={(e) => {
                        e.stopPropagation();

                        trackActivity('click', '/sites', { site_id: site.id }, 'restore_site_btn');

                        handleRestoreClick(e, site);
                      }}
                      className="p-1.5 rounded-md bg-[#1f2735] hover:bg-teal-900/30 text-gray-400 hover:text-teal-400 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
                      title="Restore"
                      disabled={isRestoring}
                    >
                      <RotateCcw size={14} />
                    </button>
                  ) : (
                    <>
                      <button
                        // onClick={(e) => handleEditClick(e, site)}
                        onClick={(e) => {
                          e.stopPropagation();

                          trackActivity('click', '/sites', { site_id: site.id }, 'edit_site_btn');

                          handleEditClick(e, site);
                        }}
                        className="p-1.5 rounded-md bg-[#1f2735] hover:bg-[#2a3441] text-gray-400 hover:text-white transition-colors"
                        title="Edit"
                      >
                        <Edit size={14} />
                      </button>
                      <button
                        // onClick={(e) => handleDeleteClick(e, site)}
                        onClick={(e) => {
                          e.stopPropagation();

                          trackActivity('click', '/sites', { site_id: site.id }, 'delete_site_btn');

                          handleDeleteClick(e, site);
                        }}
                        className="p-1.5 rounded-md bg-[#1f2735] hover:bg-red-900/30 text-gray-400 hover:text-red-400 transition-colors"
                        title="Delete"
                      >
                        <Trash2 size={14} />
                      </button>
                    </>
                  )}
                </div>

                <div className="mb-6">
                  <h2
                    className="text-lg font-semibold text-white text-start truncate pr-16"
                    title={site.name}
                  >
                    {site.name}
                  </h2>
                  <div className="flex flex-col gap-1 mt-1 mb-2">
                    <div className="flex items-center gap-1.5">
                      <p className="text-xs font-mono text-teal-400/70 text-start truncate">
                        Site ID: {site.site_id || site.id}
                      </p>
                      <button
                        onClick={(e) => handleCopySiteId(e, site)}
                        className="p-0.5 rounded text-gray-400 hover:text-teal-400 transition-colors shrink-0"
                        title="Copy Site ID"
                      >
                        {copiedSiteId === (site.site_id || site.id) ? (
                          <Check size={12} className="text-teal-400" />
                        ) : (
                          <Copy size={12} />
                        )}
                      </button>
                    </div>
                    <p className="text-sm text-gray-400 text-start truncate">
                      {site.location || 'No location'}
                    </p>
                  </div>
                </div>

                <div className="flex items-center space-x-3 mb-3">
                  {/* Render icons based on OS types present in the site */}
                  {site.os_types && site.os_types.includes('windows') && <OsIcon type="windows" />}
                  {site.os_types && site.os_types.includes('linux') && <OsIcon type="linux" />}
                  {site.os_types &&
                    (site.os_types.includes('macos') ||
                      site.os_types.includes('ios') ||
                      site.os_types.includes('apple')) && <OsIcon type="macos" />}
                  {site.os_types && site.os_types.includes('android') && <OsIcon type="android" />}
                  {site.os_types && site.os_types.includes('web') && <OsIcon type="web" />}
                  {site.os_types &&
                    (site.os_types.includes('iot') ||
                      site.os_types.includes('sensor') ||
                      site.os_types.includes('iot_sensor') ||
                      site.os_types.includes('embedded') ||
                      site.os_types.some((t) => t.includes('iot'))) && <OsIcon type="iot" />}
                </div>

                {site.alert && (
                  <div className="flex items-center text-yellow-400 text-sm mb-2">
                    <AlertTriangle size={16} className="mr-2" /> {site.alert}
                  </div>
                )}

                <div className="flex flex-col gap-2 mb-3">
                  <div className="flex items-center gap-2">
                    <span
                      className={`w-3 h-3 rounded-full ${site.status === 'Online' ? 'bg-green-400' : 'bg-red-500'}`}
                    ></span>
                    <span className="text-sm">{site.status}</span>
                  </div>
                  <div className="flex items-center gap-2 text-sm text-gray-400">
                    <span>Registered Devices:</span>
                    <span className="font-semibold text-white">{site.devices_count || 0}</span>
                  </div>
                </div>

                {/* View Details button */}
                <button
                  onClick={(e) => handleViewDetails(e, site)}
                  className="mt-auto w-full border border-[#1f2735] py-2 rounded-lg text-sm hover:bg-[#1f2735] text-gray-300 transition"
                >
                  View Details
                </button>
              </div>
            ))}
          </div>
        )}
      </div>

      <SiteDeleteDialog
        isOpen={deleteDialogOpen}
        onClose={() => setDeleteDialogOpen(false)}
        onConfirm={handleConfirmDelete}
        siteName={siteToDelete?.name}
        isDeleting={isDeleting}
      />
    </div>
  );
}
