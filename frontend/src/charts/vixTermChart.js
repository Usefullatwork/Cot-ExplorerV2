/**
 * VIX Term Structure chart — shows VIX 9D, spot, 3M with regime coloring.
 * Uses Chart.js (already installed).
 */
import { Chart, registerables } from 'chart.js';
Chart.register(...registerables);

let chartInstance = null;

/**
 * Create or update the VIX term structure chart.
 * @param {HTMLCanvasElement} canvas
 * @param {{ vix_9d: number, spot: number, vix_3m: number, regime: string, spread: number }} data
 * @returns {Chart}
 */
export function createVixTermChart(canvas, data) {
  if (!canvas || !data) return null;

  destroyVixTermChart();

  const { vix_9d = 0, spot = 0, vix_3m = 0, regime = 'unknown', spread = 0 } = data;

  // Color by regime: contango (spot < 3M) = green, backwardation (spot > 3M) = red
  const isContango = spot <= vix_3m;
  const lineColor = isContango ? '#7ee787' : '#f85149';
  const fillColor = isContango ? 'rgba(126, 231, 135, 0.15)' : 'rgba(248, 81, 73, 0.15)';

  chartInstance = new Chart(canvas, {
    type: 'line',
    data: {
      labels: ['VIX 9D', 'VIX Spot', 'VIX 3M'],
      datasets: [{
        label: 'VIX Term Structure',
        data: [vix_9d, spot, vix_3m],
        borderColor: lineColor,
        backgroundColor: fillColor,
        fill: true,
        tension: 0.3,
        pointRadius: 6,
        pointBackgroundColor: lineColor,
        pointBorderColor: '#fff',
        pointBorderWidth: 2,
      }],
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        legend: { display: false },
        tooltip: {
          callbacks: {
            label: (ctx) => `${ctx.label}: ${ctx.parsed.y.toFixed(2)}`,
          },
        },
        subtitle: {
          display: true,
          text: `${isContango ? 'Contango' : 'Backwardation'} — Spread: ${spread >= 0 ? '+' : ''}${spread.toFixed(2)}`,
          color: lineColor,
          font: { size: 12, family: "'DM Mono', monospace" },
          padding: { top: 0, bottom: 10 },
        },
      },
      scales: {
        x: {
          ticks: { color: 'rgba(255,255,255,0.5)', font: { family: "'DM Mono', monospace", size: 11 } },
          grid: { color: 'rgba(255,255,255,0.05)' },
        },
        y: {
          ticks: { color: 'rgba(255,255,255,0.5)', font: { family: "'DM Mono', monospace", size: 11 } },
          grid: { color: 'rgba(255,255,255,0.05)' },
        },
      },
    },
  });

  return chartInstance;
}

export function destroyVixTermChart() {
  if (chartInstance) {
    chartInstance.destroy();
    chartInstance = null;
  }
}
