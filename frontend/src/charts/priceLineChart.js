/**
 * Price line chart factory using lightweight-charts.
 *
 * Creates a dark-themed area chart for price overlay in the COT modal.
 */

import { createChart, ColorType } from 'lightweight-charts';

/**
 * Create a lightweight-charts price chart inside the given container.
 * @param {HTMLElement} container  Block-level element; chart fills it
 * @param {{ time: string, value: number }[]} data  Sorted ascending by time
 * @returns {{ chart: IChartApi, series: ISeriesApi }} Handles for later disposal
 */
export function createPriceChart(container, data) {
  const chart = createChart(container, {
    width: container.clientWidth,
    height: container.clientHeight || 200,
    layout: {
      background: { type: ColorType.Solid, color: '#161b22' },
      textColor: '#7d8590',
      fontFamily: "'DM Mono', monospace",
      fontSize: 10,
    },
    grid: {
      vertLines: { color: '#21262d' },
      horzLines: { color: '#21262d' },
    },
    crosshair: { mode: 0 },
    rightPriceScale: { borderColor: '#21262d' },
    timeScale: { borderColor: '#21262d' },
  });

  const series = chart.addAreaSeries({
    lineColor: 'rgba(255,255,255,0.8)',
    topColor: 'rgba(255,255,255,0.12)',
    bottomColor: 'rgba(255,255,255,0.02)',
    lineWidth: 1,
  });

  if (data && data.length) {
    series.setData(data);
    chart.timeScale().fitContent();
  }

  // Auto-resize on window resize
  const ro = new ResizeObserver(() => {
    chart.applyOptions({ width: container.clientWidth });
  });
  ro.observe(container);

  return { chart, series, _ro: ro };
}
