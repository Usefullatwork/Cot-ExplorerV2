/**
 * Lightweight SVG bar chart renderer.
 *
 * Vertical bars with optional labels. Zero dependencies.
 * Returns SVG string for innerHTML embedding.
 */

/**
 * Render a vertical bar chart.
 * @param {Array<{label: string, value: number, color?: string}>} data  Bar data
 * @param {Object} [opts]
 * @param {number} [opts.width=400]   SVG width
 * @param {number} [opts.height=200]  SVG height
 * @param {number} [opts.barGap=4]    Gap between bars
 * @param {string} [opts.defaultColor='var(--bull)']  Default bar color
 * @param {boolean} [opts.showLabels=true]  Show labels below bars
 * @param {boolean} [opts.showValues=true]  Show values above bars
 * @returns {string}  SVG markup
 */
export function renderBarChart(data, opts = {}) {
  if (!data || !data.length) return '';

  const w = opts.width || 400;
  const h = opts.height || 200;
  const gap = opts.barGap || 4;
  const showLabels = opts.showLabels !== false;
  const showValues = opts.showValues !== false;
  const labelH = showLabels ? 20 : 0;
  const valueH = showValues ? 16 : 0;
  const chartH = h - labelH - valueH - 4;
  const defaultColor = opts.defaultColor || 'var(--bull)';

  const maxVal = Math.max(...data.map((d) => Math.abs(d.value)), 0.001);
  const barW = Math.max(2, (w - gap * (data.length + 1)) / data.length);

  const bars = data.map((d, i) => {
    const x = gap + i * (barW + gap);
    const barH = Math.max(1, (Math.abs(d.value) / maxVal) * chartH);
    const y = valueH + chartH - barH;
    const color = d.color || (d.value >= 0 ? defaultColor : 'var(--bear)');

    let label = '';
    if (showLabels) {
      label = `<text x="${x + barW / 2}" y="${h - 2}" text-anchor="middle" fill="var(--m)" font-size="9" font-family="'DM Mono',monospace">${d.label || ''}</text>`;
    }

    let valueText = '';
    if (showValues) {
      const fmt = Math.abs(d.value) >= 100 ? d.value.toFixed(0) : d.value.toFixed(1);
      valueText = `<text x="${x + barW / 2}" y="${y - 2}" text-anchor="middle" fill="${color}" font-size="9" font-family="'DM Mono',monospace">${fmt}</text>`;
    }

    return `<rect x="${x}" y="${y}" width="${barW}" height="${barH}" rx="2" fill="${color}" />` + valueText + label;
  });

  return `<svg width="${w}" height="${h}" viewBox="0 0 ${w} ${h}" style="display:block" aria-hidden="true">${bars.join('')}</svg>`;
}
