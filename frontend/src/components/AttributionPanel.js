/**
 * Attribution Panel — performance attribution breakdown.
 * Tab: attribution
 *
 * Shows per-signal PnL bars, regime performance table, and sizing alpha.
 */

import { fetchAttribution } from '../api.js';
import { escapeHtml } from '../utils.js';

/**
 * Build the attribution panel skeleton.
 * @param {HTMLElement} container  #panel-attribution
 */
export function render(container) {
  container.innerHTML = `
    <div class="sh"><h2 class="sh-t">Performance Attribution</h2><div class="sh-b" id="attrTotal" aria-live="polite">-</div></div>
    <div id="attrSizing" class="g4" role="group" aria-label="Sizing-metrikker" style="margin-bottom:var(--sp-lg)"></div>
    <div class="g22">
      <div>
        <div class="sh"><h2 class="sh-t">PnL per signal</h2><div class="sh-b">19-punkt ensemble bidrag (R-multiples)</div></div>
        <div class="card" id="attrSignalBars" role="region" aria-label="Signal PnL-bidrag" style="overflow-x:auto">
          <div class="loading" role="status"><div class="spinner" aria-hidden="true"></div>Laster attribusjon...</div>
        </div>
      </div>
      <div>
        <div class="sh"><h2 class="sh-t">Regime-ytelse</h2></div>
        <div class="card" id="attrRegimeTable" role="region" aria-label="Regime-ytelse" style="overflow-x:auto">
          <div class="loading" role="status"><div class="spinner" aria-hidden="true"></div>Laster regime-data...</div>
        </div>
      </div>
    </div>`;

  refreshAll();
}

/**
 * Fetch and render attribution data.
 */
export async function refreshAll() {
  try {
    const data = await fetchAttribution();
    update(data);
  } catch (err) {
    const el = document.getElementById('attrSignalBars');
    if (el) {
      el.innerHTML = `<div class="error-card">Kunne ikke laste attribusjon: ${escapeHtml(String(err))}</div>`;
    }
  }
}

/**
 * Update the panel with attribution data.
 * @param {Object} data  Attribution response
 */
export function update(data) {
  if (!data) return;

  // Total summary
  const totalEl = document.getElementById('attrTotal');
  if (totalEl) {
    const cls = data.total_pnl_r >= 0 ? 'bull' : 'bear';
    totalEl.innerHTML = `<span class="${cls} mono">Total: ${data.total_pnl_r >= 0 ? '+' : ''}${data.total_pnl_r.toFixed(1)}R</span> | ${escapeHtml(String(data.total_trades))} trades`;
  }

  // Sizing alpha cards
  renderSizing(data.sizing_alpha);

  // Signal PnL bars
  renderSignalBars(data.signal_pnl);

  // Regime table
  renderRegimeTable(data.regime_performance);
}

/**
 * Render sizing alpha metric cards.
 * @param {Object} sizing  Sizing alpha data
 */
function renderSizing(sizing) {
  const el = document.getElementById('attrSizing');
  if (!el || !sizing) return;

  const metrics = [
    { name: 'Full size PnL', val: `${sizing.full_size_pnl_r >= 0 ? '+' : ''}${sizing.full_size_pnl_r.toFixed(1)}R`, col: sizing.full_size_pnl_r >= 0 ? 'bull' : 'bear' },
    { name: 'Halv size PnL', val: `${sizing.half_size_pnl_r >= 0 ? '+' : ''}${sizing.half_size_pnl_r.toFixed(1)}R`, col: sizing.half_size_pnl_r >= 0 ? 'bull' : 'bear' },
    { name: 'Kvart size PnL', val: `${sizing.quarter_size_pnl_r >= 0 ? '+' : ''}${sizing.quarter_size_pnl_r.toFixed(1)}R`, col: sizing.quarter_size_pnl_r >= 0 ? 'bull' : 'bear' },
    { name: 'Sizing-alfa', val: `+${sizing.sizing_contribution_pct.toFixed(1)}%`, col: 'bull' },
  ];

  el.innerHTML = metrics
    .map((m) => `<div class="card card-stat"><div class="ct">${escapeHtml(m.name)}</div><div class="snum ${m.col} mono">${escapeHtml(m.val)}</div></div>`)
    .join('');
}

/**
 * Render horizontal bar chart for per-signal PnL.
 * @param {Array} signals  Signal PnL array
 */
function renderSignalBars(signals) {
  const el = document.getElementById('attrSignalBars');
  if (!el || !signals) return;

  // Find max absolute PnL for scaling
  const maxAbs = Math.max(...signals.map((s) => Math.abs(s.pnl_r)), 1);

  const rows = signals
    .sort((a, b) => b.pnl_r - a.pnl_r)
    .map((s) => {
      const pct = (Math.abs(s.pnl_r) / maxAbs) * 100;
      const isPositive = s.pnl_r >= 0;
      const barColor = isPositive ? 'var(--bull)' : 'var(--bear)';
      const valCls = isPositive ? 'bull' : 'bear';
      const wrCls = s.win_rate >= 0.58 ? 'bull' : s.win_rate >= 0.54 ? 'neutral' : 'bear';
      return `<div style="display:flex;align-items:center;gap:var(--sp-sm);padding:3px 0">
        <span class="mono" style="width:100px;flex-shrink:0;font-size:var(--fs-sm);text-align:right">${escapeHtml(s.signal)}</span>
        <div style="flex:1;height:14px;background:var(--s2);border-radius:var(--radius-sm);position:relative;overflow:hidden">
          <div style="width:${pct.toFixed(1)}%;height:100%;background:${barColor};border-radius:var(--radius-sm);transition:width var(--ease)"></div>
        </div>
        <span class="mono ${valCls}" style="width:55px;text-align:right;font-size:var(--fs-sm)">${isPositive ? '+' : ''}${s.pnl_r.toFixed(1)}R</span>
        <span class="mono ${wrCls}" style="width:45px;text-align:right;font-size:var(--fs-xs)">${(s.win_rate * 100).toFixed(0)}%</span>
        <span class="mono" style="width:30px;text-align:right;font-size:var(--fs-xs);color:var(--m)">${escapeHtml(String(s.trades))}</span>
      </div>`;
    })
    .join('');

  el.innerHTML = `
    <div style="display:flex;gap:var(--sp-sm);padding:var(--sp-xs) 0;font-size:var(--fs-xs);color:var(--m);border-bottom:1px solid var(--b)">
      <span style="width:100px;text-align:right">Signal</span>
      <span style="flex:1">PnL-bidrag</span>
      <span style="width:55px;text-align:right">PnL</span>
      <span style="width:45px;text-align:right">WR</span>
      <span style="width:30px;text-align:right">#</span>
    </div>
    ${rows}`;
}

/**
 * Render regime performance table.
 * @param {Array} regimes  Regime performance array
 */
function renderRegimeTable(regimes) {
  const el = document.getElementById('attrRegimeTable');
  if (!el || !regimes) return;

  const rows = regimes
    .map((r) => {
      const pnlCls = r.pnl_r >= 0 ? 'bull' : 'bear';
      const wrCls = r.win_rate >= 0.55 ? 'bull' : r.win_rate >= 0.50 ? 'neutral' : 'bear';
      const rrCls = r.avg_rr >= 1.2 ? 'bull' : r.avg_rr >= 1.0 ? 'neutral' : 'bear';
      return `<tr>
        <td class="mono">${escapeHtml(r.regime)}</td>
        <td class="mono ${pnlCls}">${r.pnl_r >= 0 ? '+' : ''}${r.pnl_r.toFixed(1)}R</td>
        <td class="mono">${escapeHtml(String(r.trades))}</td>
        <td class="mono ${wrCls}">${(r.win_rate * 100).toFixed(0)}%</td>
        <td class="mono ${rrCls}">${r.avg_rr.toFixed(2)}</td>
      </tr>`;
    })
    .join('');

  el.innerHTML = `
    <table class="data-table" aria-label="Regime-ytelse">
      <thead>
        <tr>
          <th scope="col">Regime</th>
          <th scope="col">PnL</th>
          <th scope="col">Trades</th>
          <th scope="col">Win Rate</th>
          <th scope="col">Snitt R:R</th>
        </tr>
      </thead>
      <tbody>${rows}</tbody>
    </table>`;
}
