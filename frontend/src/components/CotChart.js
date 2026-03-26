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
    `<div class="cot-modal" id="cotModal" role="dialog" aria-modal="true" aria-labelledby="cotModalTitle" aria-hidden="true">
      <div class="cot-modal-inner">
        <div class="cot-modal-header">
          <h2 class="cot-modal-title" id="cotModalTitle">-</h2>
          <button class="cot-modal-close" id="cotModalClose" aria-label="Lukk dialog">
            <span aria-hidden="true">X</span>
          </button>
        </div>
        <div class="cot-chart-wrap" role="img" aria-label="COT historikk diagram"><canvas id="cotChart"></canvas></div>
        <div id="cotBarDetail" class="cot-bar-detail" style="display:none"></div>
        <div class="cot-stat-row" id="cotModalStats" role="group" aria-label="COT statistikk"></div>
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

  // Trap focus inside modal when open
  document.getElementById('cotModal').addEventListener('keydown', (e) => {
    if (e.key !== 'Tab') return;
    const modal = document.getElementById('cotModal');
    if (!modal || !modal.classList.contains('open')) return;
    const focusable = modal.querySelectorAll('button, [href], input, [tabindex]:not([tabindex="-1"])');
    if (!focusable.length) return;
    const first = focusable[0];
    const last = focusable[focusable.length - 1];
    if (e.shiftKey && document.activeElement === first) {
      e.preventDefault();
      last.focus();
    } else if (!e.shiftKey && document.activeElement === last) {
      e.preventDefault();
      first.focus();
    }
  });
}

/** Previously focused element for restoring focus on close */
let previousFocus = null;

/** Close the modal */
function close() {
  const modal = document.getElementById('cotModal');
  if (modal) {
    modal.classList.remove('open');
    modal.setAttribute('aria-hidden', 'true');
  }
  const detail = document.getElementById('cotBarDetail');
  if (detail) detail.style.display = 'none';
  // Restore focus to the element that opened the modal
  if (previousFocus && previousFocus.focus) {
    previousFocus.focus();
    previousFocus = null;
  }
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

  // Save current focus for restoration on close
  previousFocus = document.activeElement;

  document.getElementById('cotModalTitle').textContent = name + ' - COT Historikk';
  document.getElementById('cotModalStats').innerHTML =
    '<div class="skeleton-row" style="height:80px" role="status" aria-label="Laster"></div>';
  const detailEl = document.getElementById('cotBarDetail');
  if (detailEl) detailEl.style.display = 'none';
  modal.classList.add('open');
  modal.setAttribute('aria-hidden', 'false');

  // Focus the close button for keyboard users
  const closeBtn = document.getElementById('cotModalClose');
  if (closeBtn) closeBtn.focus();

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
    chartInstance = createCotBarChart(canvas, { labels, nets, ois }, {
      onBarClick(idx, label, value) {
        const detail = document.getElementById('cotBarDetail');
        if (!detail) return;
        const oi = ois[idx] || 0;
        const prevNet = idx > 0 ? nets[idx - 1] : 0;
        const weekChg = value - prevNet;
        const pctOi = oi ? ((value / oi) * 100).toFixed(1) : '-';
        detail.innerHTML =
          `<div class="cot-bar-detail-title">Uke: ${label}</div>` +
          `<div class="cot-bar-detail-grid">` +
          `<div><span class="cot-bar-detail-label">Netto</span><span class="${colorClass(value)}" style="font-family:'DM Mono',monospace;font-weight:600">${value > 0 ? '+' : ''}${formatNumber(value)}</span></div>` +
          `<div><span class="cot-bar-detail-label">Uke-endring</span><span class="${colorClass(weekChg)}" style="font-family:'DM Mono',monospace;font-weight:600">${weekChg > 0 ? '+' : ''}${formatNumber(weekChg)}</span></div>` +
          `<div><span class="cot-bar-detail-label">OI</span><span style="font-family:'DM Mono',monospace">${formatNumber(oi)}</span></div>` +
          `<div><span class="cot-bar-detail-label">% av OI</span><span style="font-family:'DM Mono',monospace">${pctOi}%</span></div>` +
          `</div>`;
        detail.style.display = 'block';
      },
    });

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
      '<div class="empty-state"><div class="empty-state-icon">\u26A0</div><div class="empty-state-text">Ingen historikk tilgjengelig for dette markedet</div></div>';
    console.error('[CotChart]', e);
  }
}
