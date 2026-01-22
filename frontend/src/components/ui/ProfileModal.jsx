import React from 'react';
import { User, Mail, AtSign, Shield, Calendar, CheckCircle } from 'lucide-react';
import { Dialog, DialogContent, DialogTitle } from './dialog';

export default function ProfileModal({ open, onOpenChange, user }) {
  if (!user) return null;

  // Determine visual theme based on role
  // "Engineer" or Admin -> Indigo/Purple theme
  // "Client" or User -> Teal/Emerald theme
  const isEngineer =
    (user.role && user.role.toLowerCase() === 'engineer') || user.role === 'Admin' || user.isAdmin;

  const theme = isEngineer
    ? {
        main: 'indigo',
        gradient: 'from-indigo-600 via-purple-600 to-indigo-800',
        light: 'indigo-400',
        bg: 'bg-indigo-500/10',
        border: 'border-indigo-500/20',
        text: 'text-indigo-300',
        shadow: 'shadow-indigo-500/20',
      }
    : {
        main: 'teal',
        gradient: 'from-teal-600 via-emerald-600 to-teal-800',
        light: 'teal-400',
        bg: 'bg-teal-500/10',
        border: 'border-teal-500/20',
        text: 'text-teal-300',
        shadow: 'shadow-teal-500/20',
      };

  const profileFields = [
    {
      icon: <User className="w-4 h-4" />,
      label: 'Full Name',
      value: user.fullName || 'Not set',
    },
    {
      icon: <AtSign className="w-4 h-4" />,
      label: 'Username',
      value: user.username || 'Not set',
    },
    {
      icon: <Mail className="w-4 h-4" />,
      label: 'Email',
      value: user.email || 'Not set',
    },
    {
      icon: <Shield className="w-4 h-4" />,
      label: 'Role Authorization',
      value: user.role || (user.isAdmin ? 'Admin' : 'User'),
    },
  ];

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="p-0 bg-slate-950 border-slate-800 text-white w-full max-w-sm overflow-hidden rounded-3xl shadow-2xl">
        <DialogTitle className="sr-only">User Profile</DialogTitle>

        {/* Header Banner */}
        <div className={`h-24 bg-gradient-to-r ${theme.gradient} relative`}>
          {/* Decorative patterns */}
          <div className="absolute inset-0 opacity-20 bg-[url('https://www.transparenttextures.com/patterns/cubes.png')] mix-blend-overlay"></div>
          <div className="absolute top-3 left-3 text-white/50 text-[10px] font-mono border border-white/10 px-1.5 py-0.5 rounded bg-black/10 backdrop-blur-sm">
            ID: {Math.random().toString(36).substr(2, 9).toUpperCase()}
          </div>
        </div>

        {/* Profile Content */}
        <div className="px-5 pb-6 relative">
          {/* Avatar - Floating overlap */}
          <div className="flex justify-between items-end -mt-10 mb-4">
            <div className={`w-20 h-20 rounded-full p-1 bg-slate-950 shadow-xl ${theme.shadow}`}>
              <div
                className={`w-full h-full rounded-full bg-gradient-to-br ${theme.gradient} flex items-center justify-center text-2xl font-bold text-white shadow-inner`}
              >
                {user.fullName?.[0]?.toUpperCase() || user.username?.[0]?.toUpperCase() || 'U'}
              </div>
            </div>

            {/* Status Badge */}
            <div
              className={`px-3 py-1 rounded-full text-[10px] font-bold tracking-wider border bg-slate-900/80 backdrop-blur ${theme.text} ${theme.border} flex items-center gap-1.5 mb-2 shadow-lg`}
            >
              <div className={`w-1.5 h-1.5 rounded-full bg-${theme.main}-400 animate-pulse`}></div>
              {isEngineer ? 'SYSTEM LEVEL' : 'ACTIVE USER'}
            </div>
          </div>

          <div className="space-y-0.5 mb-5">
            <h2 className="text-xl font-bold text-white tracking-tight leading-tight">
              {user.fullName || user.username}
            </h2>
            <p className="text-slate-400 text-sm flex items-center gap-2">
              <span className={`inline-block w-3 h-[1px] bg-${theme.main}-500`}></span>
              {user.email}
            </p>
          </div>

          {/* Verification Card - Compact */}
          <div
            className={`mb-4 p-3 rounded-xl border ${theme.border} ${theme.bg} relative overflow-hidden group`}
          >
            <div
              className={`absolute top-0 right-0 p-2 opacity-10 group-hover:opacity-20 transition-opacity`}
            >
              <Shield className="w-12 h-12" />
            </div>
            <div className="flex items-center gap-3">
              <div className={`p-1.5 rounded-lg bg-slate-900/50 ${theme.text}`}>
                <CheckCircle className="w-4 h-4" />
              </div>
              <div>
                <h3 className={`text-xs font-bold ${theme.text}`}>Account Verified</h3>
                <p className="text-[10px] text-slate-400">Security checks passed.</p>
              </div>
            </div>
          </div>

          {/* Details Grid - Compact */}
          <div className="grid grid-cols-1 gap-2">
            {profileFields.map((field, index) => (
              <div
                key={index}
                className="group flex items-center gap-3 p-2.5 rounded-lg bg-slate-900/50 border border-slate-800 hover:border-slate-700 hover:bg-slate-900 transition-all duration-200"
              >
                <div
                  className={`flex-shrink-0 w-8 h-8 rounded-md bg-slate-950 border border-slate-800 flex items-center justify-center text-slate-400 group-hover:${theme.text} group-hover:border-${theme.main}-500/30 transition-colors`}
                >
                  {field.icon}
                </div>
                <div className="flex-1 min-w-0">
                  <p className="text-[9px] uppercase font-bold text-slate-500 tracking-wider mb-0.5">
                    {field.label}
                  </p>
                  <p className="text-xs font-medium text-slate-200 truncate">{field.value}</p>
                </div>
              </div>
            ))}
          </div>

          {/* Footer Metadata */}
          <div className="mt-6 flex items-center justify-between text-[10px] text-slate-600 pt-3 border-t border-slate-900">
            <div className="flex items-center gap-1.5">
              <Calendar className="w-3 h-3" />
              Joined {new Date().getFullYear()}
            </div>
            <span>HOMEPOT Client v2.1</span>
          </div>
        </div>
      </DialogContent>
    </Dialog>
  );
}
