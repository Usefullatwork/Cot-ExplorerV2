/**
 * SVG sparkline renderer — lightweight inline sparklines.
 *
 * Zero dependencies. Returns an SVG string for embedding in innerHTML templates.
 * Default size: 60x20px. Color auto-detected from trend direction.
 */

/**
 * Render an inline SVG sparkline from a values array.
 * @param {number[]} values  Data points (oldest first)
 * @param {Object} [opts]
 * @param {number} [opts.width=60]   SVG width in px
 * @param {number} [opts.height=20]  SVG height in px
 * @param {string} [opts.color]      Line color (auto if omitted: green for up, red for down)
 * @param {number} [opts.strokeWidth=1.5]  Line width
 * @param {boolean} [opts.fill=true]  Show area fill below line
 * @returns {string}  SVG markup string
 */
export function renderSparkline(values, opts = {}) {
  if (!values || values.length < 2) return '';

  const w = opts.width || 60;
  const h = opts.height || 20;
  const sw = opts.strokeWidth || 1.5;
  const pad = 2;

  const min = Math.min(...values);
  const max = Math.max(...values);
  const range = max - min || 1;

  // Auto-detect color from trend
  const trend = values[values.length - 1] - values[0];
  const color = opts.color || (trend >= 0 ? '#3fb950' : '#f85149');
  const fillColor = opts.fill !== false
    ? color.replace('#', '').length === 6
      ? color + '33'
      : 'rgba(127,127,127,0.2)'
    : 'none';

  // Generate points
  const points = values.map((v, i) => {
    const x = pad + (i / (values.length - 1)) * (w - 2 * pad);
    const y = pad + (1 - (v - min) / range) * (h - 2 * pad);
    return `${x.toFixed(1)},${y.toFixed(1)}`;
  });

  const polyline = points.join(' ');

  // Area fill polygon (line + bottom edge)
  const fillPath = opts.fill !== false
    ? `<polygon points="${polyline} ${(w - pad).toFixed(1)},${(h - pad).toFixed(1)} ${pad.toFixed(1)},${(h - pad).toFixed(1)}" fill="${fillColor}" />`
    : '';

  return `<svg width="${w}" height="${h}" viewBox="0 0 ${w} ${h}" style="display:inline-block;vertical-align:middle" aria-hidden="true">${fillPath}<polyline points="${polyline}" fill="none" stroke="${color}" stroke-width="${sw}" stroke-linecap="round" stroke-linejoin="round" /></svg>`;
}

/**
 * Render score breakdown dots — filled (pass) or empty (fail).
 * @param {Array<{kryss: string, verdi: boolean}>} details  Score detail items
 * @param {Object} [opts]
 * @param {number} [opts.size=8]  Dot diameter in px
 * @returns {string}  HTML string of dots with tooltips
 */
export function renderScoreDots(details, opts = {}) {
  if (!details || !details.length) return '';
  const size = opts.size || 8;
  return details
    .map(
      (d) =>
        `<span title="${d.kryss || ''}" style="display:inline-block;width:${size}px;height:${size}px;border-radius:50%;background:${d.verdi ? 'var(--bull)' : 'var(--b2)'};margin:0 1px;cursor:help" aria-label="${d.kryss || ''}: ${d.verdi ? 'pass' : 'fail'}"></span>`
    )
    .join('');
}
