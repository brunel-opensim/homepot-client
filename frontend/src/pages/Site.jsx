import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Terminal, Smartphone, AlertTriangle } from 'lucide-react';
import { Button } from '@/components/ui/button';

export default function SiteScreen() {
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

  // Apple Icon (light grey)
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
  const navigate = useNavigate();

  const [searchTerm, setSearchTerm] = useState('');
  const [locationFilter, setLocationFilter] = useState('');

  const sites = [
    { id: '00001', name: 'Site - 00001', location: 'Los Angeles', status: 'Online', alert: null },
    {
      id: '00002',
      name: 'Site - 00002',
      location: 'New York',
      status: 'Online',
      alert: '1 asst alert: 2h ago',
    },
    { id: '00003', name: 'Site - 00003', location: 'Chicago', status: 'Online', alert: null },
    {
      id: '00004',
      name: 'Site - 00004',
      location: 'New York',
      status: 'Offline',
      alert: '2 asst alerts: 1h ago',
    },
  ];

  const filteredSites = sites.filter((site) => {
    const matchSearch =
      site.name.toLowerCase().includes(searchTerm.toLowerCase()) || site.id.includes(searchTerm);
    const matchLocation = locationFilter ? site.location === locationFilter : true;
    return matchSearch && matchLocation;
  });

  return (
    <div className="min-h-screen bg-[#0b0e13] text-white p-6">
      <div className="flex flex-col md:flex-row justify-between items-center mb-6 gap-3">
        <h1 className="text-2xl font-semibold">View Sites</h1>
        <div className="flex gap-3">
          <Button className="bg-primary text-textPrimary border border-borderPrimary">
            View Devices
          </Button>
          <Button className="bg-primary text-textPrimary border border-borderPrimary">
            Send Notification
          </Button>
        </div>
      </div>

      <div className="flex flex-col md:flex-row items-center gap-3 mb-6">
        <input
          type="text"
          placeholder="Search by site ID or name"
          className="bg-[#141a24] border border-[#1f2735] text-white px-4 py-2 rounded-lg w-full md:w-1/2 focus:outline-none"
          value={searchTerm}
          onChange={(e) => setSearchTerm(e.target.value)}
        />

        <select
          className="bg-[#141a24] border border-[#1f2735] text-textPrimary w-80 px-4 py-[10px] rounded-lg"
          value={locationFilter}
          onChange={(e) => setLocationFilter(e.target.value)}
        >
          <option value="">Location</option>
          <option value="Los Angeles">Los Angeles</option>
          <option value="New York">New York</option>
          <option value="Chicago">Chicago</option>
        </select>
        <div className="bg-[#141a24] border border-[#1f2735] text-textPrimary px-4 py-[10px] rounded-lg">
          <p className="text-textPrimary text-sm">Status</p>
        </div>
      </div>

      <div className="grid sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4">
        {filteredSites.map((site) => (
          <div
            key={site.id}
            // onClick={() => handleCardClick(site.id)}
            className="bg-[#141a24] border border-[#1f2735] rounded-xl p-5 hover:border-teal-400 cursor-pointer transition-all flex flex-col"
          >
            <div className="mb-6">
              <h2 className="text-lg font-semibold text-text text-start">{site.name}</h2>
              <p className="text-sm text-textPrimary mb-2 text-start">{site.location}</p>
            </div>

            <div className="flex items-center space-x-3 mb-3">
              <WindowsIcon />
              <LinuxIcon />
              <AppleIcon />
              <AndroidIcon />
            </div>

            {site.alert ? (
              <div className="flex items-center text-yellow-400 text-sm mb-2">
                <AlertTriangle size={16} className="mr-2" /> {site.alert}
              </div>
            ) : null}

            <div className="flex items-center gap-2 mb-3">
              <span
                className={`w-3 h-3 rounded-full ${
                  site.status === 'Online' ? 'bg-green-400' : 'bg-red-500'
                }`}
              ></span>
              <span className="text-sm">{site.status}</span>
            </div>

            {/* push button to bottom */}
            <button
              onClick={(e) => {
                e.stopPropagation();
                navigate(`/site/${site.id}`);
              }}
              className="mt-auto w-full border border-borderPrimary py-2 rounded-lg text-sm hover:bg-[#1f2735] text-textPrimary transition"
            >
              View Devices
            </button>
          </div>
        ))}
      </div>
    </div>
  );
}
