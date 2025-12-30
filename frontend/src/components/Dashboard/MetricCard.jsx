const MetricCard = ({ sites }) => {
  return (
    <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-4 mt-4 w-full">
      {sites.map((s, i) => (
        <div
          key={i}
          className="w-full p-3 rounded-xl border border-primary bg-gray-800/90 hover:bg-gray-800 transition-colors"
        >
          <div className="flex justify-between items-center">
            <h3 className="text-md text-text font-semibold mb-1 truncate pr-2" title={s.site}>
              {s.site}
            </h3>
            <div className="shrink-0">{s.icon}</div>
          </div>
          <p className="text-sm text-start text-green-400 mb-1">{s.online} Online</p>
          <p className="text-xs text-start text-gray-400">Last Alert: {s.alert}</p>
        </div>
      ))}
    </div>
  );
};

export default MetricCard;
