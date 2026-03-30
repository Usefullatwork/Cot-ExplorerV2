/**
 * BacktestDashboard component — performance stats, equity curve, breakdowns.
 *
 * Visualizes backtest results with:
 * - 12-metric performance stats grid
 * - Equity curve (SVG line chart)
 * - Per-instrument breakdown table
 * - Per-grade breakdown bar chart
 */

import { escapeHtml, formatPct, colorClass, formatNumber } from '../utils.js';
import { renderSparkline } from '../charts/svgSparkline.js';

/** @type {Object|null} */
let cachedData = null;

/**
 * Build the backtest dashboard skeleton.
 * @param {HTMLElement} container  #panel-backtest
 */
export function render(container) {
  container.innerHTML = `
    <div class="sh"><h2 class="sh-t">Backtest Dashboard</h2><div class="sh-b" id="btUpdated" aria-live="polite">-</div></div>
    <div id="btStats" class="g4" role="group" aria-label="Ytelsesstatistikk"></div>
    <div class="sh" style="margin-top:16px"><h2 class="sh-t">Egenkapitalkurve</h2><div class="sh-b">Kumulativ PnL (R:R)</div></div>
    <div id="btEquity" style="text-align:center;padding:16px 0" role="img" aria-label="Egenkapitalkurve"></div>
    <div class="g22" style="margin-top:16px">
      <div>
        <div class="sh"><h2 class="sh-t">Per Instrument</h2></div>
        <div id="btInstruments" role="region" aria-label="Instrument-fordeling"></div>
      </div>
      <div>
        <div class="sh"><h2 class="sh-t">Per Klasse</h2></div>
        <div id="btGrades" role="region" aria-label="Klasse-fordeling"></div>
      </div>
    </div>`;
}

/**
 * Update the dashboard with backtest stats.
 * @param {Object} data  BacktestStatsResponse
 */
export function update(data) {
  if (!data) return;
  cachedData = data;

  // ── Stats grid (12 metrics) ────────────────────────────
  const statsEl = document.getElementById('btStats');
  if (statsEl) {
    const metrics = [
      { name: 'Totalt', val: data.total_trades, col: 'neutral' },
      { name: 'Gevinst', val: data.wins, col: 'bull' },
      { name: 'Tap', val: data.losses, col: 'bear' },
      { name: 'Win Rate', val: data.win_rate.toFixed(1) + '%', col: data.win_rate >= 50 ? 'bull' : 'bear' },
      { name: 'Snitt gevinst', val: data.avg_win_rr.toFixed(2) + 'R', col: 'bull' },
      { name: 'Snitt tap', val: data.avg_loss_rr.toFixed(2) + 'R', col: 'bear' },
      { name: 'Profit Factor', val: data.profit_factor.toFixed(2), col: data.profit_factor >= 1.5 ? 'bull' : data.profit_factor >= 1 ? 'warn' : 'bear' },
      { name: 'Maks DD', val: data.max_drawdown_rr.toFixed(2) + 'R', col: 'bear' },
      { name: 'Snitt R:R', val: data.avg_rr.toFixed(2), col: data.avg_rr > 0 ? 'bull' : 'bear' },
      { name: 'Beste trade', val: data.best_trade_rr.toFixed(2) + 'R', col: 'bull' },
      { name: 'Verste trade', val: data.worst_trade_rr.toFixed(2) + 'R', col: 'bear' },
      { name: 'Snitt varighet', val: data.avg_duration_hours.toFixed(0) + 't', col: 'neutral' },
    ];

    statsEl.innerHTML = metrics
      .map((m) => `<div class="card card-stat"><div class="ct">${escapeHtml(m.name)}</div><div class="snum ${m.col} mono">${m.val}</div></div>`)
      .join('');
  }

  // ── Equity curve (SVG sparkline, larger) ───────────────
  const eqEl = document.getElementById('btEquity');
  if (eqEl && data.equity_curve && data.equity_curve.length > 1) {
    const svg = renderSparkline(data.equity_curve, {
      width: 600,
      height: 120,
      strokeWidth: 2,
    });
    const lastVal = data.equity_curve[data.equity_curve.length - 1];
    eqEl.innerHTML = svg + `<div class="mono" style="margin-top:8px;font-size:14px;color:var(--${lastVal >= 0 ? 'bull' : 'bear'})">Total: ${lastVal >= 0 ? '+' : ''}${lastVal.toFixed(2)}R</div>`;
  } else if (eqEl) {
    eqEl.innerHTML = '<div class="empty-state" style="padding:24px 12px"><div class="empty-state-icon">\uD83D\uDCC8</div><div class="empty-state-title">Ingen backtest-data ennå</div><div class="empty-state-text">Kjør backtest for å generere egenkapitalkurven. Strategier finnes i <code>src/trading/backtesting/strategies/</code>.</div></div>';
  }

  // ── Per-instrument breakdown ───────────────────────────
  const instEl = document.getElementById('btInstruments');
  if (instEl && data.by_instrument && data.by_instrument.length > 0) {
    const rows = data.by_instrument
      .map((r) => `<tr><td>${escapeHtml(r.instrument)}</td><td style="text-align:right">${r.trades}</td><td style="text-align:right;color:var(--${r.win_rate >= 50 ? 'bull' : 'bear'})">${r.win_rate.toFixed(0)}%</td><td class="data-value" style="text-align:right;color:var(--${r.avg_pnl >= 0 ? 'bull' : 'bear'})">${r.avg_pnl >= 0 ? '+' : ''}${r.avg_pnl.toFixed(2)}R</td><td class="data-value" style="text-align:right;color:var(--${r.total_pnl >= 0 ? 'bull' : 'bear'})">${r.total_pnl >= 0 ? '+' : ''}${r.total_pnl.toFixed(2)}R</td></tr>`)
      .join('');
    instEl.innerHTML = `<div class="cotw"><table class="cott" aria-label="Instrument-fordeling"><thead><tr><th>Instrument</th><th style="text-align:right">Trades</th><th style="text-align:right">Win%</th><th style="text-align:right">Snitt</th><th style="text-align:right">Total</th></tr></thead><tbody>${rows}</tbody></table></div>`;
  } else if (instEl) {
    instEl.innerHTML = '<div style="color:var(--m);font-size:12px">Ingen data</div>';
  }

  // ── Per-grade breakdown ────────────────────────────────
  const gradeEl = document.getElementById('btGrades');
  if (gradeEl && data.by_grade && data.by_grade.length > 0) {
    const maxTrades = Math.max(...data.by_grade.map((g) => g.trades), 1);
    gradeEl.innerHTML = data.by_grade
      .map((g) => {
        const barWidth = Math.round((g.trades / maxTrades) * 100);
        const wr = g.win_rate.toFixed(0);
        const col = g.win_rate >= 60 ? 'bull' : g.win_rate >= 45 ? 'warn' : 'bear';
        return `<div style="margin-bottom:8px"><div style="display:flex;justify-content:space-between;font-size:12px;margin-bottom:2px"><span style="font-weight:600">${escapeHtml(g.grade)}</span><span>${g.trades} trades &middot; <span class="${col}">${wr}% win</span></span></div><div style="height:6px;background:var(--b2);border-radius:3px;overflow:hidden"><div style="width:${barWidth}%;height:100%;background:var(--${col});border-radius:3px"></div></div></div>`;
      })
      .join('');
  } else if (gradeEl) {
    gradeEl.innerHTML = '<div style="color:var(--m);font-size:12px">Ingen data</div>';
  }

  // Update timestamp
  const ts = document.getElementById('btUpdated');
  if (ts) ts.textContent = data.total_trades + ' trades';
}

/**
 * Fetch and display backtest stats.
 */
export async function refreshAll() {
  try {
    const { fetchBacktestStats } = await import('../api.js');
    const data = await fetchBacktestStats();
    update(data);
  } catch (e) {
    console.error('[BacktestDashboard]', e);
  }
}
