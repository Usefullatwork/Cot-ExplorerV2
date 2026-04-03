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
    </div>
    <div style="margin-top:24px">
      <div class="sh"><h2 class="sh-t">Drawdown</h2><div class="sh-b">Kumulativ drawdown (R:R)</div></div>
      <div id="btDrawdown" style="text-align:center;padding:16px 0" role="img" aria-label="Drawdown-kurve"></div>
    </div>
    <div style="margin-top:24px">
      <div class="sh"><h2 class="sh-t">Månedlig avkastning</h2><div class="sh-b">Heatmap per måned</div></div>
      <div id="btMonthly" role="region" aria-label="Månedlig heatmap" style="overflow-x:auto"></div>
    </div>
    <div style="margin-top:24px">
      <div class="sh"><h2 class="sh-t">Walk-Forward Optimalisering</h2><div class="sh-b">OOS-validering + PBO</div></div>
      <div id="btWfo" role="region" aria-label="WFO-resultater"></div>
    </div>
    <div style="margin-top:24px">
      <div class="sh"><h2 class="sh-t">Strategisammenligning</h2><div class="sh-b">WFO-basert</div></div>
      <div id="btStratCompare" role="region" aria-label="Strategisammenligning"></div>
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

  // ── Drawdown curve ─────────────────────────────────────
  updateDrawdown(data.equity_curve);

  // ── Monthly heatmap ───────────────────────────────────
  updateMonthlyHeatmap(data);

  // Update timestamp
  const ts = document.getElementById('btUpdated');
  if (ts) ts.textContent = data.total_trades + ' trades';
}

// ── WFO Section ──────────────────────────────────────────────

/**
 * Render the WFO results section below the signal-based stats.
 * @param {Array} runs  List of WfoRunResponse objects
 */
function updateWfo(runs) {
  const wfoEl = document.getElementById('btWfo');
  if (!wfoEl) return;

  if (!runs || runs.length === 0) {
    wfoEl.innerHTML = '<div class="empty-state" style="padding:16px"><div class="empty-state-title">Ingen WFO-resultater</div><div class="empty-state-text">Kjør walk-forward optimalisering via POST /api/v1/backtests/wfo/run</div></div>';
    return;
  }

  const rows = runs
    .map((r) => {
      const pboColor = r.pbo_rating === 'green' ? 'bull' : r.pbo_rating === 'yellow' ? 'warn' : 'bear';
      const pboVal = r.pbo_score !== null ? r.pbo_score.toFixed(3) : '-';
      const score = r.best_test_score !== null ? r.best_test_score.toFixed(4) : '-';
      const strat = r.best_strategy || '-';
      const tf = r.best_timeframe || '-';
      const warnings = r.overfit_warnings ? r.overfit_warnings.length : 0;
      const runtime = r.runtime_seconds ? r.runtime_seconds.toFixed(1) + 's' : '-';

      return `<tr>
        <td>${escapeHtml(r.instrument)}</td>
        <td>${escapeHtml(strat)}</td>
        <td style="text-align:center">${escapeHtml(tf)}</td>
        <td class="data-value" style="text-align:right">${score}</td>
        <td style="text-align:center"><span class="tag ${pboColor}">${pboVal}</span></td>
        <td style="text-align:right">${r.total_windows}</td>
        <td style="text-align:right;color:var(--${warnings > 0 ? 'warn' : 'm'})">${warnings}</td>
        <td style="text-align:right;color:var(--m)">${runtime}</td>
      </tr>`;
    })
    .join('');

  wfoEl.innerHTML = `<div class="cotw"><table class="cott" aria-label="WFO-resultater">
    <thead><tr>
      <th>Instrument</th><th>Beste strategi</th><th style="text-align:center">TF</th>
      <th style="text-align:right">OOS Score</th><th style="text-align:center">PBO</th>
      <th style="text-align:right">Vinduer</th><th style="text-align:right">Advarsler</th>
      <th style="text-align:right">Tid</th>
    </tr></thead>
    <tbody>${rows}</tbody>
  </table></div>`;
}

// ── Drawdown curve ──────────────────────────────────────────

/**
 * Render drawdown waterfall from equity curve data.
 * @param {number[]} equityCurve  Cumulative PnL series
 */
function updateDrawdown(equityCurve) {
  const el = document.getElementById('btDrawdown');
  if (!el) return;

  if (!equityCurve || equityCurve.length < 2) {
    el.innerHTML = '<div style="color:var(--m);font-size:12px">Ikke nok data for drawdown-kurve</div>';
    return;
  }

  // Calculate drawdown series
  const dd = [];
  let peak = equityCurve[0];
  for (const val of equityCurve) {
    if (val > peak) peak = val;
    dd.push(val - peak); // always <= 0
  }

  const svg = renderSparkline(dd, {
    width: 600,
    height: 80,
    strokeWidth: 2,
    color: '#f85149',
  });

  const maxDD = Math.min(...dd);
  el.innerHTML = svg + `<div class="mono" style="margin-top:8px;font-size:12px;color:var(--bear)">Maks drawdown: ${maxDD.toFixed(2)}R</div>`;
}

// ── Monthly returns heatmap ─────────────────────────────────

/**
 * Render monthly returns heatmap from trade data.
 * @param {Object} data  BacktestStatsResponse with monthly_returns
 */
function updateMonthlyHeatmap(data) {
  const el = document.getElementById('btMonthly');
  if (!el) return;

  // Build monthly returns from equity curve if no explicit field
  const monthly = data.monthly_returns;
  if (!monthly || !monthly.length) {
    // Derive from equity curve dates if possible, or show placeholder
    if (data.equity_curve && data.equity_curve.length > 20) {
      // Split equity curve into ~monthly chunks (approx 20 trades/month)
      const chunkSize = Math.max(Math.floor(data.equity_curve.length / 12), 2);
      const chunks = [];
      for (let i = 0; i < data.equity_curve.length; i += chunkSize) {
        const slice = data.equity_curve.slice(i, i + chunkSize);
        const start = i === 0 ? 0 : data.equity_curve[i - 1];
        const end = slice[slice.length - 1];
        chunks.push(end - start);
      }
      renderHeatmapGrid(el, chunks);
    } else {
      el.innerHTML = '<div style="color:var(--m);font-size:12px">Ikke nok data for månedlig heatmap</div>';
    }
    return;
  }

  renderHeatmapGrid(el, monthly.map((m) => m.pnl_r || 0));
}

/**
 * Render a grid of colored cells from numeric values.
 * @param {HTMLElement} el  Container element
 * @param {number[]} values  PnL values per period
 */
function renderHeatmapGrid(el, values) {
  const maxAbs = Math.max(...values.map(Math.abs), 0.01);

  const cells = values.map((v, i) => {
    const intensity = Math.min(Math.abs(v) / maxAbs, 1);
    const bg = v >= 0
      ? `rgba(63, 185, 80, ${(0.15 + intensity * 0.6).toFixed(2)})`
      : `rgba(248, 81, 73, ${(0.15 + intensity * 0.6).toFixed(2)})`;
    const textCol = intensity > 0.5 ? '#fff' : 'var(--t)';
    return `<div style="background:${bg};color:${textCol};padding:8px 6px;text-align:center;border-radius:var(--radius-sm);font-size:11px;font-family:'DM Mono',monospace;min-width:50px" title="Periode ${i + 1}: ${v >= 0 ? '+' : ''}${v.toFixed(2)}R">${v >= 0 ? '+' : ''}${v.toFixed(1)}R</div>`;
  }).join('');

  el.innerHTML = `<div style="display:flex;gap:4px;flex-wrap:wrap">${cells}</div>`;
}

// ── Strategy comparison table ───────────────────────────────

/**
 * Render strategy comparison from WFO runs.
 * @param {Array} runs  WfoRunResponse objects
 */
function updateStrategyComparison(runs) {
  const el = document.getElementById('btStratCompare');
  if (!el) return;

  if (!runs || runs.length === 0) {
    el.innerHTML = '<div style="color:var(--m);font-size:12px">Ingen WFO-data for sammenligning</div>';
    return;
  }

  // Group by strategy
  const byStrategy = {};
  for (const r of runs) {
    const s = r.best_strategy || 'unknown';
    if (!byStrategy[s]) {
      byStrategy[s] = { instruments: 0, avgScore: 0, avgPbo: 0, totalWindows: 0, scores: [], pbos: [] };
    }
    byStrategy[s].instruments++;
    byStrategy[s].totalWindows += r.total_windows || 0;
    if (r.best_test_score != null) byStrategy[s].scores.push(r.best_test_score);
    if (r.pbo_score != null) byStrategy[s].pbos.push(r.pbo_score);
  }

  const strategies = Object.entries(byStrategy).map(([name, d]) => {
    const avgScore = d.scores.length > 0 ? d.scores.reduce((a, b) => a + b, 0) / d.scores.length : null;
    const avgPbo = d.pbos.length > 0 ? d.pbos.reduce((a, b) => a + b, 0) / d.pbos.length : null;
    return { name, instruments: d.instruments, avgScore, avgPbo, totalWindows: d.totalWindows };
  }).sort((a, b) => (b.avgScore || 0) - (a.avgScore || 0));

  const rows = strategies.map((s) => {
    const scoreCls = (s.avgScore || 0) > 0 ? 'bull' : 'bear';
    const pboCls = s.avgPbo != null ? (s.avgPbo < 0.3 ? 'bull' : s.avgPbo < 0.5 ? 'warn' : 'bear') : 'm';
    const pboLabel = s.avgPbo != null ? s.avgPbo.toFixed(3) : '-';
    return `<tr>
      <td style="font-weight:600">${escapeHtml(s.name)}</td>
      <td style="text-align:center">${s.instruments}</td>
      <td class="mono ${scoreCls}" style="text-align:right">${s.avgScore != null ? s.avgScore.toFixed(4) : '-'}</td>
      <td style="text-align:center"><span class="tag ${pboCls}">${pboLabel}</span></td>
      <td style="text-align:right">${s.totalWindows}</td>
    </tr>`;
  }).join('');

  el.innerHTML = `<div class="cotw"><table class="cott" aria-label="Strategisammenligning">
    <thead><tr>
      <th>Strategi</th><th style="text-align:center">Instrumenter</th>
      <th style="text-align:right">Snitt OOS</th><th style="text-align:center">Snitt PBO</th>
      <th style="text-align:right">Vinduer</th>
    </tr></thead>
    <tbody>${rows}</tbody>
  </table></div>`;
}

/**
 * Fetch and display backtest stats + WFO results.
 */
export async function refreshAll() {
  try {
    const { fetchBacktestStats, fetchWfoRuns } = await import('../api.js');
    const [statsData, wfoData] = await Promise.all([
      fetchBacktestStats().catch(() => null),
      fetchWfoRuns().catch(() => []),
    ]);
    update(statsData);
    updateWfo(wfoData);
    updateStrategyComparison(wfoData);
  } catch (e) {
    console.error('[BacktestDashboard]', e);
  }
}
