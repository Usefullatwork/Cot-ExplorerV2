/**
 * CotTable component — 8-category accordion of COT positions.
 *
 * Replaces the flat table with an accordion layout grouped by category.
 * Each category header shows a stacked bull/neutral/bear bar + counts.
 * Each market card shows signal badge, net %, and mini sparkline.
 */

import { formatNumber, colorClass, escapeHtml } from '../utils.js';
import { renderSparkline } from '../charts/svgSparkline.js';

// ── Internal state ──────────────────────────────────────────
let allData = [];
let searchQuery = '';
let openCategories = new Set();

/** Category config: key -> { label, emoji } */
const CATS = {
  aksjer:       { label: 'Aksjer',       emoji: '\uD83D\uDCC8' },
  valuta:       { label: 'Valuta',       emoji: '\uD83D\uDCB1' },
  renter:       { label: 'Renter',       emoji: '\uD83C\uDFE6' },
  ravarer:      { label: 'Ravarer',      emoji: '\u26CF' },
  landbruk:     { label: 'Landbruk',     emoji: '\uD83C\uDF3E' },
  krypto:       { label: 'Krypto',       emoji: '\u20BF' },
  volatilitet:  { label: 'Volatilitet',  emoji: '\uD83C\uDF0A' },
  annet:        { label: 'Annet',        emoji: '\uD83D\uDCE6' },
};

/** Signal info map */
const SI = {
  'bull-strong': { i: 'B+', t: 'Kjøper sterkt',  cls: 'bull' },
  'bull-mild':   { i: 'B',  t: 'Svakt bullish',  cls: 'bull' },
  'neutral':     { i: 'N',  t: 'Nøytral',        cls: 'neutral' },
  'bear-mild':   { i: 'S',  t: 'Svakt bearish',  cls: 'bear' },
  'bear-strong': { i: 'S+', t: 'Selger sterkt',  cls: 'bear' },
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

// ── Category grouping ────────────────────────────────────
function groupByCategory(data) {
  const groups = {};
  for (const cat of Object.keys(CATS)) {
    groups[cat] = [];
  }
  for (const d of data) {
    const cat = d.kategori || 'annet';
    if (!groups[cat]) groups[cat] = [];
    groups[cat].push(d);
  }
  return groups;
}

function countSignals(items) {
  let bull = 0, neutral = 0, bear = 0;
  for (const d of items) {
    const sp = d.spekulanter || {};
    const s = sig(sp.net || 0, d.open_interest || 1);
    if (s.startsWith('bull')) bull++;
    else if (s.startsWith('bear')) bear++;
    else neutral++;
  }
  return { bull, neutral, bear, total: items.length };
}

function renderStackedBar(counts) {
  const t = counts.total || 1;
  const bw = (counts.bull / t * 100).toFixed(0);
  const nw = (counts.neutral / t * 100).toFixed(0);
  const ew = (counts.bear / t * 100).toFixed(0);
  return `<div style="display:flex;height:6px;border-radius:3px;overflow:hidden;width:100%;gap:1px" aria-label="Bull ${counts.bull}, Neutral ${counts.neutral}, Bear ${counts.bear}"><div style="width:${bw}%;background:var(--bull)"></div><div style="width:${nw}%;background:var(--m)"></div><div style="width:${ew}%;background:var(--bear)"></div></div>`;
}

// ── Rendering ───────────────────────────────────────────────

function renderMarketCard(d) {
  const sp = d.spekulanter || {};
  const s = sig(sp.net || 0, d.open_interest || 1);
  const si = SI[s];
  const net = sp.net || 0;
  const pctOi = d.open_interest ? ((net / d.open_interest) * 100).toFixed(1) : '0.0';
  const hist = d.cot_history || [];
  const spark = hist.length > 1 ? renderSparkline(hist, { width: 60, height: 20 }) : '';

  return `<div class="cot-market-card" data-sym="${escapeHtml(d.symbol)}" data-report="${escapeHtml(d.report)}" data-name="${encodeURIComponent(d.navn_no || d.market)}" tabindex="0" role="button" aria-label="${escapeHtml(d.navn_no || d.market)}: ${escapeHtml(si.t)}">
    <div style="display:flex;align-items:center;gap:8px">
      <span class="sp2 ${s}" style="min-width:28px;text-align:center">${escapeHtml(si.i)}</span>
      <div style="flex:1;min-width:0">
        <div style="font-size:13px;font-weight:600;white-space:nowrap;overflow:hidden;text-overflow:ellipsis">${escapeHtml(d.navn_no || d.market)}</div>
        <div style="font-size:10px;color:var(--m)">${escapeHtml(d.forklaring || '')}</div>
      </div>
      <div style="text-align:right;min-width:50px">
        <div class="${colorClass(net)} data-value" style="font-size:12px;font-weight:600">${pctOi}%</div>
        <div style="font-size:9px;color:var(--m)">${net > 0 ? '+' : ''}${escapeHtml(formatNumber(net))}</div>
      </div>
      ${spark ? '<div style="min-width:60px">' + spark + '</div>' : ''}
    </div>
  </div>`;
}

function renderAccordion() {
  const filtered = allData.filter((d) => {
    if (!searchQuery) return true;
    return (d.navn_no + d.market + d.symbol + d.kategori).toLowerCase().includes(searchQuery);
  });

  const cntEl = document.getElementById('cotCnt');
  if (cntEl) cntEl.textContent = filtered.length + ' markeder';

  const gridEl = document.getElementById('cotGrid');
  if (!gridEl) return;

  if (!filtered.length) {
    const isSearch = searchQuery.length > 0;
    gridEl.innerHTML = `<div class="empty-state">
      <div class="empty-state-icon">${isSearch ? '\uD83D\uDD0D' : '\uD83D\uDCCA'}</div>
      <div class="empty-state-title">${isSearch ? 'Ingen resultater' : 'Ingen COT-data'}</div>
      <div class="empty-state-text">${isSearch ? 'Prov a endre sok.' : 'Kjor fetch_all.py for a laste inn data.'}</div>
    </div>`;
    return;
  }

  const groups = groupByCategory(filtered);

  gridEl.innerHTML = Object.entries(CATS)
    .filter(([cat]) => groups[cat] && groups[cat].length > 0)
    .map(([cat, cfg]) => {
      const items = groups[cat];
      const counts = countSignals(items);
      const isOpen = openCategories.has(cat);

      return `<div class="cot-accordion" data-cat="${cat}">
        <div class="cot-accordion-header" data-cat="${cat}" role="button" tabindex="0" aria-expanded="${isOpen}" aria-label="${cfg.label}: ${counts.total} markeder">
          <div style="display:flex;align-items:center;gap:8px;flex:1">
            <span style="font-size:16px">${cfg.emoji}</span>
            <span style="font-weight:600;font-size:14px">${cfg.label}</span>
            <span style="font-size:11px;color:var(--m)">${counts.total}</span>
          </div>
          <div style="display:flex;align-items:center;gap:8px;min-width:100px">
            <span style="font-size:10px;color:var(--bull)">${counts.bull}B</span>
            <span style="font-size:10px;color:var(--m)">${counts.neutral}N</span>
            <span style="font-size:10px;color:var(--bear)">${counts.bear}S</span>
          </div>
          <div style="width:80px">${renderStackedBar(counts)}</div>
          <span style="font-size:12px;color:var(--m);margin-left:4px">${isOpen ? '\u25B2' : '\u25BC'}</span>
        </div>
        <div class="cot-accordion-body" style="display:${isOpen ? 'grid' : 'none'};grid-template-columns:repeat(auto-fill,minmax(280px,1fr));gap:8px;padding:8px 0">
          ${items.map((d) => renderMarketCard(d)).join('')}
        </div>
      </div>`;
    })
    .join('');
}

// ── Public API ──────────────────────────────────────────────

/**
 * Build the COT panel skeleton.
 * @param {HTMLElement} container  #panel-cot
 */
export function render(container) {
  container.innerHTML = `
    <div class="sh"><h2 class="sh-t">COT-posisjoner</h2><div class="sh-b" id="cotCnt" aria-live="polite">-</div></div>
    <div class="sbar2" role="search" aria-label="Sok i COT-markeder">
      <label for="cotS" class="sr-only">Sok i COT-markeder</label>
      <input type="search" id="cotS" placeholder="Sok marked..." autocomplete="off" aria-label="Sok marked">
    </div>
    <div id="cotGrid" role="region" aria-label="COT accordion" aria-live="polite"></div>`;

  // Wire search input
  const searchInput = document.getElementById('cotS');
  if (searchInput) {
    searchInput.addEventListener('input', () => {
      searchQuery = searchInput.value.toLowerCase();
      renderAccordion();
    });
  }

  // Wire accordion toggle + card click (delegated)
  container.addEventListener('click', (e) => {
    // Accordion header toggle
    const header = e.target.closest('.cot-accordion-header');
    if (header) {
      const cat = header.dataset.cat;
      if (openCategories.has(cat)) {
        openCategories.delete(cat);
      } else {
        openCategories.add(cat);
      }
      renderAccordion();
      return;
    }

    // Market card click -> open chart
    const card = e.target.closest('.cot-market-card');
    if (card && onRowClick) {
      onRowClick(card.dataset.sym, card.dataset.report, decodeURIComponent(card.dataset.name));
    }
  });

  // Keyboard: Enter/Space on accordion headers and cards
  container.addEventListener('keydown', (e) => {
    if (e.key !== 'Enter' && e.key !== ' ') return;

    const header = e.target.closest('.cot-accordion-header');
    if (header) {
      e.preventDefault();
      const cat = header.dataset.cat;
      if (openCategories.has(cat)) {
        openCategories.delete(cat);
      } else {
        openCategories.add(cat);
      }
      renderAccordion();
      return;
    }

    const card = e.target.closest('.cot-market-card');
    if (card && onRowClick) {
      e.preventDefault();
      onRowClick(card.dataset.sym, card.dataset.report, decodeURIComponent(card.dataset.name));
    }
  });
}

/**
 * Reset internal state (used by tests).
 */
export function _reset() {
  allData = [];
  searchQuery = '';
  openCategories.clear();
  onRowClick = null;
}

/**
 * Update the table with fresh COT data.
 * @param {Array} data  Array of COT market objects
 */
export function update(data) {
  if (!Array.isArray(data)) return;
  allData = data;

  // Auto-open first category with data if none are open
  if (openCategories.size === 0 && data.length > 0) {
    const groups = groupByCategory(data);
    for (const cat of Object.keys(CATS)) {
      if (groups[cat] && groups[cat].length > 0) {
        openCategories.add(cat);
        break;
      }
    }
  }

  renderAccordion();
}
