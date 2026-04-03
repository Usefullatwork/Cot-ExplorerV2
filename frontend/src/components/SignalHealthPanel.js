/**
 * Signal Health Panel — ensemble health monitoring.
 * Tab: signal-health
 *
 * Shows ensemble quality, per-signal stats table, and alerts.
 */

import { fetchSignalHealth } from '../api.js';
import { escapeHtml } from '../utils.js';

/** @type {Object|null} */
let cachedData = null;

/**
 * Status badge HTML for signal status.
 * @param {string} status  'active' | 'excluded' | 'decayed'
 * @returns {string}
 */
function statusBadge(status) {
  const map = {
    active: { cls: 'bull', text: 'Aktiv' },
    excluded: { cls: 'bear', text: 'Ekskludert' },
    decayed: { cls: 'warn-text', text: 'Forfalt' },
  };
  const m = map[status] || { cls: 'neutral', text: status };
  return `<span class="badge ${m.cls}">${escapeHtml(m.text)}</span>`;
}

/**
 * Quality badge for ensemble status.
 * @param {string} quality  'healthy' | 'degraded' | 'critical'
 * @returns {string}
 */
function qualityBadge(quality) {
  const map = {
    healthy: { cls: 'bull', text: 'Frisk' },
    degraded: { cls: 'warn-text', text: 'Degradert' },
    critical: { cls: 'bear', text: 'Kritisk' },
  };
  const m = map[quality] || { cls: 'neutral', text: quality };
  return `<span class="badge ${m.cls}" style="font-size:var(--fs-lg);padding:var(--sp-xs) var(--sp-md)">${escapeHtml(m.text)}</span>`;
}

/**
 * Build the signal health panel skeleton.
 * @param {HTMLElement} container  #panel-signal-health
 */
export function render(container) {
  container.innerHTML = `
    <div class="sh">
      <h2 class="sh-t">Signal Health</h2>
      <div class="sh-b" id="shQuality" aria-live="polite">-</div>
    </div>
    <div id="shStats" class="g4" role="group" aria-label="Signal-statistikk"></div>
    <div class="sh" style="margin-top:var(--sp-lg)">
      <h2 class="sh-t">Signaler (19-punkt ensemble)</h2>
    </div>
    <div class="card" id="shTable" role="region" aria-label="Signal-tabell" style="overflow-x:auto">
      <div class="loading" role="status"><div class="spinner" aria-hidden="true"></div>Laster signal health...</div>
    </div>
    <div id="shAlerts" role="region" aria-label="Signal-varsler" style="margin-top:var(--sp-lg)"></div>`;

  refreshAll();
}

/**
 * Fetch and render signal health data.
 */
export async function refreshAll() {
  try {
    const data = await fetchSignalHealth();
    cachedData = data;
    update(data);
  } catch (err) {
    const table = document.getElementById('shTable');
    if (table) {
      table.innerHTML = `<div class="error-card">Kunne ikke laste signal health: ${escapeHtml(String(err))}</div>`;
    }
  }
}

/**
 * Update the panel with data.
 * @param {Object} data  Signal health response
 */
export function update(data) {
  if (!data) return;

  // Quality badge
  const qualEl = document.getElementById('shQuality');
  if (qualEl) {
    qualEl.innerHTML = qualityBadge(data.ensemble_quality);
  }

  // Stats grid
  const statsEl = document.getElementById('shStats');
  if (statsEl) {
    const metrics = [
      { name: 'Aktive signaler', val: data.active_signals, col: 'bull' },
      { name: 'Ekskluderte', val: data.excluded_signals, col: 'bear' },
      { name: 'Totalt', val: data.total_signals, col: 'neutral' },
      { name: 'Snitt win rate', val: (data.mean_win_rate * 100).toFixed(1) + '%', col: data.mean_win_rate >= 0.55 ? 'bull' : 'bear' },
    ];
    statsEl.innerHTML = metrics
      .map((m) => `<div class="card card-stat"><div class="ct">${escapeHtml(m.name)}</div><div class="snum ${m.col} mono">${escapeHtml(String(m.val))}</div></div>`)
      .join('');
  }

  // Signal table
  const tableEl = document.getElementById('shTable');
  if (tableEl && data.signals) {
    const rows = data.signals
      .map((s) => {
        const wrCls = s.win_rate >= 0.58 ? 'bull' : s.win_rate >= 0.54 ? 'neutral' : 'bear';
        const pCls = s.p_value <= 0.01 ? 'bull' : s.p_value <= 0.05 ? 'neutral' : 'bear';
        return `<tr>
          <td class="mono">${escapeHtml(s.id)}</td>
          <td class="mono ${wrCls}">${(s.win_rate * 100).toFixed(1)}%</td>
          <td class="mono ${pCls}">${s.p_value.toFixed(4)}</td>
          <td class="mono">${s.weight.toFixed(2)}</td>
          <td>${statusBadge(s.status)}</td>
          <td>${s.is_decayed ? '<span class="warn-text">Ja</span>' : '<span class="bull">Nei</span>'}</td>
        </tr>`;
      })
      .join('');

    tableEl.innerHTML = `
      <table class="data-table" aria-label="Signal-detaljer">
        <thead>
          <tr>
            <th scope="col">Signal</th>
            <th scope="col">Win Rate</th>
            <th scope="col">p-verdi</th>
            <th scope="col">Vekt</th>
            <th scope="col">Status</th>
            <th scope="col">Forfalt</th>
          </tr>
        </thead>
        <tbody>${rows}</tbody>
      </table>`;
  }

  // Alerts
  const alertsEl = document.getElementById('shAlerts');
  if (alertsEl && data.alerts && data.alerts.length > 0) {
    alertsEl.innerHTML = `
      <div class="sh"><h2 class="sh-t">Varsler</h2></div>
      <div class="card" style="background:var(--wbg);border:1px solid var(--warn)">
        <ul style="margin:0;padding-left:var(--sp-lg);list-style:disc">
          ${data.alerts.map((a) => `<li style="margin-bottom:var(--sp-xs);color:var(--warn)">${escapeHtml(a)}</li>`).join('')}
        </ul>
      </div>`;
  } else if (alertsEl) {
    alertsEl.innerHTML = '';
  }
}
