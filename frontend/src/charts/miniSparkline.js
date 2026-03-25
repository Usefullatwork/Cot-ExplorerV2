/**
 * Mini sparkline factory using lightweight-charts.
 *
 * Creates a tiny inline area chart for embedding in cards / table cells.
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
    crosshairMarkerVisible: false,
    priceLineVisible: false,
    lastValueVisible: false,
  });

  if (data && data.length) {
    series.setData(data);
    chart.timeScale().fitContent();
  }

  return { chart, series };
}
