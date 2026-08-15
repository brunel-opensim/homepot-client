import React from 'react';

const TABS = [
  {
    key: 'ENGINEER',
    iconPath: 'M10 20l4-16m4 4l4 4-4 4M6 16l-4-4 4-4',
    activeClass: 'bg-indigo-600 text-white shadow-lg shadow-indigo-500/20 ring-1 ring-white/10',
    activeIconClass: 'text-indigo-200',
  },
  {
    key: 'CLIENT',
    iconPath:
      'M3 12l2-2m0 0l7-7 7 7M5 10v10a1 1 0 001 1h3m10-11l2 2m-2-2v10a1 1 0 01-1 1h-3m-6 0a1 1 0 001-1v-4a1 1 0 011-1h2a1 1 0 011 1v4a1 1 0 001 1m-6 0h6',
    activeClass: 'bg-teal-600 text-white shadow-lg shadow-teal-500/20 ring-1 ring-white/10',
    activeIconClass: 'text-teal-200',
  },
];

export default function RoleTabs({ activeTab, setActiveTab }) {
  return (
    <div className="text-center mb-8">
      <div className="flex rounded-xl bg-gray-800/50 p-1 border border-gray-700/50 relative">
        {TABS.map((tab) => (
          <button
            key={tab.key}
            type="button"
            onClick={() => setActiveTab(tab.key)}
            className={`flex-1 py-3 px-6 text-sm font-bold rounded-lg transition-all duration-300 flex items-center justify-center gap-2 ${
              activeTab === tab.key
                ? tab.activeClass
                : 'text-gray-400 hover:text-gray-200 hover:bg-white/5'
            }`}
          >
            <svg
              className={`w-4 h-4 ${activeTab === tab.key ? tab.activeIconClass : 'text-gray-500'}`}
              fill="none"
              stroke="currentColor"
              viewBox="0 0 24 24"
            >
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d={tab.iconPath} />
            </svg>
            {tab.key}
          </button>
        ))}
      </div>
    </div>
  );
}
