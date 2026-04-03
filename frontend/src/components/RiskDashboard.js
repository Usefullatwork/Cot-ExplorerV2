/**
 * Risk Dashboard — VaR, stress tests, regime limits.
 * Tab: risk
 *
 * Shows VaR/CVaR metric cards, stress test table, and regime status.
 */

import { fetchRiskVar, fetchStressTest, fetchRegimeLimits } from '../api.js';
import { escapeHtml } from '../utils.js';

/** @type {Object|null} */
let cachedVar = null;
let cachedStress = null;
let cachedRegime = null;

/**
 * Build the risk dashboard skeleton.
 * @param {HTMLElement} container  #panel-risk
 */
export function render(container) {
  container.innerHTML = `
    <div class="sh"><h2 class="sh-t">Risikostyring</h2><div class="sh-b">VaR, stresstester og posisjonsgrenser</div></div>
    <div id="riskVarCards" class="g4" role="group" aria-label="VaR-metrikker">
      <div class="loading" role="status"><div class="spinner" aria-hidden="true"></div>Laster VaR...</div>
    </div>
    <div class="sh" style="margin-top:var(--sp-lg)"><h2 class="sh-t">Stresstester</h2><div class="sh-b">4 scenarioer</div></div>
    <div class="card" id="riskStressTable" role="region" aria-label="Stresstest-resultater" style="overflow-x:auto">
      <div class="loading" role="status"><div class="spinner" aria-hidden="true"></div>Laster stresstester...</div>
    </div>
    <div class="sh" style="margin-top:var(--sp-lg)"><h2 class="sh-t">Regime &amp; Posisjonsgrenser</h2></div>
    <div id="riskRegime" class="g4" role="group" aria-label="Regime-status">
      <div class="loading" role="status"><div class="spinner" aria-hidden="true"></div>Laster regime...</div>
    </div>`;

  refreshAll();
}

/**
 * Fetch all risk data in parallel and render.
 */
export async function refreshAll() {
  try {
    const [varData, stressData, regimeData] = await Promise.all([
      fetchRiskVar(),
      fetchStressTest(),
      fetchRegimeLimits(),
    ]);
    cachedVar = varData;
    cachedStress = stressData;
    cachedRegime = regimeData;
    renderVar(varData);
    renderStress(stressData);
    renderRegime(regimeData);
  } catch (err) {
    const el = document.getElementById('riskVarCards');
    if (el) {
      el.innerHTML = `<div class="error-card">Kunne ikke laste risikodata: ${escapeHtml(String(err))}</div>`;
    }
  }
}

/**
 * Render VaR metric cards.
 * @param {Object} data  VaR response
 */
function renderVar(data) {
  const el = document.getElementById('riskVarCards');
  if (!el || !data) return;

  const metrics = [
    { name: 'VaR 95%', val: data.var_95.toFixed(2) + '%', col: data.var_95 > 2 ? 'bear' : 'warn-text' },
    { name: 'VaR 99%', val: data.var_99.toFixed(2) + '%', col: data.var_99 > 3 ? 'bear' : 'warn-text' },
    { name: 'CVaR 95%', val: data.cvar_95.toFixed(2) + '%', col: data.cvar_95 > 2.5 ? 'bear' : 'warn-text' },
    { name: 'CVaR 99%', val: data.cvar_99.toFixed(2) + '%', col: data.cvar_99 > 4 ? 'bear' : 'warn-text' },
  ];

  el.innerHTML = metrics
    .map((m) => `<div class="card card-stat"><div class="ct">${escapeHtml(m.name)}</div><div class="snum ${m.col} mono">${escapeHtml(m.val)}</div></div>`)
    .join('');
}

/**
 * Render stress test results table.
 * @param {Object} data  Stress test response
 */
function renderStress(data) {
  const el = document.getElementById('riskStressTable');
  if (!el || !data || !data.scenarios) return;

  const rows = data.scenarios
    .map((s) => {
      const impactCls = s.portfolio_impact_pct >= 0 ? 'bull' : 'bear';
      const statusCls = s.status === 'pass' ? 'bull' : 'bear';
      const statusText = s.status === 'pass' ? 'Bestatt' : 'Feilet';
      return `<tr>
        <td>${escapeHtml(s.name)}</td>
        <td class="mono" style="max-width:200px;font-size:var(--fs-sm)">${escapeHtml(s.description)}</td>
        <td class="mono ${impactCls}">${s.portfolio_impact_pct >= 0 ? '+' : ''}${s.portfolio_impact_pct.toFixed(1)}%</td>
        <td class="mono bear">${s.max_drawdown_pct.toFixed(1)}%</td>
        <td>${s.var_breach ? '<span class="bear">Ja</span>' : '<span class="bull">Nei</span>'}</td>
        <td class="mono">${escapeHtml(String(s.surviving_positions))}/${escapeHtml(String(s.total_positions))}</td>
        <td><span class="badge ${statusCls}">${escapeHtml(statusText)}</span></td>
      </tr>`;
    })
    .join('');

  el.innerHTML = `
    <table class="data-table" aria-label="Stresstest-detaljer">
      <thead>
        <tr>
          <th scope="col">Scenario</th>
          <th scope="col">Beskrivelse</th>
          <th scope="col">Portefolje-effekt</th>
          <th scope="col">Maks DD</th>
          <th scope="col">VaR-brudd</th>
          <th scope="col">Overlevende</th>
          <th scope="col">Status</th>
        </tr>
      </thead>
      <tbody>${rows}</tbody>
    </table>`;
}

/**
 * Render regime and position limits.
 * @param {Object} data  Regime limits response
 */
function renderRegime(data) {
  const el = document.getElementById('riskRegime');
  if (!el || !data) return;

  const regimeCls = data.current_regime === 'NORMAL' ? 'bull'
    : data.current_regime === 'RISK_OFF' ? 'warn-text' : 'bear';

  const posUsage = data.current_positions / data.max_positions;
  const posCls = posUsage >= 0.9 ? 'bear' : posUsage >= 0.7 ? 'warn-text' : 'bull';

  const corrUsage = data.current_correlated / data.max_correlated_positions;
  const corrCls = corrUsage >= 0.9 ? 'bear' : corrUsage >= 0.7 ? 'warn-text' : 'bull';

  const sectorCls = data.current_sector_exposure_pct >= data.max_sector_exposure_pct * 0.9 ? 'bear'
    : data.current_sector_exposure_pct >= data.max_sector_exposure_pct * 0.7 ? 'warn-text' : 'bull';

  const metrics = [
    { name: 'Regime', val: escapeHtml(data.current_regime), col: regimeCls },
    { name: 'Posisjoner', val: `${data.current_positions}/${data.max_positions}`, col: posCls },
    { name: 'Korrelerte pos.', val: `${data.current_correlated}/${data.max_correlated_positions}`, col: corrCls },
    { name: 'Sektoreksponering', val: `${data.current_sector_exposure_pct.toFixed(1)}%/${data.max_sector_exposure_pct.toFixed(0)}%`, col: sectorCls },
  ];

  el.innerHTML = metrics
    .map((m) => `<div class="card card-stat"><div class="ct">${escapeHtml(m.name)}</div><div class="snum ${m.col} mono">${m.val}</div></div>`)
    .join('');
}
