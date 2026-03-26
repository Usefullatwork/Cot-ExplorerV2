/**
 * Mini sparkline factory using lightweight-charts.
 *
 * Creates a tiny inline area chart for embedding in cards / table cells.
 * Hover shows the value at cursor position in a minimal tooltip.
 */

import { createChart, ColorType } from 'lightweight-charts';

/**
 * Create a sparkline chart inside the given container.
 * @param {HTMLElement} container  Should have explicit width/height (e.g. 80x30)
 * @param {{ time: string, value: number }[]} data  Sorted ascending
 * @param {string} [color='#3fb950']  Line/fill color
 * @returns {{ chart: IChartApi, series: ISeriesApi }}
 */
export function createSparkline(container, data, color = '#3fb950') {
  const w = container.clientWidth || 80;
  const h = container.clientHeight || 30;

  const chart = createChart(container, {
    width: w,
    height: h,
    layout: {
      background: { type: ColorType.Solid, color: 'transparent' },
      textColor: 'transparent',
    },
    grid: {
      vertLines: { visible: false },
      horzLines: { visible: false },
    },
    crosshair: { mode: 0 },
    rightPriceScale: { visible: false },
    timeScale: { visible: false },
    handleScroll: false,
    handleScale: false,
  });

  const series = chart.addAreaSeries({
    lineColor: color,
    topColor: color.replace(')', ',0.18)').replace('rgb', 'rgba'),
    bottomColor: 'transparent',
    lineWidth: 1,
    crosshairMarkerVisible: true,
    crosshairMarkerRadius: 3,
    crosshairMarkerBorderColor: color,
    crosshairMarkerBackgroundColor: '#161b22',
    priceLineVisible: false,
    lastValueVisible: false,
  });

  if (data && data.length) {
    series.setData(data);
    chart.timeScale().fitContent();
  }

  // Minimal hover tooltip for sparkline
  const tip = document.createElement('div');
  tip.style.cssText =
    'position:absolute;top:-18px;right:0;z-index:5;pointer-events:none;' +
    'font-family:"DM Mono",monospace;font-size:9px;color:#e6edf3;' +
    'background:#1c2128;border:1px solid #30363d;border-radius:3px;padding:1px 4px;display:none;';
  container.style.position = 'relative';
  container.appendChild(tip);

  chart.subscribeCrosshairMove((param) => {
    if (!param.time || !param.seriesData?.size) {
      tip.style.display = 'none';
      return;
    }
    const price = param.seriesData.get(series);
    if (price == null || price.value == null) {
      tip.style.display = 'none';
      return;
    }
    tip.textContent = price.value > 100 ? price.value.toFixed(1) : price.value.toFixed(4);
    tip.style.display = 'block';
  });

  return { chart, series };
}
