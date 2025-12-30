import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { AlertTriangle, Search, Edit, Trash2, ArrowLeft } from 'lucide-react';
import { Button } from '@/components/ui/button';
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

  // Icons from Site.jsx
  const WindowsIcon = () => (
    <img
      src="https://cdn.jsdelivr.net/gh/simple-icons/simple-icons/icons/windows.svg"
      alt="Windows"
      className="w-5 h-5"
      style={{
        filter:
          'invert(86%) sepia(36%) saturate(319%) hue-rotate(122deg) brightness(99%) contrast(98%)',
      }}
    />
  );

  const AppleIcon = () => (
    <img
      src="https://cdn.jsdelivr.net/gh/simple-icons/simple-icons/icons/apple.svg"
      alt="Apple"
      className="w-5 h-5 text-gray-300"
      style={{
        filter:
          'invert(86%) sepia(36%) saturate(319%) hue-rotate(122deg) brightness(99%) contrast(98%)',
      }}
    />
  );

  const LinuxIcon = () => (
    <img
      src="https://cdn.jsdelivr.net/gh/simple-icons/simple-icons/icons/linux.svg"
      alt="Linux"
      className="w-5 h-5"
      style={{
        filter:
          'invert(86%) sepia(36%) saturate(319%) hue-rotate(122deg) brightness(99%) contrast(98%)',
      }}
    />
  );

  const AndroidIcon = () => (
    <img
      src="https://cdn.jsdelivr.net/gh/simple-icons/simple-icons/icons/android.svg"
      alt="Android"
      className="w-5 h-5 text-gray-300"
      style={{
        filter:
          'invert(86%) sepia(36%) saturate(319%) hue-rotate(122deg) brightness(99%) contrast(98%)',
      }}
    />
  );

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

  const fetchSites = async () => {
    try {
      setLoading(true);
      const data = await api.sites.list();
      const fetchedSites = Array.isArray(data) ? data : data.sites || [];

      // Add temporary static fields to match Site.jsx look if missing from API
      const withStaticValues = fetchedSites.map((site) => ({
        ...site,
        id: site.id || site.site_id,
        status: site.status || (Math.random() > 0.5 ? 'Online' : 'Offline'),
        alert:
          site.alert ||
          (Math.random() > 0.6
            ? `${Math.floor(Math.random() * 3) + 1} asst alert: ${Math.floor(Math.random() * 5) + 1}h ago`
            : null),
      }));

      setSites(withStaticValues);
    } catch (err) {
      console.error('Failed to fetch sites:', err);
    } finally {
      setLoading(false);
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

  const handleConfirmDelete = async () => {
    if (!siteToDelete) return;

    try {
      setIsDeleting(true);
      await api.sites.delete(siteToDelete.id);
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
    <div className="min-h-screen bg-[#0b0e13] text-white p-6">
      <Button
        variant="ghost"
        onClick={() => navigate('/dashboard')}
        className="mb-4 pl-0 hover:pl-1 transition-all text-gray-400 hover:text-white hover:bg-transparent"
      >
        <ArrowLeft className="h-4 w-4 mr-2" />
        Back to Dashboard
      </Button>

      <div className="flex flex-col md:flex-row justify-between items-center mb-6 gap-3">
        <h1 className="text-2xl font-semibold">Manage Sites</h1>
      </div>

      <div className="flex flex-col md:flex-row items-center gap-3 mb-6">
        {/* Search input */}
        <div className="relative w-full md:w-1/2">
          <span className="absolute inset-y-0 left-0 flex items-center pl-3 pointer-events-none">
            <Search className="h-5 w-5 text-gray-400" />
          </span>
          <input
            type="text"
            placeholder="Search by site ID or name"
            className="bg-[#141a24] border border-[#1f2735] text-white px-10 py-2 rounded-lg w-full focus:outline-none focus:border-teal-500 transition-colors"
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
          className="bg-[#141a24] border border-[#1f2735] text-white w-full md:w-80 px-4 py-[10px] rounded-lg focus:outline-none focus:border-teal-500 transition-colors"
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

        {/* Status box placeholder */}
        <div className="bg-[#141a24] border border-[#1f2735] text-white px-4 py-[10px] rounded-lg hidden md:block">
          <p className="text-sm">Status</p>
        </div>
      </div>

      <div className="grid sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4">
        {filteredSites.map((site) => (
          <div
            key={site.id}
            className="bg-[#141a24] border border-[#1f2735] rounded-xl p-5 hover:border-teal-400 transition-all flex flex-col group relative"
            onClick={() => navigate(`/sites/${site.id}`)}
          >
            {/* Edit/Delete Actions - Visible on hover or always visible on mobile */}
            <div className="absolute top-4 right-4 flex gap-2 opacity-0 group-hover:opacity-100 transition-opacity">
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
            </div>

            <div className="mb-6 cursor-pointer">
              <h2 className="text-lg font-semibold text-white text-start truncate pr-16">
                {site.name}
              </h2>
              <p className="text-sm text-gray-400 mb-2 text-start truncate">
                {site.location || 'No location'}
              </p>
            </div>

            <div className="flex items-center space-x-3 mb-3">
              {site.status === 'Online' && (
                <>
                  <WindowsIcon />
                  <LinuxIcon />
                  <AppleIcon />
                  <AndroidIcon />
                </>
              )}
            </div>

            {site.alert && (
              <div className="flex items-center text-yellow-400 text-sm mb-2">
                <AlertTriangle size={16} className="mr-2" /> {site.alert}
              </div>
            )}

            <div className="flex items-center gap-2 mb-3">
              <span
                className={`w-3 h-3 rounded-full ${site.status === 'Online' ? 'bg-green-400' : 'bg-red-500'}`}
              ></span>
              <span className="text-sm">{site.status}</span>
            </div>

            {/* View Details button */}
            <button
              // onClick={(e) => {
              //   e.stopPropagation();
              //   navigate(`/sites/${site.id}`);
              // }}
              onClick={(e) => {
                e.stopPropagation();

                trackActivity('click', '/sites', { site_id: site.id }, 'view_site_details_btn');

                navigate(`/sites/${site.id}`);
              }}
              className="mt-auto w-full border border-[#1f2735] py-2 rounded-lg text-sm hover:bg-[#1f2735] text-gray-300 transition"
            >
              View Details
            </button>
          </div>
        ))}
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
