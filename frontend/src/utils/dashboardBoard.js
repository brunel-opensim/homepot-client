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
  const siteDeviceIds = new Map(
    sites.map((s) => [
      s.site_id,
      new Set(
        devices
          .filter((d) => d.site_id === s.site_id)
          .map((d) => d.device_id)
      ),
    ])
  );

  const keyOf = (item) => {
    const matching = anomalies.filter((a) =>
      item._type === 'site'
        ? (siteDeviceIds.get(item.site_id) || new Set()).has(a.device_id)
        : a.device_id === item.device_id
    );
    let rank = 4;
    let latest = '';
    for (const a of matching) {
      const r = severityRank(a.severity);
      if (r < rank) rank = r;
      if (a.timestamp && a.timestamp > latest) latest = a.timestamp;
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