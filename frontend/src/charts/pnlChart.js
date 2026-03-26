/**
 * P&L equity curve chart using Chart.js.
 *
 * Creates a line chart with gradient fill — green above zero, red below.
 * Used by BotPanel to display cumulative P&L over time.
 */

import {
  Chart,
  LineController,
  LineElement,
  PointElement,
  CategoryScale,
  LinearScale,
  Tooltip,
  Filler,
} from 'chart.js';

Chart.register(LineController, LineElement, PointElement, CategoryScale, LinearScale, Tooltip, Filler);

/** @type {Chart|null} */
let pnlChartInstance = null;

/**
 * Create or update the P&L equity curve chart.
 * @param {HTMLCanvasElement} canvas  Target canvas element
 * @param {{ date: string, pnl: number }[]} data  Sorted ascending by date
 * @returns {Chart}  Chart.js instance for later disposal
 */
export function createPnlChart(canvas, data) {
  if (pnlChartInstance) {
    pnlChartInstance.destroy();
    pnlChartInstance = null;
  }

  if (!data || !data.length) return null;

  const labels = data.map((d) => d.date);
  const values = data.map((d) => d.pnl);
  const ctx = canvas.getContext('2d');

  // Gradient fill: green above 0, red below 0
  const gradient = ctx.createLinearGradient(0, 0, 0, canvas.height || 200);
  const maxVal = Math.max(...values, 0);
  const minVal = Math.min(...values, 0);
  const range = maxVal - minVal || 1;
  const zeroFrac = maxVal / range;

  gradient.addColorStop(0, 'rgba(63, 185, 80, 0.25)');
  gradient.addColorStop(Math.min(zeroFrac, 1), 'rgba(63, 185, 80, 0.05)');
  gradient.addColorStop(Math.min(zeroFrac, 1), 'rgba(248, 81, 73, 0.05)');
  gradient.addColorStop(1, 'rgba(248, 81, 73, 0.25)');

  // Line color based on last value
  const lastVal = values[values.length - 1] || 0;
  const lineColor = lastVal >= 0 ? 'rgba(63, 185, 80, 0.9)' : 'rgba(248, 81, 73, 0.9)';

  pnlChartInstance = new Chart(ctx, {
    type: 'line',
    data: {
      labels,
      datasets: [{
        data: values,
        borderColor: lineColor,
        backgroundColor: gradient,
        borderWidth: 2,
        pointRadius: 2,
        pointBackgroundColor: lineColor,
        fill: true,
        tension: 0.3,
      }],
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        legend: { display: false },
        tooltip: {
          backgroundColor: '#1c2128',
          borderColor: '#30363d',
          borderWidth: 1,
          titleColor: '#e6edf3',
          bodyColor: '#7d8590',
          padding: 8,
          cornerRadius: 6,
          displayColors: false,
          callbacks: {
            label(ctx) {
              const v = ctx.raw;
              const sign = v >= 0 ? '+' : '';
              return `P&L: ${sign}$${v.toFixed(2)}`;
            },
          },
        },
      },
      scales: {
        x: {
          ticks: { color: '#7d8590', font: { size: 9 }, maxTicksLimit: 10 },
          grid: { color: '#21262d' },
        },
        y: {
          ticks: {
            color: '#7d8590',
            font: { size: 9 },
            callback(v) { return (v >= 0 ? '+' : '') + '$' + v.toFixed(0); },
          },
          grid: { color: '#21262d' },
        },
      },
    },
  });

  return pnlChartInstance;
}

/**
 * Destroy the current P&L chart instance, if any.
 */
export function destroyPnlChart() {
  if (pnlChartInstance) {
    pnlChartInstance.destroy();
    pnlChartInstance = null;
  }
}
