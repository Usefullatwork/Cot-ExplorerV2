/**
 * PricesPanel component — live prices for Indices, Forex, and Commodities.
 *
 * Three card groups with auto-refresh every 60s when the tab is active.
 */

import { escapeHtml, formatPct, colorClass } from '../utils.js';
import { fetchPricesLive } from '../api.js';

let pollTimer = null;

/**
 * Format a price: 2 decimals for large, 5 for small (FX).
 * @param {number} v
 * @returns {string}
 */
function fmtPrice(v) {
  if (!v && v !== 0) return '-';
  return v > 100 ? v.toFixed(2) : v.toFixed(5);
}

/**
 * Build the Prices panel skeleton.
 * @param {HTMLElement} container  #panel-prices
 */
export function render(container) {
  container.innerHTML = `
    <div class="sh"><h2 class="sh-t">Priser</h2><div class="sh-b" id="pricesUpdated" aria-live="polite">-</div></div>
    <div id="pricesContent">
      <div class="loading" role="status"><div class="spinner" aria-hidden="true"></div>Laster priser...</div>
    </div>`;
}

/**
 * Update the panel with price data.
 * @param {{ items: Array }} data  Prices response
 */
export function update(data) {
  const el = document.getElementById('pricesContent');
  if (!el || !data || !data.items) return;

  // Group items
  const groups = {};
  for (const item of data.items) {
    const g = item.group || 'Annet';
    if (!groups[g]) groups[g] = [];
    groups[g].push(item);
  }

  const groupEmoji = { Indekser: '\uD83D\uDCC8', Valuta: '\uD83D\uDCB1', Ravarer: '\u26CF' };

  el.innerHTML = Object.entries(groups)
    .map(([name, items]) => `
      <div class="sh" style="margin-top:16px"><h2 class="sh-t">${groupEmoji[name] || ''} ${escapeHtml(name)}</h2><div class="sh-b">${items.length} instrumenter</div></div>
      <div class="g4">${items.map((p) => {
        const chg1d = p.chg_1d;
        const chg5d = p.chg_5d;
        const col1d = chg1d != null ? colorClass(chg1d) : 'neutral';
        const col5d = chg5d != null ? colorClass(chg5d) : 'neutral';
        return `<div class="card">
          <div class="ct">${escapeHtml(p.name)}</div>
          <div class="snum" style="font-family:'DM Mono',monospace">${fmtPrice(p.price)}</div>
          <div style="display:flex;gap:12px;margin-top:8px;font-size:11px">
            <span class="${col1d}">1d: ${chg1d != null ? formatPct(chg1d) : '--'}</span>
            <span class="${col5d}">5d: ${chg5d != null ? formatPct(chg5d) : '--'}</span>
          </div>
        </div>`;
      }).join('')}</div>`)
    .join('');

  // Update timestamp
  const ts = document.getElementById('pricesUpdated');
  if (ts) ts.textContent = 'Oppdatert: ' + new Date().toLocaleTimeString('nb-NO');
}

/**
 * Fetch and update prices. Called when tab becomes active.
 */
export async function refreshAll() {
  try {
    const data = await fetchPricesLive();
    update(data);
  } catch (e) {
    console.error('[PricesPanel]', e);
  }

  // Start auto-refresh every 60s
  stopPolling();
  pollTimer = setInterval(async () => {
    try {
      const data = await fetchPricesLive();
      update(data);
    } catch { /* ignore */ }
  }, 60_000);
}

/**
 * Stop auto-refresh polling. Called when tab becomes inactive.
 */
export function stopPolling() {
  if (pollTimer) {
    clearInterval(pollTimer);
    pollTimer = null;
  }
}
