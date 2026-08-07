import React from 'react';
import { Cpu, Globe } from 'lucide-react';

const SIMPLE_ICONS_CDN = 'https://cdn.jsdelivr.net/gh/simple-icons/simple-icons/icons';

const BRAND_FILTER =
  'invert(86%) sepia(36%) saturate(319%) hue-rotate(122deg) brightness(99%) contrast(98%)';

const OsIcon = ({ type, size = 'w-5 h-5' }) => {
  switch (type) {
    case 'windows':
      return (
        <img
          src={`${SIMPLE_ICONS_CDN}/windows.svg`}
          alt="Windows"
          className={size}
          style={{ filter: BRAND_FILTER }}
        />
      );
    case 'apple':
    case 'macos':
    case 'ios':
    case 'darwin':
      return (
        <img
          src={`${SIMPLE_ICONS_CDN}/apple.svg`}
          alt="Apple"
          className={size}
          style={{ filter: BRAND_FILTER }}
        />
      );
    case 'linux':
    case 'ubuntu':
    case 'debian':
      return (
        <img
          src={`${SIMPLE_ICONS_CDN}/linux.svg`}
          alt="Linux"
          className={size}
          style={{ filter: BRAND_FILTER }}
        />
      );
    case 'android':
      return (
        <img
          src={`${SIMPLE_ICONS_CDN}/android.svg`}
          alt="Android"
          className={size}
          style={{ filter: BRAND_FILTER }}
        />
      );
    case 'web':
      return <Globe className={`${size} text-blue-400`} />;
    case 'iot':
    default:
      return <Cpu className={`${size} text-blue-400`} />;
  }
};

export default OsIcon;
