import { describe, it, expect } from 'vitest';
import { buildStatsFromMetrics } from './deviceStats';

const sample = (i, io) => ({
  cpu_percent: 10 + i,
  memory_percent: 55,
  disk_percent: 4.6,
  network_latency_ms: 5,
  extra_metrics: {
    uptime_seconds: 1000 + i,
    ...(io != null ? { disk_io_bytes_s: io } : {}),
  },
});

describe('buildStatsFromMetrics disk card', () => {
  it('keeps the 4.6% headline while sparklining disk I/O when available', () => {
    const stats = buildStatsFromMetrics([20, 19, 18, 17].map((io, i) => sample(i, io)));
    expect(stats.disk.value).toBe('4.6%');
    expect(stats.disk.data).toEqual([17, 18, 19, 20]);
  });

  it('falls back to the disk_percent series when no disk I/O data exists', () => {
    const stats = buildStatsFromMetrics([0, 1, 2, 3].map((i) => sample(i, null)));
    expect(stats.disk.data).toEqual([4.6, 4.6, 4.6, 4.6]);
  });

  it('returns null for empty metrics', () => {
    expect(buildStatsFromMetrics([])).toBeNull();
    expect(buildStatsFromMetrics(undefined)).toBeNull();
  });
});
