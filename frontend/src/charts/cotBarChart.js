/**
 * COT Bar Chart factory — speculator net position over time.
 *
 * Uses Chart.js BarController for rendering green (long) / red (short) bars.
 * Click on a bar to emit detail data via the onBarClick callback.
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
 * @param {{ onBarClick?: (index: number, label: string, value: number) => void }} [callbacks]
 * @returns {Chart} Chart.js instance (call .destroy() before recreating)
 */
export function createCotBarChart(canvas, data, callbacks = {}) {
  const { labels, nets } = data;

  const barColors = nets.map((n) =>
    n >= 0 ? 'rgba(63,185,80,0.7)' : 'rgba(248,81,73,0.7)'
  );
  const barHoverColors = nets.map((n) =>
    n >= 0 ? 'rgba(63,185,80,1)' : 'rgba(248,81,73,1)'
  );

  const chart = new Chart(canvas.getContext('2d'), {
    type: 'bar',
    data: {
      labels,
      datasets: [
        {
          label: 'Spec. Netto',
          data: nets,
          backgroundColor: barColors,
          hoverBackgroundColor: barHoverColors,
          borderWidth: 0,
        },
      ],
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      interaction: {
        mode: 'index',
        intersect: false,
      },
      plugins: {
        legend: { display: false },
        tooltip: {
          backgroundColor: '#1c2128',
          borderColor: '#30363d',
          borderWidth: 1,
          titleColor: '#e6edf3',
          bodyColor: '#7d8590',
          titleFont: { family: "'DM Sans', sans-serif", size: 12 },
          bodyFont: { family: "'DM Mono', monospace", size: 12 },
          padding: 10,
          cornerRadius: 6,
          displayColors: false,
          callbacks: {
            title(items) {
              return items[0]?.label || '';
            },
            label(ctx) {
              const v = ctx.raw;
              const sign = v > 0 ? '+' : '';
              return `Netto: ${sign}${Math.round(v).toLocaleString()}`;
            },
            afterLabel(ctx) {
              const idx = ctx.dataIndex;
              const oi = data.ois?.[idx];
              if (oi) {
                const pct = ((nets[idx] / oi) * 100).toFixed(1);
                return `OI: ${Math.round(oi).toLocaleString()} (${pct}%)`;
              }
              return '';
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
      onClick(_event, elements) {
        if (!elements.length || !callbacks.onBarClick) return;
        const el = elements[0];
        const idx = el.index;
        callbacks.onBarClick(idx, labels[idx], nets[idx]);
      },
      onHover(event, elements) {
        const target = event.native?.target;
        if (target) {
          target.style.cursor = elements.length ? 'pointer' : 'default';
        }
      },
    },
  });

  return chart;
}
