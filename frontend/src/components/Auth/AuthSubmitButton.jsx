import React from 'react';

export default function AuthSubmitButton({ activeTab, loading, loadingText, children }) {
  return (
    <button
      type="submit"
      disabled={loading}
      className={`w-full font-bold py-4 px-6 rounded-xl transition-all duration-300 transform hover:scale-[1.02] focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-offset-gray-900 shadow-lg disabled:opacity-60 disabled:cursor-not-allowed flex justify-center items-center gap-2 ${
        activeTab === 'ENGINEER'
          ? 'bg-indigo-600 hover:bg-indigo-500 focus:ring-indigo-500 shadow-indigo-900/20'
          : 'bg-teal-600 hover:bg-teal-500 focus:ring-teal-500 shadow-teal-900/20'
      }`}
    >
      {loading ? (
        <>
          <svg
            className="animate-spin -ml-1 mr-2 h-5 w-5 text-white"
            xmlns="http://www.w3.org/2000/svg"
            fill="none"
            viewBox="0 0 24 24"
          >
            <circle
              className="opacity-25"
              cx="12"
              cy="12"
              r="10"
              stroke="currentColor"
              strokeWidth="4"
            ></circle>
            <path
              className="opacity-75"
              fill="currentColor"
              d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"
            ></path>
          </svg>
          {loadingText}
        </>
      ) : (
        children
      )}
    </button>
  );
}
