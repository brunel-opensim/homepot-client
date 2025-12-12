import React from 'react';
import { MapPin, Server, Activity, MoreVertical, Edit, Trash2 } from 'lucide-react';
import { Card } from '@/components/ui/card';
import { Button } from '@/components/ui/button';

export default function SiteCard({ site, onEdit, onDelete }) {
  return (
    <Card className="p-5 hover:shadow-md transition-shadow border-border/60">
      <div className="flex justify-between items-start mb-4">
        <div>
          <h3
            className="font-semibold text-lg text-foreground truncate max-w-[200px]"
            title={site.name}
          >
            {site.name}
          </h3>
          <div className="flex items-center text-muted-foreground text-sm mt-1">
            <MapPin className="h-3.5 w-3.5 mr-1" />
            <span className="truncate max-w-[180px]">{site.location || 'No location'}</span>
          </div>
        </div>

        <div className="flex gap-1">
          <Button
            variant="ghost"
            size="icon"
            className="h-8 w-8"
            onClick={() => onEdit(site)}
            title="Edit"
          >
            <Edit className="h-4 w-4" />
          </Button>
          <Button
            variant="ghost"
            size="icon"
            className="h-8 w-8 text-destructive hover:text-destructive"
            onClick={() => onDelete(site)}
            title="Delete"
          >
            <Trash2 className="h-4 w-4" />
          </Button>
        </div>
      </div>

      <div className="grid grid-cols-2 gap-4 mt-4 pt-4 border-t border-border/50">
        <div className="flex flex-col">
          <span className="text-xs text-muted-foreground mb-1">Devices</span>
          <div className="flex items-center font-medium">
            <Server className="h-4 w-4 mr-2 text-primary" />
            {site.devices_count || 0}
          </div>
        </div>
        <div className="flex flex-col">
          <span className="text-xs text-muted-foreground mb-1">Status</span>
          <div className="flex items-center font-medium">
            <Activity className="h-4 w-4 mr-2 text-green-500" />
            Active
          </div>
        </div>
      </div>
    </Card>
  );
}
