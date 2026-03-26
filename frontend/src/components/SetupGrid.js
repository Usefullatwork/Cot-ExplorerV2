/**
 * SetupGrid component — container for all 12 SetupCards.
 *
 * Renders 4 stat summary cards at top, then a sorted list of SetupCards.
 * Subscribes to state.signals for live updates.
 */

import { renderCard, attachToggle } from './SetupCard.js';

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
    <div id="ideGrid">
      <div class="skeleton-card-list">
        <div class="skeleton-card-item"><div class="skeleton-row" style="height:48px"></div></div>
        <div class="skeleton-card-item"><div class="skeleton-row" style="height:48px"></div></div>
        <div class="skeleton-card-item"><div class="skeleton-row" style="height:48px"></div></div>
      </div>
    </div>`;
}

/**
 * Update the grid with fresh signal data.
 * @param {Object} data  Full macro/signals payload (trading_levels, vix_regime, cot_date, etc.)
 */
export function update(data) {
  if (!data) return;

  const lvs = data.trading_levels || {};
  const arr = Object.values(lvs);

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

  // Summary stats
  const aplus = arr.filter((l) => l.grade === 'A+').length;
  const bgrade = arr.filter((l) => l.grade === 'B').length;
  const makro = arr.filter((l) => l.timeframe_bias === 'MAKRO').length;
  const risk = arr.filter((l) => l.binary_risk && l.binary_risk.length > 0).length;

  const statsEl = document.getElementById('ideStats');
  if (statsEl) {
    statsEl.innerHTML =
      '<div class="card" role="status" aria-label="A+ setups: ' + aplus + '"><div class="ct">A+ Setups</div><div class="snum bull">' + aplus + '</div><div class="slabel">Score 7-8/8</div></div>' +
      '<div class="card" role="status" aria-label="B setups: ' + bgrade + '"><div class="ct">B Setups</div><div class="snum warn">' + bgrade + '</div><div class="slabel">Score 4-5/8</div></div>' +
      '<div class="card" role="status" aria-label="MAKRO setups: ' + makro + '"><div class="ct">MAKRO Setups</div><div class="snum bull">' + makro + '</div><div class="slabel">COT + HTF struktur</div></div>' +
      '<div class="card" role="status" aria-label="Binar risiko: ' + risk + '"><div class="ct">Binar risiko</div><div class="snum bear">' + risk + '</div><div class="slabel">High impact neste 4t</div></div>';
  }

  // Grid of SetupCards
  const gridEl = document.getElementById('ideGrid');
  if (!gridEl) return;

  if (!arr.length) {
    gridEl.innerHTML = `<div class="empty-state">
      <div class="empty-state-icon">\uD83D\uDCCA</div>
      <div class="empty-state-title">Ingen trading setups</div>
      <div class="empty-state-text">Kjor <code>fetch_all.py</code> for a hente ferske data fra CFTC og beregne setups.</div>
    </div>`;
    return;
  }

  // Sort: grade (A+ first), then timeframe, then score descending
  const gradeOrder = { 'A+': -1, 'A': 0, 'B': 1, 'C': 2 };
  const tfOrder = { 'MAKRO': -1, 'SWING': 0, 'SCALP': 1, 'WATCHLIST': 2 };

  arr.sort((a, b) => {
    const gd = (gradeOrder[a.grade] ?? 2) - (gradeOrder[b.grade] ?? 2);
    if (gd !== 0) return gd;
    const td = (tfOrder[a.timeframe_bias] || 0) - (tfOrder[b.timeframe_bias] || 0);
    if (td !== 0) return td;
    return (b.score || 0) - (a.score || 0);
  });

  gridEl.innerHTML = arr.map((lv, i) => renderCard(lv, i)).join('');
  attachToggle(gridEl);
}
