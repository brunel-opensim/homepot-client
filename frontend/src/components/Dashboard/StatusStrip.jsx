import React from 'react';
import { Card, CardContent } from '@/components/ui/card';
import ActiveAlertsTicker from '@/components/Dashboard/ActiveAlertsTicker';

/**
 * Compact status strip shown above the main Dashboard grid.
 *
 * System Pulse and Active Alerts used to live in the Dashboard's right column,
 * above the AI assistant, which squeezed the assistant into a small area. Moving
 * them here frees the whole right column for the AI UI without touching the
 * monitored-devices area.
 */
const StatusStrip = ({ systemPulse, alerts }) => {
  const activeCount = Math.ceil((systemPulse.load_score || 0) / 10);

  return (
    <div className="grid grid-cols-1 md:grid-cols-2 gap-2 mb-2 shrink-0">
      {/* System Pulse */}
      <Card className="bg-[#080A0A] border border-secondary shrink-0">
        <CardContent className="p-2">
          <div className="flex items-center justify-between gap-2">
            <h2 className="text-xs font-semibold text-white shrink-0">System Pulse</h2>
            <div className="flex space-x-1.5">
              {Array.from({ length: 10 }).map((_, i) => {
                const isActive = i < activeCount;
                let colorClass = 'bg-gray-800';
                if (isActive) {
                  if (i < 6) {
                    colorClass = 'bg-green-500 shadow-[0_0_6px_rgba(34,197,94,0.6)]';
                  } else if (i < 8) {
                    colorClass = 'bg-yellow-500 shadow-[0_0_6px_rgba(234,179,8,0.6)]';
                  } else {
                    colorClass = 'bg-red-500 shadow-[0_0_8px_rgba(239,68,68,0.8)]';
                  }
                }
                return (
                  <span
                    key={i}
                    className={`w-2.5 h-2.5 rounded-full transition-all duration-300 ${colorClass} ${isActive ? 'scale-110' : 'scale-100'}`}
                  />
                );
              })}
            </div>
            <p className="text-[10px] text-gray-400 font-mono whitespace-nowrap">
              Load:{' '}
              <span
                className={
                  systemPulse.load_score >= 90
                    ? 'text-red-400 font-bold'
                    : systemPulse.load_score >= 70
                      ? 'text-yellow-400'
                      : 'text-green-400'
                }
              >
                {systemPulse.load_score}%
              </span>
              {' · '}
              Jobs: {systemPulse.active_jobs > 0 ? systemPulse.active_jobs : 'IDLE'}
              {' · '}
              CPU: {Math.round(systemPulse.cpu_percent || 0)}%{' · '}
              Mem: {Math.round(systemPulse.memory_percent || 0)}%
            </p>
          </div>
        </CardContent>
      </Card>

      {/* Active Alerts */}
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

export default StatusStrip;
