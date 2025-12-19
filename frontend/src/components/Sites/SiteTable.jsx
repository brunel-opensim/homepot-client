import React from 'react';
import { Edit, Trash2, MapPin, Server, MoreHorizontal } from 'lucide-react';
import { Button } from '@/components/ui/button';

export default function SiteTable({ sites, onEdit, onDelete }) {
  return (
    <div className="rounded-md border border-border overflow-hidden">
      <table className="w-full text-sm text-left">
        <thead className="bg-muted/50 text-muted-foreground font-medium border-b border-border">
          <tr>
            <th className="px-4 py-3">Name</th>
            <th className="px-4 py-3">Location</th>
            <th className="px-4 py-3">Devices</th>
            <th className="px-4 py-3">Status</th>
            <th className="px-4 py-3 text-right">Actions</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-border">
          {sites.length === 0 ? (
            <tr>
              <td colSpan="5" className="px-4 py-8 text-center text-muted-foreground">
                No sites found. Create one to get started.
              </td>
            </tr>
          ) : (
            sites.map((site) => (
              <tr key={site.id} className="hover:bg-muted/30 transition-colors">
                <td className="px-4 py-3 font-medium text-foreground">{site.name}</td>
                <td className="px-4 py-3 text-muted-foreground">
                  <div className="flex items-center">
                    <MapPin className="h-3.5 w-3.5 mr-1.5 opacity-70" />
                    {site.location || '-'}
                  </div>
                </td>
                <td className="px-4 py-3">
                  <div className="flex items-center">
                    <Server className="h-3.5 w-3.5 mr-1.5 opacity-70" />
                    {site.devices_count || 0}
                  </div>
                </td>
                <td className="px-4 py-3">
                  <span className="inline-flex items-center px-2 py-1 rounded-full text-xs font-medium bg-green-500/10 text-green-600 dark:text-green-400">
                    Active
                  </span>
                </td>
                <td className="px-4 py-3 text-right">
                  <div className="flex justify-end gap-2">
                    <Button variant="ghost" size="sm" onClick={() => onEdit(site)} title="Edit">
                      <Edit className="h-4 w-4" />
                    </Button>
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={() => onDelete(site)}
                      className="text-destructive hover:text-destructive"
                      title="Delete"
                    >
                      <Trash2 className="h-4 w-4" />
                    </Button>
                  </div>
                </td>
              </tr>
            ))
          )}
        </tbody>
      </table>
    </div>
  );
}
