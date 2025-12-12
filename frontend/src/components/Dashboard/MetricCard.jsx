const MetricCard = ({ sites }) => {
  return (
    <div className="grid grid-cols-2 md:grid-cols-4 gap-6 mt-4 z-10 flex-1 justify-items-center items-center">
      {sites.map((s, i) => (
        <div key={i} className="w-40 p-3 rounded-xl border border-primary bg-gray-800/90">
          <div className="flex justify-between items-center">
            <h3 className="text-md text-text font-semibold mb-1">{s.site}</h3>
            {s.icon}
          </div>
          <p className="text-sm text-start text-green-400 mb-1">{s.online} Online</p>
          <p className="text-xs text-start text-gray-400">Last Alert: {s.alert}</p>
        </div>
      ))}
    </div>
  );
};

export default MetricCard;
