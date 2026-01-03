import React, { useState, useEffect } from 'react';
import {
  ChevronLeft,
  ChevronRight,
  AlertTriangle,
  AlertCircle,
  CheckCircle2,
  Maximize2,
  X,
} from 'lucide-react';
import { Button } from '@/components/ui/button';
import { useNavigate } from 'react-router-dom';
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from '@/components/ui/dialog';

const ActiveAlertsTicker = ({ alerts: rawAlerts = [] }) => {
  const [dismissedAlerts, setDismissedAlerts] = useState(() => {
    const saved = localStorage.getItem('dismissedAlerts');
    return saved ? JSON.parse(saved) : [];
  });

  // Filter out dismissed alerts
  const alerts = (rawAlerts || []).filter((alert) => {
    const alertId =
      alert.device_id && alert.timestamp ? `${alert.device_id}-${alert.timestamp}` : null;
    return !alertId || !dismissedAlerts.includes(alertId);
  });

  const [currentIndex, setCurrentIndex] = useState(0);
  const [isPaused, setIsPaused] = useState(false);
  const [isDialogOpen, setIsDialogOpen] = useState(false);
  const navigate = useNavigate();

  // Reset dialog state when alerts are cleared
  useEffect(() => {
    if (alerts.length === 0) {
      setIsDialogOpen(false);
    }
  }, [alerts.length]);

  // Auto-rotation logic
  useEffect(() => {
    // Don't rotate if paused, dialog is open, or not enough alerts
    if (alerts.length <= 1 || isPaused || isDialogOpen) return;

    const interval = setInterval(() => {
      setCurrentIndex((prev) => (prev + 1) % alerts.length);
    }, 4000); // Rotate every 4 seconds

    return () => clearInterval(interval);
  }, [alerts.length, isPaused, isDialogOpen]);

  const handleNext = (e) => {
    e.stopPropagation();
    setCurrentIndex((prev) => (prev + 1) % alerts.length);
  };

  const handlePrev = (e) => {
    e.stopPropagation();
    setCurrentIndex((prev) => (prev - 1 + alerts.length) % alerts.length);
  };

  const handleDismiss = (e, alert) => {
    e.stopPropagation();
    if (!alert.device_id || !alert.timestamp) return;

    const alertId = `${alert.device_id}-${alert.timestamp}`;
    const newDismissed = [...dismissedAlerts, alertId];
    setDismissedAlerts(newDismissed);
    localStorage.setItem('dismissedAlerts', JSON.stringify(newDismissed));

    // Adjust index if needed
    if (currentIndex >= alerts.length - 1) {
      setCurrentIndex(Math.max(0, alerts.length - 2));
    }
  };

  // Ensure safe index access in case alerts array changes size
  const safeIndex = currentIndex >= alerts.length ? 0 : currentIndex;
  const currentAlert = alerts[safeIndex];

  // Helper to get severity icon and color
  const getSeverityStyles = (severity) => {
    if (severity === 'critical') {
      return {
        icon: <AlertCircle className="w-4 h-4 text-red-500" />,
        textClass: 'text-red-400',
        borderClass: 'border-red-500/30 bg-red-500/10',
      };
    }
    return {
      icon: <AlertTriangle className="w-4 h-4 text-orange-400" />,
      textClass: 'text-orange-300',
      borderClass: 'border-orange-500/30 bg-orange-500/10',
    };
  };

  if (!alerts || alerts.length === 0) {
    return (
      <div className="flex items-center justify-center h-12 text-green-400 gap-2 bg-green-500/5 rounded-lg border border-green-500/20">
        <CheckCircle2 className="w-4 h-4" />
        <span className="text-sm font-medium">All systems normal</span>
      </div>
    );
  }

  const styles = getSeverityStyles(currentAlert?.severity);

  return (
    <div
      className="relative group"
      onMouseEnter={() => setIsPaused(true)}
      onMouseLeave={() => setIsPaused(false)}
    >
      {/* Main Ticker Card */}
      <div
        className={`flex items-center justify-between p-3 rounded-lg border transition-all duration-300 ${styles.borderClass} ${currentAlert?.device_id && !currentAlert.device_id.startsWith('mock-') ? 'cursor-pointer hover:bg-opacity-20' : ''}`}
        onClick={() => {
          if (currentAlert?.device_id && !currentAlert.device_id.startsWith('mock-')) {
            navigate(`/device/${currentAlert.device_id}`);
          }
        }}
      >
        <div className="flex items-center gap-3 overflow-hidden">
          <div className="shrink-0 animate-pulse">{styles.icon}</div>

          <div className="flex flex-col min-w-0">
            <div className="flex items-center gap-2">
              <span className={`text-sm font-semibold truncate ${styles.textClass}`}>
                {currentAlert?.message?.split(':')[0] || 'Alert'}
              </span>
              <span className="text-xs text-gray-500 shrink-0">
                {currentAlert?.timestamp
                  ? new Date(currentAlert.timestamp).toLocaleTimeString([], {
                      hour: '2-digit',
                      minute: '2-digit',
                    })
                  : ''}
              </span>
            </div>
            <span className="text-xs text-gray-400 truncate">
              {currentAlert?.message?.split(':').slice(1).join(':') || ''}
            </span>
          </div>
        </div>

        {/* Controls (visible on hover) */}
        <div className="flex items-center gap-1 opacity-0 group-hover:opacity-100 transition-opacity absolute right-2 bg-[#080A0A] border border-gray-800 rounded-md shadow-lg">
          <Button
            variant="ghost"
            size="icon"
            className="h-6 w-6 hover:bg-gray-800"
            onClick={handlePrev}
          >
            <ChevronLeft className="w-3 h-3 text-gray-400" />
          </Button>
          <span className="text-[10px] text-gray-500 font-mono w-8 text-center">
            {currentIndex + 1}/{alerts.length}
          </span>
          <Button
            variant="ghost"
            size="icon"
            className="h-6 w-6 hover:bg-gray-800"
            onClick={handleNext}
          >
            <ChevronRight className="w-3 h-3 text-gray-400" />
          </Button>

          {/* Expand Button */}
          <Dialog open={isDialogOpen} onOpenChange={setIsDialogOpen}>
            <DialogTrigger asChild>
              <Button
                variant="ghost"
                size="icon"
                className="h-6 w-6 hover:bg-gray-800 border-l border-gray-800 ml-1"
                onClick={(e) => {
                  e.stopPropagation();
                  setIsPaused(true); // Pause when opening
                }}
              >
                <Maximize2 className="w-3 h-3 text-gray-400" />
              </Button>
            </DialogTrigger>
            <DialogContent
              className="bg-[#080A0A] border-gray-800 text-gray-200 max-w-2xl max-h-[80vh] overflow-y-auto"
              onClick={(e) => e.stopPropagation()}
              onPointerDownOutside={() => setIsPaused(false)} // Resume when clicking outside
              onCloseAutoFocus={() => setIsPaused(false)} // Resume when closing
            >
              <DialogHeader>
                <DialogTitle>Active Alerts ({alerts.length})</DialogTitle>
              </DialogHeader>
              <div className="space-y-2 mt-4">
                {alerts.map((alert, idx) => {
                  const alertStyles = getSeverityStyles(alert.severity);
                  const isMock = alert.device_id && alert.device_id.startsWith('mock-');

                  return (
                    <div
                      key={idx}
                      className={`flex items-center gap-3 p-3 rounded-lg border ${alertStyles.borderClass} ${isMock ? '' : 'cursor-pointer hover:bg-opacity-20'} group/item`}
                      onClick={() => {
                        if (alert.device_id && !isMock) {
                          navigate(`/device/${alert.device_id}`);
                        }
                      }}
                    >
                      {alertStyles.icon}
                      <div className="flex-1">
                        <div className="flex justify-between">
                          <span className={`font-medium ${alertStyles.textClass}`}>
                            {alert.message || 'Alert'}
                          </span>
                          <div className="flex items-center gap-2">
                            <span className="text-xs text-gray-500">
                              {alert.timestamp ? new Date(alert.timestamp).toLocaleString() : ''}
                            </span>
                            <Button
                              variant="ghost"
                              size="icon"
                              className="h-6 w-6 opacity-0 group-hover/item:opacity-100 hover:bg-red-500/20 hover:text-red-400 transition-all"
                              onClick={(e) => handleDismiss(e, alert)}
                            >
                              <X className="w-3 h-3" />
                            </Button>
                          </div>
                        </div>
                      </div>
                    </div>
                  );
                })}
              </div>
            </DialogContent>
          </Dialog>

          {/* Dismiss Button (Ticker View) */}
          <Button
            variant="ghost"
            size="icon"
            className="h-6 w-6 hover:bg-red-500/20 hover:text-red-400 border-l border-gray-800 ml-1"
            onClick={(e) => handleDismiss(e, currentAlert)}
            title="Dismiss alert"
          >
            <X className="w-3 h-3" />
          </Button>
        </div>
      </div>

      {/* Progress Bar */}
      {alerts.length > 1 && !isPaused && (
        <div className="absolute bottom-0 left-0 h-0.5 bg-gray-800 w-full rounded-b-lg overflow-hidden">
          <div
            key={currentIndex} // Reset animation on index change
            className="h-full bg-teal-500/50 animate-progress origin-left"
            style={{ animationDuration: '4000ms' }}
          />
        </div>
      )}
    </div>
  );
};

export default ActiveAlertsTicker;
