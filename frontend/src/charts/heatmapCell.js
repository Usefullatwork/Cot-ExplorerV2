/**
 * Heatmap cell utility — returns a colored background for a value within a range.
 *
 * Used for correlation matrices and analytics tables.
 * Zero dependencies.
 */

/**
 * Get a heatmap background color for a value.
 * @param {number} value  The value to colorize
 * @param {number} [min=-1]  Minimum value (maps to red)
 * @param {number} [max=1]   Maximum value (maps to green)
 * @returns {string}  CSS background color string
 */
export function heatmapColor(value, min = -1, max = 1) {
  const range = max - min || 1;
  const normalized = Math.max(0, Math.min(1, (value - min) / range));

  // Red (0) -> Yellow (0.5) -> Green (1)
  let r, g;
  if (normalized < 0.5) {
    r = 248;
    g = Math.round(81 + (normalized / 0.5) * (210 - 81));
  } else {
    r = Math.round(210 - ((normalized - 0.5) / 0.5) * (210 - 63));
    g = Math.round(153 + ((normalized - 0.5) / 0.5) * (185 - 153));
  }

  return `rgba(${r},${g},${r < 100 ? 80 : 50},0.25)`;
}

/**
 * Render a heatmap cell HTML string.
 * @param {number} value  Display value
 * @param {number} [min=-1]
 * @param {number} [max=1]
 * @param {string} [format]  'pct' for percentage, 'decimal' for 2-decimal
 * @returns {string}  HTML string for a table cell
 */
export function renderHeatmapCell(value, min = -1, max = 1, format = 'decimal') {
  const bg = heatmapColor(value, min, max);
  const text = format === 'pct' ? (value * 100).toFixed(0) + '%' : value.toFixed(2);
  return `<td style="background:${bg};text-align:center;font-family:'DM Mono',monospace;font-size:11px;padding:4px 6px">${text}</td>`;
}
