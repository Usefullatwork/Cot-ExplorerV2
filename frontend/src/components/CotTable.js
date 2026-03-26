/**
 * CotTable component — searchable, filterable table of COT positions.
 *
 * Ports the renderCot / setCF / filterCot functions from v1 index.html.
 */

import { formatNumber, colorClass } from '../utils.js';

// ── Internal state ──────────────────────────────────────────
let allData = [];
let activeFilter = 'alle';
let searchQuery = '';

/** Category labels (Norwegian UI) */
const CATS = {
  alle: 'Alle',
  aksjer: 'Aksjer',
  valuta: 'Valuta',
  renter: 'Renter',
  ravarer: 'Ravarer',
  krypto: 'Krypto',
  landbruk: 'Landbruk',
  volatilitet: 'Vol',
  annet: 'Annet',
};

/** Signal info map */
const SI = {
  'bull-strong': { i: 'B+', t: 'Kjoeper sterkt' },
  'bull-mild':   { i: 'B',  t: 'Svakt bullish' },
  'neutral':     { i: 'N',  t: 'Noytral' },
  'bear-mild':   { i: 'S',  t: 'Svakt bearish' },
  'bear-strong': { i: 'S+', t: 'Selger sterkt' },
};

function sig(net, oi) {
  if (!oi) return 'neutral';
  const p = net / oi;
  if (p > 0.15) return 'bull-strong';
  if (p > 0.04) return 'bull-mild';
  if (p < -0.15) return 'bear-strong';
  if (p < -0.04) return 'bear-mild';
  return 'neutral';
}

/** @type {Function|null} Chart open callback set by CotChart */
let onRowClick = null;

/**
 * Register a callback for when a COT row is clicked.
 * @param {Function} cb  (symbol, report, name) => void
 */
export function onOpenChart(cb) {
  onRowClick = cb;
}

// ── Rendering ───────────────────────────────────────────────

function renderTable() {
  const data = allData.filter((d) => {
    if (activeFilter !== 'alle' && d.kategori !== activeFilter) return false;
    if (!searchQuery) return true;
    return (d.navn_no + d.market + d.symbol + d.kategori).toLowerCase().includes(searchQuery);
  });

  const cntEl = document.getElementById('cotCnt');
  if (cntEl) cntEl.textContent = data.length + ' markeder';

  // Category counts
  const counts = { alle: allData.length };
  allData.forEach((d) => {
    counts[d.kategori] = (counts[d.kategori] || 0) + 1;
  });

  const fchEl = document.getElementById('fchips');
  if (fchEl) {
    fchEl.innerHTML = Object.entries(CATS)
      .filter(([k]) => k === 'alle' || counts[k])
      .map(
        ([k, v]) =>
          `<button class="fc${k === activeFilter ? ' on' : ''}" data-cat="${k}" aria-pressed="${k === activeFilter ? 'true' : 'false'}" aria-label="Filter: ${v} (${counts[k] || 0} markeder)">${v} <span style="opacity:.6" aria-hidden="true">${counts[k] || 0}</span></button>`
      )
      .join('');
  }

  const gridEl = document.getElementById('cotGrid');
  if (!gridEl) return;

  if (!data.length) {
    const isSearch = searchQuery || activeFilter !== 'alle';
    gridEl.innerHTML = `<div class="empty-state">
      <div class="empty-state-icon">${isSearch ? '\uD83D\uDD0D' : '\uD83D\uDCCA'}</div>
      <div class="empty-state-title">${isSearch ? 'Ingen resultater' : 'Ingen COT-data'}</div>
      <div class="empty-state-text">${isSearch ? 'Prov a endre sok eller filter.' : 'Kjor fetch_all.py for a laste inn data.'}</div>
    </div>`;
    return;
  }

  const rows = data
    .map((d) => {
      const sp = d.spekulanter || {};
      const s2 = sig(sp.net || 0, d.open_interest || 1);
      const si = SI[s2];
      return `<tr data-sym="${d.symbol}" data-report="${d.report}" data-name="${encodeURIComponent(d.navn_no || d.market)}" tabindex="0" role="row" aria-label="${d.navn_no || d.market}: ${si.t}, netto ${formatNumber(sp.net || 0)}">
        <td style="cursor:pointer" class="cot-row-click"><div class="tdname">${d.navn_no || d.market}</div><div class="tdsub">${d.forklaring || ''}</div></td>
        <td><span class="sp2 ${s2}" role="status">${si.i} ${si.t}</span></td>
        <td class="${sp.net >= 0 ? 'tdbull' : 'tdbear'}">${sp.net > 0 ? '+' : ''}${formatNumber(sp.net || 0)}</td>
        <td class="${d.change_spec_net >= 0 ? 'tdbull' : 'tdbear'}">${d.change_spec_net > 0 ? '+' : ''}${formatNumber(d.change_spec_net || 0)}</td>
        <td class="tdr">${formatNumber(d.open_interest || 0)}</td>
        <td class="tdr" style="font-size:10px;color:var(--m)">${d.report}</td>
      </tr>`;
    })
    .join('');

  gridEl.innerHTML = `<div class="cotw"><table class="cott" aria-label="COT posisjoner tabell"><thead><tr>
    <th scope="col">Marked</th><th scope="col">Signal</th><th scope="col" style="text-align:right">Spec. Netto</th>
    <th scope="col" style="text-align:right">Uke</th><th scope="col" style="text-align:right">OI</th>
    <th scope="col" style="text-align:right">Kilde</th></tr></thead><tbody>${rows}</tbody></table></div>`;
}

// ── Public API ──────────────────────────────────────────────

/**
 * Build the COT panel skeleton.
 * @param {HTMLElement} container  #panel-cot
 */
export function render(container) {
  container.innerHTML = `
    <div class="sh"><h2 class="sh-t">COT-posisjoner</h2><div class="sh-b" id="cotCnt" aria-live="polite">-</div></div>
    <div class="sbar2" role="search" aria-label="Sok og filtrer COT-markeder">
      <label for="cotS" class="sr-only">Sok i COT-markeder</label>
      <input type="search" id="cotS" placeholder="Sok marked..." autocomplete="off" aria-label="Sok marked">
      <div id="fchips" role="group" aria-label="Kategorifilter"></div>
    </div>
    <div id="cotGrid" role="region" aria-label="COT tabell" aria-live="polite"></div>`;

  // Wire search input
  const searchInput = document.getElementById('cotS');
  if (searchInput) {
    searchInput.addEventListener('input', () => {
      searchQuery = searchInput.value.toLowerCase();
      renderTable();
    });
  }

  // Wire filter chips (delegated)
  container.addEventListener('click', (e) => {
    const chip = e.target.closest('.fc');
    if (chip && chip.dataset.cat) {
      activeFilter = chip.dataset.cat;
      renderTable();
    }

    // Row click -> open chart
    const row = e.target.closest('tr[data-sym]');
    if (row && onRowClick) {
      onRowClick(row.dataset.sym, row.dataset.report, decodeURIComponent(row.dataset.name));
    }
  });

  // Keyboard: Enter/Space on table rows to open chart
  container.addEventListener('keydown', (e) => {
    if (e.key === 'Enter' || e.key === ' ') {
      const row = e.target.closest('tr[data-sym]');
      if (row && onRowClick) {
        e.preventDefault();
        onRowClick(row.dataset.sym, row.dataset.report, decodeURIComponent(row.dataset.name));
      }
    }
  });
}

/**
 * Update the table with fresh COT data.
 * @param {Array} data  Array of COT market objects
 */
export function update(data) {
  if (!Array.isArray(data)) return;
  allData = data;
  renderTable();
}
