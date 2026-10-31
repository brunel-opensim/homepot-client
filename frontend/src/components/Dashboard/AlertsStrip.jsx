import React from 'react';
import { Card, CardContent } from '@/components/ui/card';
import ActiveAlertsTicker from '@/components/Dashboard/ActiveAlertsTicker';

/**
 * Compact full-width strip showing active alerts.
 *
 * System Pulse moved into the summary stats row; this strip now carries only
 * the alerts ticker so it gets the full row width.
 */
const AlertsStrip = ({ alerts }) => {
  return (
    <div className="mb-2 shrink-0">
      <Card className="bg-[#080A0A] border border-secondary shrink-0">
        <CardContent className="p-2">
          <div className="flex items-center gap-2">
            <h2 className="text-xs font-semibold text-white shrink-0">Active Alerts</h2>
            <div className="flex-1 min-w-0">
              <ActiveAlertsTicker alerts={alerts} />
            </div>
          </div>
        </CardContent>
      </Card>
    </div>
  );
};

export default AlertsStrip;
