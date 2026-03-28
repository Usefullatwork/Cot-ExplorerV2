/**
 * SetupGrid component — container for all 12 SetupCards.
 *
 * Renders 4 stat summary cards at top, then a sorted list of SetupCards.
 * Subscribes to state.signals for live updates.
 */

import { renderCard, attachToggle } from './SetupCard.js';
import { escapeHtml } from '../utils.js';

// ── Filter state ──────────────────────────────────────────────
let filterGrade = 'alle';
let filterTimeframe = 'alle';
let filterClass = 'alle';
let allSignals = [];

/**
 * Build the initial DOM inside the setups panel.
 * @param {HTMLElement} container  #panel-setups
 */
export function render(container) {
  container.innerHTML = `
    <div class="sh">
      <h2 class="sh-t">Trading Setups</h2>
      <div class="sh-b" id="ideDate" aria-live="polite">-</div>
      <div class="sh-b" id="vixSize" style="margin-left:4px" role="status" aria-live="polite">-</div>
    </div>
    <div class="g4" id="ideStats">
      <div class="card skeleton-card"><div class="skeleton-row" style="height:12px;width:60%"></div><div class="skeleton-row" style="height:26px;width:40%;margin-top:8px"></div><div class="skeleton-row" style="height:10px;width:80%;margin-top:8px"></div></div>
      <div class="card skeleton-card"><div class="skeleton-row" style="height:12px;width:60%"></div><div class="skeleton-row" style="height:26px;width:40%;margin-top:8px"></div><div class="skeleton-row" style="height:10px;width:80%;margin-top:8px"></div></div>
      <div class="card skeleton-card"><div class="skeleton-row" style="height:12px;width:60%"></div><div class="skeleton-row" style="height:26px;width:40%;margin-top:8px"></div><div class="skeleton-row" style="height:10px;width:80%;margin-top:8px"></div></div>
      <div class="card skeleton-card"><div class="skeleton-row" style="height:12px;width:60%"></div><div class="skeleton-row" style="height:26px;width:40%;margin-top:8px"></div><div class="skeleton-row" style="height:10px;width:80%;margin-top:8px"></div></div>
    </div>
    <div class="sbar2" id="setupFilters" role="search" aria-label="Filtrer setups" style="margin-bottom:12px">
      <div id="setupFilterChips" role="group" aria-label="Setup-filter" style="display:flex;gap:8px;flex-wrap:wrap"></div>
    </div>
    <div id="ideGrid">
      <div class="skeleton-card-list">
        <div class="skeleton-card-item"><div class="skeleton-row" style="height:48px"></div></div>
        <div class="skeleton-card-item"><div class="skeleton-row" style="height:48px"></div></div>
        <div class="skeleton-card-item"><div class="skeleton-row" style="height:48px"></div></div>
      </div>
    </div>`;
}

/** Sort helpers */
const gradeOrder = { 'A+': -1, 'A': 0, 'B': 1, 'C': 2 };
const tfOrder = { 'MAKRO': -1, 'SWING': 0, 'SCALP': 1, 'WATCHLIST': 2 };

function sortSetups(arr) {
  return arr.slice().sort((a, b) => {
    const gd = (gradeOrder[a.grade] ?? 2) - (gradeOrder[b.grade] ?? 2);
    if (gd !== 0) return gd;
    const td = (tfOrder[a.timeframe_bias] || 0) - (tfOrder[b.timeframe_bias] || 0);
    if (td !== 0) return td;
    return (b.score || 0) - (a.score || 0);
  });
}

function filterSetups(arr) {
  return arr.filter((l) => {
    if (filterGrade !== 'alle' && l.grade !== filterGrade) return false;
    if (filterTimeframe !== 'alle' && l.timeframe_bias !== filterTimeframe) return false;
    if (filterClass !== 'alle' && l.class !== filterClass) return false;
    return true;
  });
}

function renderFilterChips(arr) {
  const chipEl = document.getElementById('setupFilterChips');
  if (!chipEl) return;

  const grades = ['alle', ...new Set(arr.map((l) => l.grade).filter(Boolean))];
  const timeframes = ['alle', ...new Set(arr.map((l) => l.timeframe_bias).filter(Boolean))];
  const classes = ['alle', ...new Set(arr.map((l) => l.class).filter(Boolean))];

  const mkChips = (items, current, prefix, label) =>
    `<div style="display:flex;gap:4px;align-items:center"><span style="font-size:10px;color:var(--m);min-width:40px">${label}:</span>${items.map((g) => `<button class="fc${g === current ? ' on' : ''}" data-filter="${prefix}" data-val="${escapeHtml(g)}" style="font-size:10px;padding:2px 8px">${escapeHtml(g === 'alle' ? 'Alle' : g)}</button>`).join('')}</div>`;

  chipEl.innerHTML = mkChips(grades, filterGrade, 'grade', 'Klasse') + mkChips(timeframes, filterTimeframe, 'tf', 'TF') + mkChips(classes, filterClass, 'cls', 'Type');
}

function renderGrid(arr) {
  const gridEl = document.getElementById('ideGrid');
  if (!gridEl) return;

  const filtered = filterSetups(arr);
  const sorted = sortSetups(filtered);

  if (!sorted.length) {
    const isFiltered = filterGrade !== 'alle' || filterTimeframe !== 'alle' || filterClass !== 'alle';
    gridEl.innerHTML = `<div class="empty-state">
      <div class="empty-state-icon">${isFiltered ? '\uD83D\uDD0D' : '\uD83D\uDCCA'}</div>
      <div class="empty-state-title">${isFiltered ? 'Ingen treff' : 'Ingen trading setups'}</div>
      <div class="empty-state-text">${isFiltered ? 'Prov a endre filter.' : 'Kjor <code>fetch_all.py</code> for a hente ferske data fra CFTC og beregne setups.'}</div>
    </div>`;
    return;
  }

  gridEl.innerHTML = sorted.map((lv, i) => renderCard(lv, i)).join('');
  attachToggle(gridEl);
}

/**
 * Update the grid with fresh signal data.
 * @param {Object} data  Full macro/signals payload (trading_levels, vix_regime, cot_date, etc.)
 */
export function update(data) {
  if (!data) return;

  const lvs = data.trading_levels || {};
  allSignals = Object.values(lvs);

  // Date badge
  const ideDate = document.getElementById('ideDate');
  if (ideDate) ideDate.textContent = 'COT per ' + (data.cot_date || '-');

  // VIX size badge
  const vr = data.vix_regime || {};
  const vsEl = document.getElementById('vixSize');
  if (vsEl) {
    vsEl.textContent = vr.label || '-';
    vsEl.style.color = 'var(--' + (vr.color || 'm') + ')';
  }

  // Summary stats (always show ALL, not filtered)
  const aplus = allSignals.filter((l) => l.grade === 'A+').length;
  const agrade = allSignals.filter((l) => l.grade === 'A').length;
  const bgrade = allSignals.filter((l) => l.grade === 'B').length;
  const makro = allSignals.filter((l) => l.timeframe_bias === 'MAKRO').length;
  const risk = allSignals.filter((l) => l.binary_risk && l.binary_risk.length > 0).length;

  const statsEl = document.getElementById('ideStats');
  if (statsEl) {
    statsEl.innerHTML =
      '<div class="card" role="status" aria-label="A+ setups: ' + aplus + '"><div class="ct">A+ Setups</div><div class="snum bull">' + aplus + '</div><div class="slabel">Score 7-8/8</div></div>' +
      '<div class="card" role="status" aria-label="A setups: ' + agrade + '"><div class="ct">A Setups</div><div class="snum bull">' + agrade + '</div><div class="slabel">Score 6/8</div></div>' +
      '<div class="card" role="status" aria-label="MAKRO setups: ' + makro + '"><div class="ct">MAKRO</div><div class="snum bull">' + makro + '</div><div class="slabel">COT + HTF</div></div>' +
      '<div class="card" role="status" aria-label="Binar risiko: ' + risk + '"><div class="ct">Binar risiko</div><div class="snum bear">' + risk + '</div><div class="slabel">High impact</div></div>';
  }

  // Render filter chips
  renderFilterChips(allSignals);

  // Wire filter click handler (delegated, only once)
  const filterEl = document.getElementById('setupFilters');
  if (filterEl && !filterEl.dataset.wired) {
    filterEl.dataset.wired = '1';
    filterEl.addEventListener('click', (e) => {
      const btn = e.target.closest('[data-filter]');
      if (!btn) return;
      const prefix = btn.dataset.filter;
      const val = btn.dataset.val;
      if (prefix === 'grade') filterGrade = val;
      else if (prefix === 'tf') filterTimeframe = val;
      else if (prefix === 'cls') filterClass = val;
      renderFilterChips(allSignals);
      renderGrid(allSignals);
    });
  }

  // Render grid
  renderGrid(allSignals);
}
