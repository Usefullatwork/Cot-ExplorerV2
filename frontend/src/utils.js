/**
 * Format a large number with K/M suffix.
 * @param {number|null} n
 * @returns {string}
 */
export function formatNumber(n) {
  if (n == null) return '-';
  const a = Math.abs(n);
  if (a >= 1e6) return (n > 0 ? '' : '-') + (a / 1e6).toFixed(2) + 'M';
  if (a >= 1e3) return (n > 0 ? '' : '-') + (a / 1e3).toFixed(1) + 'K';
  return String(Math.round(n));
}

/**
 * Format a percentage with sign.
 * @param {number} n
 * @returns {string}
 */
export function formatPct(n) {
  return (n > 0 ? '+' : '') + n.toFixed(2) + '%';
}

/**
 * Return a CSS utility class name based on sign.
 * @param {number} n
 * @returns {'bull'|'bear'|'neutral'}
 */
export function colorClass(n) {
  return n > 0 ? 'bull' : n < 0 ? 'bear' : 'neutral';
}

/**
 * Format a price value — 2 decimals for large, 5 for small (FX).
 * @param {number|null} v
 * @returns {string}
 */
export function formatPrice(v) {
  if (!v) return '-';
  return v > 100 ? v.toFixed(2) : v.toFixed(5);
}

/**
 * Human-friendly relative time string.
 * @param {string|Date} date  ISO date string or Date object
 * @returns {string}
 */
export function timeAgo(date) {
  const now = Date.now();
  const then = date instanceof Date ? date.getTime() : new Date(date).getTime();
  const diff = Math.max(0, now - then);

  const seconds = Math.floor(diff / 1000);
  if (seconds < 60) return 'naa';

  const minutes = Math.floor(seconds / 60);
  if (minutes < 60) return minutes + ' min siden';

  const hours = Math.floor(minutes / 60);
  if (hours < 24) return hours + 't siden';

  const days = Math.floor(hours / 24);
  return days + 'd siden';
}
