function App() {
  return (
    <div className="min-h-screen bg-slate-900 text-slate-100 flex flex-col items-center justify-center p-4 font-sans">
      <div className="w-full max-w-sm bg-slate-800 rounded-2xl shadow-2xl border border-slate-700 p-8 flex flex-col items-center gap-8">
        
        {/* Header */}
        <h1 className="text-lg font-semibold text-slate-300">HOMEPOT Agent</h1>

        {/* The "Digital Badge" Status Ring */}
        <div className="w-40 h-40 rounded-full border-8 border-emerald-500 flex items-center justify-center bg-slate-900 shadow-[0_0_30px_rgba(16,185,129,0.2)]">
          <span className="text-emerald-500 font-bold tracking-wider">SECURE</span>
        </div>

        {/* User Identity Placeholder */}
        <div className="flex flex-col items-center mt-2">
          <div className="w-12 h-12 bg-slate-700 rounded-full flex items-center justify-center mb-3">
             <span className="text-xl">👤</span>
          </div>
          <h2 className="text-xl font-medium">Employee Name</h2>
          <p className="text-sm text-slate-400 mt-1">Device linked &amp; compliant</p>
        </div>

        {/* Action Buttons Placeholder */}
        <div className="w-full flex flex-col gap-3 mt-4">
          <button className="w-full py-3 px-4 bg-teal-600 hover:bg-teal-500 text-white font-medium rounded-lg transition-colors">
            Sync Now
          </button>
          <button className="w-full py-3 px-4 bg-slate-700 hover:bg-slate-600 text-white font-medium rounded-lg transition-colors">
            Corporate Files
          </button>
        </div>

        {/* Developer Note */}
        <div className="mt-4 text-xs text-slate-500 text-center border-t border-slate-700 pt-4 w-full">
          GetFudo: Connect this UI to Dealdio's IPC Layer.
        </div>

      </div>
    </div>
  )
}

export default App
