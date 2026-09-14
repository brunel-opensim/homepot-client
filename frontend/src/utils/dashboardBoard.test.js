import { describe, it, expect } from 'vitest';
import {
  MAX_AUTO_MONITORED_CARDS,
  severityRank,
  buildMonitoredBoard,
} from './dashboardBoard';

const device = (device_id, site_id = 'SITE-1', extra = {}) => ({
  _type: 'device',
  device_id,
  site_id,
  name: device_id,
  ...extra,
});

const site = (site_id, extra = {}) => ({
  _type: 'site',
  site_id,
  name: site_id,
  ...extra,
});

const anomaly = (device_id, severity, timestamp = '2026-09-14T08:00:00Z') => ({
  device_id,
  severity,
  timestamp,
});

describe('severityRank', () => {
  it('ranks critical and high as most urgent', () => {
    expect(severityRank('critical')).toBe(0);
    expect(severityRank('high')).toBe(0);
  });

  it('ranks warning above medium, low and info', () => {
    expect(severityRank('warning')).toBe(1);
    expect(severityRank('medium')).toBe(2);
    expect(severityRank('low')).toBe(3);
    expect(severityRank('info')).toBe(4);
  });

  it('treats unknown severities as least urgent', () => {
    expect(severityRank('fatal')).toBe(4);
    expect(severityRank(undefined)).toBe(4);
  });
});

describe('buildMonitoredBoard', () => {
  const devices = [
    device('D-CRIT', 'SITE-A'),
    device('D-WARN', 'SITE-A'),
    device('D-SILENT', 'SITE-B'),
    device('D-CRIT-OLD', 'SITE-B'),
  ];
  const sites = [
    { site_id: 'SITE-A', name: 'Site A' },
    { site_id: 'SITE-B', name: 'Site B' },
  ];
  const anomalies = [
    anomaly('D-CRIT', 'critical', '2026-09-14T09:00:00Z'),
    anomaly('D-CRIT-OLD', 'critical', '2026-09-14T06:00:00Z'),
    anomaly('D-WARN', 'warning', '2026-09-14T08:30:00Z'),
  ];

  it('orders critical first, then warning, healthy items last', () => {
    const { items } = buildMonitoredBoard({
      items: devices,
      anomalies,
      sites,
      devices,
      maxCards: 20,
    });
    expect(items.map((d) => d.device_id)).toEqual([
      'D-CRIT',
      'D-CRIT-OLD',
      'D-WARN',
      'D-SILENT',
    ]);
  });

  it('orders same-severity items by most recent anomaly first', () => {
    const { items } = buildMonitoredBoard({
      items: [device('D-CRIT-OLD', 'SITE-B'), device('D-CRIT', 'SITE-A')],
      anomalies: [
        anomaly('D-CRIT', 'critical', '2026-09-14T09:00:00Z'),
        anomaly('D-CRIT-OLD', 'critical', '2026-09-14T06:00:00Z'),
      ],
      sites,
      devices,
      maxCards: 20,
    });
    expect(items.map((d) => d.device_id)).toEqual(['D-CRIT', 'D-CRIT-OLD']);
  });

  it('promotes a site when one of its devices is alerting', () => {
    const { items } = buildMonitoredBoard({
      items: [site('SITE-B'), site('SITE-A')],
      anomalies,
      sites,
      devices,
      maxCards: 20,
    });
    expect(items.map((s) => s.site_id)).toEqual(['SITE-A', 'SITE-B']);
  });

  it('caps the board and reports the hidden overflow', () => {
    const manyDevices = Array.from({ length: 25 }, (_, i) =>
      device(
        `D-${i}`,
        'SITE-A',
        i < 3 ? { _alerted: true } : {}
      )
    );
    const { items, hidden } = buildMonitoredBoard({
      items: manyDevices,
      anomalies: [anomaly('D-0', 'critical')],
      sites,
      devices: manyDevices,
      maxCards: MAX_AUTO_MONITORED_CARDS,
    });
    expect(items).toHaveLength(MAX_AUTO_MONITORED_CARDS);
    expect(items[0].device_id).toBe('D-0');
    expect(hidden).toBe(5);
  });

  it('keeps every item when the fleet stays under the cap', () => {
    const { items, hidden } = buildMonitoredBoard({
      items: devices,
      anomalies,
      sites,
      devices,
      maxCards: 20,
    });
    expect(items).toHaveLength(devices.length);
    expect(hidden).toBe(0);
  });
});