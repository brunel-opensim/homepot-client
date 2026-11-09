import React, { useState, useEffect } from 'react';
import { NavLink } from 'react-router-dom';
import {
  LayoutDashboard,
  Map,
  Monitor,
  PlusCircle,
  LogOut,
  Sparkles,
  Download,
} from 'lucide-react';
import { useAuth } from '@/hooks/useAuth';
import api from '@/services/api';
import ProfileModal from '@/components/ui/ProfileModal';

function NavList({ items, pendingProposals = 0 }) {
  return (
    <div className="space-y-1">
      {items.map((item) => (
        <NavLink
          key={item.to}
          to={item.to}
          className={({ isActive }) =>
            `flex items-center gap-3 px-3 py-2 rounded-md transition-colors ${
              isActive
                ? 'bg-indigo-600 text-white'
                : 'text-slate-300 hover:bg-slate-800 hover:text-white'
            }`
          }
        >
          {item.icon}
          <span>{item.label}</span>
          {item.to === '/ai-proposals' && pendingProposals > 0 && (
            <span className="ml-auto inline-flex items-center justify-center min-w-[20px] h-5 px-1.5 rounded-full bg-amber-500 text-black text-[11px] font-bold">
              {pendingProposals > 99 ? '99+' : pendingProposals}
            </span>
          )}
        </NavLink>
      ))}
    </div>
  );
}

export default function Sidebar() {
  const { logout, user } = useAuth();
  const [profileOpen, setProfileOpen] = useState(false);
  const [pendingProposals, setPendingProposals] = useState(0);

  useEffect(() => {
    let cancelled = false;
    const fetchPending = async () => {
      try {
        const data = await api.ai.getPlanSummary(30, null);
        if (!cancelled) {
          setPendingProposals(data?.needs_approval ?? data?.by_status?.pending_approval ?? 0);
        }
      } catch {
        // ignore — badge is best-effort
      }
    };
    fetchPending();
    const interval = setInterval(fetchPending, 30000);
    return () => {
      cancelled = true;
      clearInterval(interval);
    };
  }, []);

  const navItems = [
    { to: '/dashboard', icon: <LayoutDashboard size={20} />, label: 'Dashboard' },
    { to: '/sites', icon: <Map size={20} />, label: 'Sites' },
    { to: '/device', icon: <Monitor size={20} />, label: 'Devices' },
    { to: '/ai-proposals', icon: <Sparkles size={20} />, label: 'AI Proposals' },
  ];

  const actionItems = [
    { to: '/sites/new', icon: <PlusCircle size={20} />, label: 'Add Site' },
    { to: '/device/new', icon: <PlusCircle size={20} />, label: 'Register Device' },
    { to: '/downloads', icon: <Download size={20} />, label: 'Downloads' },
  ];

  return (
    <div className="w-64 bg-slate-900 text-white flex flex-col h-screen fixed left-0 top-0">
      <div className="p-6 border-b border-slate-800">
        <h1 className="text-xl font-bold text-indigo-400">
          HOMEPOT{' '}
          <span className="text-xs font-normal text-slate-400">
            v{import.meta.env.VITE_APP_VERSION || 'dev'}
          </span>
        </h1>
      </div>

      <nav className="flex-1 p-4 space-y-6 overflow-y-auto">
        <div>
          <h3 className="text-xs font-semibold text-slate-500 uppercase tracking-wider mb-3 px-2">
            Overview
          </h3>
          <div className="space-y-1">
            <NavList items={navItems} pendingProposals={pendingProposals} />
          </div>
        </div>

        <div>
          <h3 className="text-xs font-semibold text-slate-500 uppercase tracking-wider mb-3 px-2">
            Actions
          </h3>
          <div className="space-y-1">
            <NavList items={actionItems} />
          </div>
        </div>
      </nav>

      <div className="p-4 border-t border-slate-800">
        <button
          onClick={() => setProfileOpen(true)}
          className="w-full flex items-center gap-3 px-2 mb-4 py-2 rounded-md hover:bg-slate-800 transition-colors cursor-pointer"
        >
          <div className="w-8 h-8 rounded-full bg-gradient-to-br from-indigo-500 to-purple-600 flex items-center justify-center text-sm font-bold">
            {user?.fullName?.[0]?.toUpperCase() || user?.username?.[0]?.toUpperCase() || 'U'}
          </div>
          <div className="flex-1 overflow-hidden text-left">
            <p className="text-sm font-medium truncate">
              {user?.fullName || user?.username || (user?.isAdmin ? 'Admin' : 'User')}
            </p>
            <p
              className={`text-xs truncate ${user?.role === 'Engineer' ? 'text-indigo-400' : 'text-slate-400'}`}
            >
              {user?.role || 'View Profile'}
            </p>
          </div>
        </button>
        <button
          onClick={logout}
          className="w-full flex items-center gap-2 px-3 py-2 text-sm text-red-400 hover:bg-slate-800 rounded-md transition-colors"
        >
          <LogOut size={18} />
          <span>Sign Out</span>
        </button>
      </div>

      <ProfileModal open={profileOpen} onOpenChange={setProfileOpen} user={user} />
    </div>
  );
}
