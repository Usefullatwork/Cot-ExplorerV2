/**
 * Radar chart factory for confluence scoring.
 *
 * Uses Chart.js RadarController to display 12 criteria as axes.
 */

import {
  Chart,
  RadarController,
  RadialLinearScale,
  PointElement,
  LineElement,
  Filler,
  Tooltip,
} from 'chart.js';

Chart.register(RadarController, RadialLinearScale, PointElement, LineElement, Filler, Tooltip);

/**
 * Create a radar chart on the given canvas.
 * @param {HTMLCanvasElement} canvas
 * @param {string[]} labels   12 criteria names
 * @param {number[]} values   1 (pass) or 0 (fail) per criterion
 * @returns {Chart} Chart.js instance
 */
export function createRadarChart(canvas, labels, values) {
  return new Chart(canvas.getContext('2d'), {
    type: 'radar',
    data: {
      labels,
      datasets: [
        {
          label: 'Konfluens',
          data: values,
          backgroundColor: 'rgba(63,185,80,0.15)',
          borderColor: 'rgba(63,185,80,0.8)',
          borderWidth: 2,
          pointBackgroundColor: values.map((v) =>
            v ? '#3fb950' : '#30363d'
          ),
          pointBorderColor: values.map((v) =>
            v ? '#3fb950' : '#30363d'
          ),
          pointRadius: 4,
          fill: true,
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
              return ctx.raw ? 'Pass' : 'Fail';
            },
          },
        },
      },
      scales: {
        r: {
          min: 0,
          max: 1,
          ticks: { display: false, stepSize: 1 },
          grid: { color: '#21262d' },
          angleLines: { color: '#21262d' },
          pointLabels: {
            color: '#7d8590',
            font: { size: 10, family: "'DM Sans', sans-serif" },
          },
        },
      },
    },
  });
}
