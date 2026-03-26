/**
 * Price line chart factory using lightweight-charts.
 *
 * Creates a dark-themed area chart for price overlay in the COT modal.
 * Includes crosshair with snap-to-data tooltip showing price and date.
 */

import { createChart, ColorType, CrosshairMode } from 'lightweight-charts';

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
    crosshair: {
      mode: CrosshairMode.Normal,
      vertLine: {
        color: 'rgba(88,166,255,0.4)',
        width: 1,
        style: 2,
        labelBackgroundColor: '#1c2128',
      },
      horzLine: {
        color: 'rgba(88,166,255,0.4)',
        width: 1,
        style: 2,
        labelBackgroundColor: '#1c2128',
      },
    },
    rightPriceScale: { borderColor: '#21262d' },
    timeScale: { borderColor: '#21262d' },
  });

  const series = chart.addAreaSeries({
    lineColor: 'rgba(255,255,255,0.8)',
    topColor: 'rgba(255,255,255,0.12)',
    bottomColor: 'rgba(255,255,255,0.02)',
    lineWidth: 1,
    crosshairMarkerVisible: true,
    crosshairMarkerRadius: 4,
    crosshairMarkerBorderColor: '#58a6ff',
    crosshairMarkerBackgroundColor: '#161b22',
  });

  if (data && data.length) {
    series.setData(data);
    chart.timeScale().fitContent();
  }

  // Floating tooltip element
  const tooltip = document.createElement('div');
  tooltip.className = 'lwc-tooltip';
  tooltip.style.cssText =
    'position:absolute;top:8px;left:8px;z-index:10;pointer-events:none;' +
    'background:#1c2128;border:1px solid #30363d;border-radius:6px;padding:8px 10px;' +
    'font-family:"DM Mono",monospace;font-size:11px;color:#e6edf3;display:none;' +
    'box-shadow:0 4px 12px rgba(0,0,0,0.4);';
  container.style.position = 'relative';
  container.appendChild(tooltip);

  chart.subscribeCrosshairMove((param) => {
    if (!param.time || !param.seriesData?.size) {
      tooltip.style.display = 'none';
      return;
    }
    const price = param.seriesData.get(series);
    if (price == null || price.value == null) {
      tooltip.style.display = 'none';
      return;
    }
    const dateStr = typeof param.time === 'string'
      ? param.time
      : `${param.time.year}-${String(param.time.month).padStart(2, '0')}-${String(param.time.day).padStart(2, '0')}`;
    const priceStr = price.value > 100 ? price.value.toFixed(2) : price.value.toFixed(5);
    tooltip.innerHTML = `<div style="color:#7d8590;font-size:10px;margin-bottom:2px">${dateStr}</div><div style="font-weight:500">${priceStr}</div>`;
    tooltip.style.display = 'block';
  });

  // Auto-resize on window resize
  const ro = new ResizeObserver(() => {
    chart.applyOptions({ width: container.clientWidth });
  });
  ro.observe(container);

  return { chart, series, _ro: ro };
}
