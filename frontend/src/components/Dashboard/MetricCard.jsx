import React from 'react';
import OsIcon from '@/components/common/OsIcon';

const MetricCard = ({ sites, onItemClick }) => {
  return (
    <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-2 mt-2 w-full">
      {sites.map((s, i) => {
        // Assume 'site' type if not specified
        const isSite = s.type === 'site';

        return (
          <div
            key={i}
            onClick={() => onItemClick && onItemClick(s)}
            className={`
              p-2 rounded-lg border border-primary bg-gray-800/90 hover:bg-gray-800 transition-colors cursor-pointer
              ${isSite ? 'col-span-2' : 'col-span-1'}
            `}
          >
            <div className="flex justify-between items-start">
              <div className="flex-1 min-w-0 pr-2">
                <h3 className="text-sm text-text font-semibold mb-0.5 truncate" title={s.site}>
                  {s.site}
                </h3>
                <p className="text-[10px] font-mono text-teal-400/80 mb-0.5 truncate" title={s.id}>
                  {s.id}
                </p>
                <p
                  className={`text-xs text-start mb-0.5 ${
                    !isSite && s.online === 0 ? 'text-gray-400' : 'text-green-400'
                  }`}
                >
                  {isSite ? `${s.online} Online` : s.online > 0 ? 'Online' : 'Offline'}
                </p>
                <p className="text-[10px] text-start text-gray-400">Last Alert: {s.alert}</p>
              </div>

              {/* Icons Section */}
              <div
                className={`flex gap-1 ${
                  isSite ? 'flex-wrap justify-end max-w-[50%]' : 'shrink-0'
                }`}
              >
                {s.osList && s.osList.length > 0 ? (
                  s.osList.map((os, idx) => <OsIcon key={idx} type={os} />)
                ) : s.icon ? (
                  s.icon
                ) : (
                  <OsIcon type="iot" />
                )}
              </div>
            </div>
          </div>
        );
      })}
    </div>
  );
};

export default MetricCard;
