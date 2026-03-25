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
      <div class="sh-t">Trading Setups</div>
      <div class="sh-b" id="ideDate">-</div>
      <div class="sh-b" id="vixSize" style="margin-left:4px">-</div>
    </div>
    <div class="g4" id="ideStats"></div>
    <div id="ideGrid"><div class="loading"><div class="spinner"></div>Laster...</div></div>`;
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
      '<div class="card"><div class="ct">A+ Setups</div><div class="snum bull">' + aplus + '</div><div class="slabel">Score 7-8/8</div></div>' +
      '<div class="card"><div class="ct">B Setups</div><div class="snum warn">' + bgrade + '</div><div class="slabel">Score 4-5/8</div></div>' +
      '<div class="card"><div class="ct">MAKRO Setups</div><div class="snum bull">' + makro + '</div><div class="slabel">COT + HTF struktur</div></div>' +
      '<div class="card"><div class="ct">Binar risiko</div><div class="snum bear">' + risk + '</div><div class="slabel">High impact neste 4t</div></div>';
  }

  // Grid of SetupCards
  const gridEl = document.getElementById('ideGrid');
  if (!gridEl) return;

  if (!arr.length) {
    gridEl.innerHTML = '<div class="loading">Ingen data - kjor fetch_all.py</div>';
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
