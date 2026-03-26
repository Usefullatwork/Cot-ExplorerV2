/**
 * Radar chart factory for confluence scoring.
 *
 * Uses Chart.js RadarController to display 12 criteria as axes.
 * Hover tooltips show criterion name + pass/fail status with styled tooltip.
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
  const passing = values.filter((v) => v).length;
  const total = values.length;

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
            v ? '#3fb950' : '#484f58'
          ),
          pointHoverBackgroundColor: values.map((v) =>
            v ? '#56d364' : '#484f58'
          ),
          pointHoverBorderColor: values.map((v) =>
            v ? '#56d364' : '#6e7681'
          ),
          pointRadius: 5,
          pointHoverRadius: 7,
          fill: true,
        },
      ],
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      interaction: {
        mode: 'point',
        intersect: true,
      },
      plugins: {
        legend: { display: false },
        tooltip: {
          backgroundColor: '#1c2128',
          borderColor: '#30363d',
          borderWidth: 1,
          titleColor: '#e6edf3',
          bodyColor: '#7d8590',
          titleFont: { family: "'DM Sans', sans-serif", size: 12, weight: '600' },
          bodyFont: { family: "'DM Mono', monospace", size: 11 },
          padding: 10,
          cornerRadius: 6,
          displayColors: false,
          callbacks: {
            title(items) {
              return items[0]?.label || '';
            },
            label(ctx) {
              const passed = ctx.raw === 1;
              const icon = passed ? '\u2714' : '\u2718';
              const status = passed ? 'Oppfylt' : 'Ikke oppfylt';
              return `${icon} ${status}`;
            },
            afterBody() {
              return `${passing}/${total} kriterier`;
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
            color: (ctx) => {
              const idx = ctx.index;
              return values[idx] ? '#3fb950' : '#7d8590';
            },
            font: { size: 10, family: "'DM Sans', sans-serif" },
          },
        },
      },
    },
  });
}
