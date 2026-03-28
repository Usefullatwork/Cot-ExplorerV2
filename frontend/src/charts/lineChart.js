/**
 * Lightweight SVG line chart renderer.
 *
 * Line with optional gradient fill area. Zero dependencies.
 * Returns SVG string for innerHTML embedding.
 */

/**
 * Render a line chart with optional area fill.
 * @param {number[]} values  Data points (oldest first)
 * @param {Object} [opts]
 * @param {number} [opts.width=400]   SVG width
 * @param {number} [opts.height=200]  SVG height
 * @param {string} [opts.color]       Line color (auto: green/red based on trend)
 * @param {number} [opts.strokeWidth=2]  Line width
 * @param {boolean} [opts.fill=true]  Show area fill below line
 * @param {boolean} [opts.dots=false]  Show dots at data points
 * @param {string[]} [opts.labels]    X-axis labels (same length as values)
 * @returns {string}  SVG markup
 */
export function renderLineChart(values, opts = {}) {
  if (!values || values.length < 2) return '';

  const w = opts.width || 400;
  const h = opts.height || 200;
  const sw = opts.strokeWidth || 2;
  const pad = { top: 10, right: 10, bottom: opts.labels ? 20 : 10, left: 10 };

  const chartW = w - pad.left - pad.right;
  const chartH = h - pad.top - pad.bottom;

  const min = Math.min(...values);
  const max = Math.max(...values);
  const range = max - min || 1;

  const trend = values[values.length - 1] - values[0];
  const color = opts.color || (trend >= 0 ? '#3fb950' : '#f85149');
  const fillId = 'lc_fill_' + Math.random().toString(36).slice(2, 8);

  const points = values.map((v, i) => {
    const x = pad.left + (i / (values.length - 1)) * chartW;
    const y = pad.top + (1 - (v - min) / range) * chartH;
    return { x, y };
  });

  const pathD = points.map((p, i) => `${i === 0 ? 'M' : 'L'}${p.x.toFixed(1)},${p.y.toFixed(1)}`).join(' ');

  const fill = opts.fill !== false
    ? `<defs><linearGradient id="${fillId}" x1="0" y1="0" x2="0" y2="1"><stop offset="0%" stop-color="${color}" stop-opacity="0.3"/><stop offset="100%" stop-color="${color}" stop-opacity="0.02"/></linearGradient></defs><path d="${pathD} L${points[points.length - 1].x.toFixed(1)},${(h - pad.bottom).toFixed(1)} L${points[0].x.toFixed(1)},${(h - pad.bottom).toFixed(1)} Z" fill="url(#${fillId})" />`
    : '';

  const dots = opts.dots
    ? points.map((p) => `<circle cx="${p.x.toFixed(1)}" cy="${p.y.toFixed(1)}" r="3" fill="${color}" />`).join('')
    : '';

  const labels = opts.labels
    ? opts.labels.map((l, i) => {
        if (i % Math.ceil(values.length / 8) !== 0) return '';
        const x = pad.left + (i / (values.length - 1)) * chartW;
        return `<text x="${x.toFixed(1)}" y="${h - 2}" text-anchor="middle" fill="var(--m)" font-size="9" font-family="'DM Mono',monospace">${l}</text>`;
      }).join('')
    : '';

  return `<svg width="${w}" height="${h}" viewBox="0 0 ${w} ${h}" style="display:block" aria-hidden="true">${fill}<path d="${pathD}" fill="none" stroke="${color}" stroke-width="${sw}" stroke-linecap="round" stroke-linejoin="round" />${dots}${labels}</svg>`;
}
