import React from 'react';
import { User, Mail, AtSign, Shield } from 'lucide-react';
import { Dialog, DialogContent, DialogHeader, DialogTitle } from './dialog';

export default function ProfileModal({ open, onOpenChange, user }) {
  if (!user) return null;

  const profileFields = [
    {
      icon: <User className="w-5 h-5" />,
      label: 'Full Name',
      value: user.fullName || 'Not set',
    },
    {
      icon: <AtSign className="w-5 h-5" />,
      label: 'Username',
      value: user.username || 'Not set',
    },
    {
      icon: <Mail className="w-5 h-5" />,
      label: 'Email',
      value: user.email || 'Not set',
    },
    {
      icon: <Shield className="w-5 h-5" />,
      label: 'Role',
      value: user.role || (user.isAdmin ? 'Admin' : 'User'),
    },
  ];

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="bg-slate-900 border-slate-700 text-white sm:max-w-md">
        <DialogHeader>
          <DialogTitle className="text-xl font-semibold text-white">User Profile</DialogTitle>
        </DialogHeader>

        <div className="flex flex-col items-center py-4">
          {/* Avatar */}
          <div className="w-20 h-20 rounded-full bg-gradient-to-br from-indigo-500 to-purple-600 flex items-center justify-center text-3xl font-bold text-white shadow-lg mb-4">
            {user.fullName?.[0]?.toUpperCase() || user.username?.[0]?.toUpperCase() || 'U'}
          </div>

          {/* Name */}
          <h2 className="text-lg font-semibold text-white mb-1">
            {user.fullName || user.username || 'User'}
          </h2>

          {/* Role Badge */}
          <span
            className={`px-3 py-1 rounded-full text-xs font-medium ${
              user.isAdmin
                ? 'bg-amber-500/20 text-amber-400 border border-amber-500/30'
                : 'bg-teal-500/20 text-teal-400 border border-teal-500/30'
            }`}
          >
            {user.role || (user.isAdmin ? 'Admin' : 'User')}
          </span>
        </div>

        {/* Profile Details */}
        <div className="space-y-3 pt-2 border-t border-slate-700">
          {profileFields.map((field, index) => (
            <div
              key={index}
              className="flex items-center gap-3 p-3 rounded-lg bg-slate-800/50 hover:bg-slate-800 transition-colors"
            >
              <div className="flex-shrink-0 w-10 h-10 rounded-full bg-slate-700 flex items-center justify-center text-slate-400">
                {field.icon}
              </div>
              <div className="flex-1 min-w-0">
                <p className="text-xs text-slate-400 uppercase tracking-wider">{field.label}</p>
                <p className="text-sm font-medium text-white truncate">{field.value}</p>
              </div>
            </div>
          ))}
        </div>
      </DialogContent>
    </Dialog>
  );
}
