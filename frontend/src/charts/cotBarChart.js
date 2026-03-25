/**
 * COT Bar Chart factory — speculator net position over time.
 *
 * Uses Chart.js BarController for rendering green (long) / red (short) bars.
 */

import {
  Chart,
  BarController,
  BarElement,
  CategoryScale,
  LinearScale,
  Tooltip,
  Legend,
} from 'chart.js';

Chart.register(BarController, BarElement, CategoryScale, LinearScale, Tooltip, Legend);

/**
 * Create a COT bar chart on the given canvas.
 * @param {HTMLCanvasElement} canvas
 * @param {{ labels: string[], nets: number[], ois: number[] }} data
 * @returns {Chart} Chart.js instance (call .destroy() before recreating)
 */
export function createCotBarChart(canvas, data) {
  const { labels, nets } = data;

  const barColors = nets.map((n) =>
    n >= 0 ? 'rgba(63,185,80,0.7)' : 'rgba(248,81,73,0.7)'
  );

  return new Chart(canvas.getContext('2d'), {
    type: 'bar',
    data: {
      labels,
      datasets: [
        {
          label: 'Spec. Netto',
          data: nets,
          backgroundColor: barColors,
          borderWidth: 0,
        },
      ],
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        legend: { display: false },
        tooltip: {
          callbacks: {
            label(ctx) {
              const v = ctx.raw;
              return (v > 0 ? '+' : '') + Math.round(v).toLocaleString();
            },
          },
        },
      },
      scales: {
        x: {
          ticks: { maxTicksLimit: 10, color: '#7d8590', font: { size: 10 }, maxRotation: 0 },
          grid: { color: '#21262d' },
        },
        y: {
          ticks: {
            color: '#7d8590',
            font: { size: 10 },
            callback(v) {
              const a = Math.abs(v);
              if (a >= 1e6) return (v / 1e6).toFixed(1) + 'M';
              if (a >= 1e3) return (v / 1e3).toFixed(0) + 'K';
              return v;
            },
          },
          grid: { color: '#21262d' },
        },
      },
    },
  });
}
