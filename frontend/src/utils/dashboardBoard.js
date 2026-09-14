/**
 * Ordering and bounding for the Dashboard "Monitored Resources" board.
 *
 * HOMEPOT auto-adds any device with an active alert to the dashboard so the
 * technician can see it. On a fleet-wide incident that set can be huge, so we
 * sort the board by urgency (active alerts first, critical before warning,
 * then most recent) and cap how many cards render at once. The overflow count
 * is surfaced instead of unbounded cards.
 */

export const MAX_AUTO_MONITORED_CARDS = 20;

const SEVERITY_RANK = { critical: 0, high: 0, warning: 1, medium: 2, low: 3, info: 4 };

/**
 * Rank a severity string for urgency ordering.
 * Unknown severities are treated as least urgent.
 */
export const severityRank = (severity) => SEVERITY_RANK[severity] ?? 4;

/**
 * Build the bounded, urgency-ordered board for the monitored resources list.
 *
 * @param {Object} opts
 * @param {Array}    opts.items     Monitored sites + devices (with `_type`, `site_id`/`device_id`)
 * @param {Array}    opts.anomalies Active alerts / anomalies from the AI feed
 * @param {Array}    opts.sites     All fetched sites
 * @param {Array}    opts.devices   All fetched devices
 * @param {number}   [opts.maxCards] Number of cards to keep
 * @returns {{ items: Array, hidden: number }}
 */
export const buildMonitoredBoard = ({
  items,
  anomalies,
  sites,
  devices,
  maxCards = MAX_AUTO_MONITORED_CARDS,
}) => {
  const siteDeviceIds = new Map(sites.map((s) => [s.site_id, new Set()]));
  for (const device of devices) {
    if (!siteDeviceIds.has(device.site_id)) siteDeviceIds.set(device.site_id, new Set());
    siteDeviceIds.get(device.site_id).add(device.device_id);
  }

  const anomalySummaryByDevice = new Map();
  for (const anomaly of anomalies) {
    const summary = anomalySummaryByDevice.get(anomaly.device_id) || { rank: 4, latest: '' };
    const rank = severityRank(anomaly.severity);
    anomalySummaryByDevice.set(anomaly.device_id, {
      rank: Math.min(summary.rank, rank),
      latest:
        anomaly.timestamp && anomaly.timestamp > summary.latest
          ? anomaly.timestamp
          : summary.latest,
    });
  }

  const keyOf = (item) => {
    if (item._type !== 'site') {
      return anomalySummaryByDevice.get(item.device_id) || { rank: 4, latest: '' };
    }

    let rank = 4;
    let latest = '';
    for (const deviceId of siteDeviceIds.get(item.site_id) || []) {
      const summary = anomalySummaryByDevice.get(deviceId);
      if (!summary) continue;
      if (summary.rank < rank) rank = summary.rank;
      if (summary.latest > latest) latest = summary.latest;
    }
    return { rank, latest };
  };

  const sorted = items
    .map((item) => ({ item, key: keyOf(item) }))
    .sort((a, b) => {
      if (a.key.rank !== b.key.rank) return a.key.rank - b.key.rank;
      if (a.key.latest !== b.key.latest) return a.key.latest > b.key.latest ? -1 : 1;
      return 0;
    })
    .map((entry) => entry.item);

  return {
    items: sorted.slice(0, maxCards),
    hidden: Math.max(0, sorted.length - maxCards),
  };
};
