export function formatUptime(seconds) {
  if (!seconds) return '0s';
  const days = Math.floor(seconds / 86400);
  const hours = Math.floor((seconds % 86400) / 3600);
  if (days > 0) return `${days}d ${hours}h`;
  const minutes = Math.floor((seconds % 3600) / 60);
  return `${hours}h ${minutes}m`;
}

export function buildStatsFromMetrics(metricsData) {
  if (!metricsData || metricsData.length === 0) return null;

  const latest = metricsData[0];
  const cpuTrend = metricsData.map((m) => m.cpu_percent).reverse();
  const memTrend = metricsData.map((m) => m.memory_percent).reverse();
  const diskTrend = metricsData.map((m) => m.disk_percent).reverse();
  const netTrend = metricsData.map((m) => m.network_latency_ms).reverse();
  // Disk % usage is a slow-moving gauge; its sparkline shows real disk I/O
  // throughput (bytes/s) when the agent reports it, so the trend stays honest
  // and visible instead of a perpetually flat line.
  const diskIoTrend = metricsData
    .map((m) => m.extra_metrics?.disk_io_bytes_s ?? m.disk_io_bytes_s ?? null)
    .reverse();
  const hasDiskIO = diskIoTrend.some((v) => typeof v === 'number' && Number.isFinite(v));

  // Extract uptime from extra_metrics if available
  const currentUptime = latest.extra_metrics?.uptime_seconds || 0;
  const uptimeTrend = metricsData.map((m) => m.extra_metrics?.uptime_seconds || 0).reverse();

  return {
    cpu: {
      label: 'CPU',
      value: `${latest.cpu_percent?.toFixed(1) || 0}%`,
      subtitle: 'current load',
      data: cpuTrend,
    },
    memory: {
      label: 'Memory',
      value: `${latest.memory_percent?.toFixed(1) || 0}%`,
      subtitle: 'utilization',
      data: memTrend,
    },
    disk: {
      label: 'Disk',
      value: `${latest.disk_percent?.toFixed(1) || 0}%`,
      subtitle: 'usage',
      data: hasDiskIO ? diskIoTrend : diskTrend,
    },
    network: {
      label: 'Network',
      value: `${latest.network_latency_ms?.toFixed(0) || 0}ms`,
      subtitle: 'latency',
      data: netTrend,
    },
    uptime: {
      label: 'Uptime',
      value: formatUptime(currentUptime),
      subtitle: 'system up',
      data: uptimeTrend,
    },
  };
}
