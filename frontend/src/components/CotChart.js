/**
 * CotChart component — modal overlay with COT bar chart + stats.
 *
 * Ports the openCotChart / closeCotModal functions from v1 index.html.
 * Uses the cotBarChart factory for the Chart.js instance.
 */

import { createCotBarChart } from '../charts/cotBarChart.js';
import { formatNumber, colorClass } from '../utils.js';
import { fetchCotHistory } from '../api.js';

let chartInstance = null;

/**
 * Build the modal DOM and append it to the document body.
 * Call once at startup.
 */
export function render() {
  // Only create once
  if (document.getElementById('cotModal')) return;

  document.body.insertAdjacentHTML(
    'beforeend',
    `<div class="cot-modal" id="cotModal">
      <div class="cot-modal-inner">
        <div class="cot-modal-header">
          <div class="cot-modal-title" id="cotModalTitle">-</div>
          <button class="cot-modal-close" id="cotModalClose">X</button>
        </div>
        <div class="cot-chart-wrap"><canvas id="cotChart"></canvas></div>
        <div class="cot-stat-row" id="cotModalStats"></div>
      </div>
    </div>`
  );

  // Close on backdrop click
  document.getElementById('cotModal').addEventListener('click', (e) => {
    if (e.target.id === 'cotModal') close();
  });

  // Close button
  document.getElementById('cotModalClose').addEventListener('click', close);

  // Escape key
  document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape') close();
  });
}

/** Close the modal */
function close() {
  const modal = document.getElementById('cotModal');
  if (modal) modal.classList.remove('open');
}

/**
 * Open the COT chart modal for a given market.
 * @param {string} symbol   CFTC market code
 * @param {string} report   Report type (e.g. 'legacy', 'tff')
 * @param {string} name     Human-readable market name
 */
export async function open(symbol, report, name) {
  const modal = document.getElementById('cotModal');
  if (!modal) return;

  document.getElementById('cotModalTitle').textContent = name + ' - COT Historikk';
  document.getElementById('cotModalStats').innerHTML =
    '<div style="color:var(--m);font-size:13px">Laster...</div>';
  modal.classList.add('open');

  try {
    const ts = await fetchCotHistory(symbol);
    const data = (ts.data || ts || []).filter((d) => d.date && d.spec_net != null);
    if (!data.length) throw new Error('Ingen data');

    const labels = data.map((d) => d.date);
    const nets = data.map((d) => d.spec_net);
    const ois = data.map((d) => d.oi || 0);

    // Destroy previous chart
    if (chartInstance) {
      chartInstance.destroy();
      chartInstance = null;
    }

    const canvas = document.getElementById('cotChart');
    chartInstance = createCotBarChart(canvas, { labels, nets, ois });

    // Stats
    const last = nets[nets.length - 1];
    const prev = nets.length > 1 ? nets[nets.length - 2] : 0;
    const chg = last - prev;
    const max = Math.max(...nets);
    const min = Math.min(...nets);
    const lastOi = ois[ois.length - 1];
    const pct = lastOi ? (last / lastOi * 100).toFixed(1) : '-';

    document.getElementById('cotModalStats').innerHTML =
      `<div class="cot-stat"><div class="cot-stat-label">Netto na</div><div class="cot-stat-val ${colorClass(last)}">${formatNumber(last)}</div></div>` +
      `<div class="cot-stat"><div class="cot-stat-label">Uke endring</div><div class="cot-stat-val ${colorClass(chg)}">${formatNumber(chg)}</div></div>` +
      `<div class="cot-stat"><div class="cot-stat-label">% av OI</div><div class="cot-stat-val">${pct}%</div></div>` +
      `<div class="cot-stat"><div class="cot-stat-label">Historisk maks</div><div class="cot-stat-val bull">${formatNumber(max)}</div></div>` +
      `<div class="cot-stat"><div class="cot-stat-label">Historisk min</div><div class="cot-stat-val bear">${formatNumber(min)}</div></div>` +
      `<div class="cot-stat"><div class="cot-stat-label">Datapunkter</div><div class="cot-stat-val">${data.length}</div></div>`;
  } catch (e) {
    document.getElementById('cotModalStats').innerHTML =
      '<div style="color:var(--bear)">Ingen historikk tilgjengelig for dette markedet</div>';
    console.error('[CotChart]', e);
  }
}
