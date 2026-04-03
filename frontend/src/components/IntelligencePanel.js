/**
 * Intelligence Panel — sentiment, propagation, microstructure.
 * Tab: intelligence
 *
 * Shows NLP sentiment bars, signal propagation edges, and liquidity scores.
 */

import { fetchSentiment, fetchPropagation, fetchMicrostructure } from '../api.js';
import { escapeHtml } from '../utils.js';

/**
 * Build the intelligence panel skeleton.
 * @param {HTMLElement} container  #panel-intelligence
 */
export function render(container) {
  container.innerHTML = `
    <div class="sh"><h2 class="sh-t">Intelligence</h2><div class="sh-b">Sentiment, signalflyt og mikrostruktur</div></div>
    <div class="g22" style="margin-top:var(--sp-md)">
      <div>
        <div class="sh"><h2 class="sh-t">Sentiment per instrument</h2></div>
        <div class="card" id="intSentiment" role="region" aria-label="Sentiment-oversikt" style="overflow-x:auto">
          <div class="loading" role="status"><div class="spinner" aria-hidden="true"></div>Laster sentiment...</div>
        </div>
      </div>
      <div>
        <div class="sh"><h2 class="sh-t">Mikrostruktur</h2></div>
        <div class="card" id="intMicro" role="region" aria-label="Likviditetsoversikt" style="overflow-x:auto">
          <div class="loading" role="status"><div class="spinner" aria-hidden="true"></div>Laster mikrostruktur...</div>
        </div>
      </div>
    </div>
    <div class="sh" style="margin-top:var(--sp-lg)"><h2 class="sh-t">Signalflyt (Propagation)</h2><div class="sh-b">Hvordan signaler sprer seg mellom instrumenter</div></div>
    <div class="card" id="intPropagation" role="region" aria-label="Signal-propagasjon" style="overflow-x:auto">
      <div class="loading" role="status"><div class="spinner" aria-hidden="true"></div>Laster signalflyt...</div>
    </div>`;

  refreshAll();
}

/**
 * Fetch all intelligence data and render.
 */
export async function refreshAll() {
  try {
    const [sentiment, propagation, micro] = await Promise.all([
      fetchSentiment(),
      fetchPropagation(),
      fetchMicrostructure(),
    ]);
    renderSentiment(sentiment);
    renderPropagation(propagation);
    renderMicrostructure(micro);
  } catch (err) {
    const el = document.getElementById('intSentiment');
    if (el) {
      el.innerHTML = `<div class="error-card">Kunne ikke laste intelligence: ${escapeHtml(String(err))}</div>`;
    }
  }
}

/**
 * Render sentiment bars.
 * @param {Object} data  Sentiment response
 */
function renderSentiment(data) {
  const el = document.getElementById('intSentiment');
  if (!el || !data || !data.scores) return;

  const rows = data.scores
    .map((s) => {
      const pct = ((s.score + 1) / 2) * 100;
      const barColor = s.score > 0.1 ? 'var(--bull)' : s.score < -0.1 ? 'var(--bear)' : 'var(--m)';
      const labelCls = s.score > 0.1 ? 'bull' : s.score < -0.1 ? 'bear' : 'neutral';
      return `<div style="display:flex;align-items:center;gap:var(--sp-sm);padding:var(--sp-xs) 0">
        <span class="mono" style="width:70px;flex-shrink:0;font-size:var(--fs-sm)">${escapeHtml(s.instrument)}</span>
        <div style="flex:1;height:16px;background:var(--s2);border-radius:var(--radius-sm);position:relative;overflow:hidden" role="meter" aria-label="${escapeHtml(s.instrument)} sentiment" aria-valuenow="${s.score}" aria-valuemin="-1" aria-valuemax="1">
          <div style="position:absolute;left:50%;top:0;width:1px;height:100%;background:var(--b2)"></div>
          <div style="position:absolute;left:${Math.min(pct, 50)}%;width:${Math.abs(pct - 50)}%;top:2px;height:12px;background:${barColor};border-radius:var(--radius-sm);transition:width var(--ease)"></div>
        </div>
        <span class="mono ${labelCls}" style="width:50px;text-align:right;font-size:var(--fs-sm)">${s.score >= 0 ? '+' : ''}${s.score.toFixed(2)}</span>
        <span class="mono" style="width:50px;text-align:right;font-size:var(--fs-xs);color:var(--m)">${escapeHtml(String(s.sources))} src</span>
      </div>`;
    })
    .join('');

  el.innerHTML = `<div style="padding:var(--sp-sm)">${rows}</div>`;
}

/**
 * Render signal propagation edges.
 * @param {Object} data  Propagation response
 */
function renderPropagation(data) {
  const el = document.getElementById('intPropagation');
  if (!el || !data || !data.edges) return;

  const rows = data.edges
    .map((e) => {
      const arrow = e.direction === 'inverse' ? ' (inv)' : '';
      const strCls = e.strength >= 0.8 ? 'bull' : e.strength >= 0.6 ? 'neutral' : 'bear';
      return `<tr>
        <td class="mono">${escapeHtml(e.source)}</td>
        <td style="text-align:center;color:var(--m)">&rarr;</td>
        <td class="mono">${escapeHtml(e.target)}</td>
        <td class="mono">${escapeHtml(String(e.lag_hours))}t</td>
        <td class="mono ${strCls}">${e.strength.toFixed(2)}</td>
        <td class="mono" style="font-size:var(--fs-sm);color:var(--m)">${escapeHtml(e.direction)}${escapeHtml(arrow)}</td>
      </tr>`;
    })
    .join('');

  el.innerHTML = `
    <table class="data-table" aria-label="Signal-propagasjon">
      <thead>
        <tr>
          <th scope="col">Kilde</th>
          <th scope="col"></th>
          <th scope="col">Mal</th>
          <th scope="col">Lag</th>
          <th scope="col">Styrke</th>
          <th scope="col">Retning</th>
        </tr>
      </thead>
      <tbody>${rows}</tbody>
    </table>
    <div style="padding:var(--sp-sm) 0;font-size:var(--fs-sm);color:var(--m)">
      ${escapeHtml(String(data.total_nodes))} noder, ${escapeHtml(String(data.total_edges))} kanter
    </div>`;
}

/**
 * Render microstructure liquidity table.
 * @param {Object} data  Microstructure response
 */
function renderMicrostructure(data) {
  const el = document.getElementById('intMicro');
  if (!el || !data || !data.instruments) return;

  const rows = data.instruments
    .map((i) => {
      const liqCls = i.liquidity_score >= 0.85 ? 'bull' : i.liquidity_score >= 0.7 ? 'neutral' : 'bear';
      return `<tr>
        <td class="mono">${escapeHtml(i.instrument)}</td>
        <td class="mono ${liqCls}">${(i.liquidity_score * 100).toFixed(0)}%</td>
        <td class="mono">${i.spread_bps.toFixed(1)} bps</td>
        <td style="font-size:var(--fs-sm)">${escapeHtml(i.optimal_window)}</td>
      </tr>`;
    })
    .join('');

  el.innerHTML = `
    <table class="data-table" aria-label="Mikrostruktur">
      <thead>
        <tr>
          <th scope="col">Instrument</th>
          <th scope="col">Likviditet</th>
          <th scope="col">Spread</th>
          <th scope="col">Beste vindu</th>
        </tr>
      </thead>
      <tbody>${rows}</tbody>
    </table>`;
}
