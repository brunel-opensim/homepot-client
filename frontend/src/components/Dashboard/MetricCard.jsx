import React from 'react';
import { Cpu, Globe } from 'lucide-react';

const OsIcon = ({ type }) => {
  const iconBase = 'w-5 h-5';
  switch (type) {
    case 'windows':
      return (
        <img
          src="https://cdn.jsdelivr.net/gh/simple-icons/simple-icons/icons/windows.svg"
          className={iconBase}
          style={{
            filter:
              'invert(47%) sepia(100%) saturate(5000%) hue-rotate(180deg) brightness(95%) contrast(105%)',
          }}
          alt="Windows"
        />
      );
    case 'apple':
    case 'macos':
    case 'ios':
    case 'darwin':
      return (
        <img
          src="https://cdn.jsdelivr.net/gh/simple-icons/simple-icons/icons/apple.svg"
          className={iconBase}
          style={{ filter: 'invert(80%) grayscale(100%)' }}
          alt="Apple"
        />
      );
    case 'linux':
    case 'ubuntu':
    case 'debian':
      return (
        <img
          src="https://cdn.jsdelivr.net/gh/simple-icons/simple-icons/icons/linux.svg"
          className={iconBase}
          style={{ filter: 'invert(100%)' }}
          alt="Linux"
        />
      );
    case 'android':
      return (
        <img
          src="https://cdn.jsdelivr.net/gh/simple-icons/simple-icons/icons/android.svg"
          className={iconBase}
          style={{
            filter: 'invert(65%) sepia(50%) saturate(500%) hue-rotate(60deg)',
          }}
          alt="Android"
        />
      );
    case 'web':
      return <Globe className={`${iconBase} text-blue-400`} />;
    case 'iot':
    default:
      return <Cpu className={`${iconBase} text-blue-400`} />;
  }
};

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
