/**
 * PipelinePanel component — pipeline monitoring dashboard.
 *
 * Shows Layer 1/2 status, recent pipeline runs, gate log for recent signals,
 * and a manual "Force Layer 2" trigger button.
 */

import { escapeHtml, timeAgo } from '../utils.js';
import {
  fetchPipelineStatus,
  fetchPipelineRuns,
  fetchBotSignals,
  fetchGateLog,
  forceLayer2,
} from '../api.js';

/* ── Helpers ─────────────────────────────────────────────── */

function statusBadge(status) {
  const colors = { ok: 'bull', running: 'warn', error: 'bear', completed: 'bull', failed: 'bear' };
  const col = colors[status] || 'warn';
  return `<span class="tgrade ${col}" style="font-size:10px">${escapeHtml((status || 'unknown').toUpperCase())}</span>`;
}

function durationStr(sec) {
  if (sec == null) return '-';
  if (sec < 60) return sec.toFixed(1) + 's';
  return (sec / 60).toFixed(1) + 'm';
}

/* ── Render ──────────────────────────────────────────────── */

/** @param {HTMLElement} container  #panel-pipeline */
export function render(container) {
  container.innerHTML = `
    <div class="sh"><h2 class="sh-t">Pipeline Monitor</h2><div class="sh-b" id="plUpdated" aria-live="polite">-</div></div>
    <div class="g4" id="plStatus" role="group" aria-label="Pipeline-status" style="margin-bottom:var(--sp-lg)"></div>
    <div style="margin-bottom:var(--sp-lg)">
      <button id="plForceBtn" class="fc" style="background:var(--blbg);border-color:var(--blue);color:var(--blue);padding:8px 20px;font-size:12px;font-weight:600;cursor:pointer">Force Layer 2</button>
      <span id="plForceMsg" style="font-size:11px;color:var(--m);margin-left:8px" aria-live="polite"></span>
    </div>
    <div class="g22" style="margin-bottom:var(--sp-lg)">
      <div>
        <div class="sh"><h2 class="sh-t">Siste kjøringer</h2><div class="sh-b">Pipeline runs</div></div>
        <div class="cotw" style="overflow-x:auto">
          <table class="cott" aria-label="Pipeline-kjøringer">
            <thead><tr><th>Startet</th><th>Layer</th><th>Status</th><th style="text-align:right">Varighet</th><th style="text-align:right">Signaler</th></tr></thead>
            <tbody id="plRunsBody"><tr><td colspan="5" style="color:var(--m);text-align:center">Laster...</td></tr></tbody>
          </table>
        </div>
      </div>
      <div>
        <div class="sh"><h2 class="sh-t">Gate-logg</h2><div class="sh-b">Siste signaler gjennom gates</div></div>
        <div id="plGateLog" role="region" aria-label="Gate-logg">
          <div class="loading" role="status"><div class="spinner" aria-hidden="true"></div>Laster gate-logg...</div>
        </div>
      </div>
    </div>`;

  wireForceButton();
  refreshAll();
}

/* ── Force Layer 2 button ────────────────────────────────── */

function wireForceButton() {
  const btn = document.getElementById('plForceBtn');
  if (!btn) return;
  btn.addEventListener('click', async () => {
    const msg = document.getElementById('plForceMsg');
    btn.disabled = true;
    btn.textContent = 'Kjører...';
    try {
      const result = await forceLayer2();
      if (msg) {
        msg.style.color = 'var(--bull)';
        msg.textContent = `OK — regime: ${result.layer2?.regime || '?'}, ${result.signals_processed} signaler, ${result.signals_passed} passerte`;
      }
      await refreshAll();
    } catch (err) {
      if (msg) {
        msg.style.color = 'var(--bear)';
        msg.textContent = 'Feil: ' + (err.message || 'Ukjent');
      }
    } finally {
      btn.disabled = false;
      btn.textContent = 'Force Layer 2';
    }
  });
}

/* ── Update functions ────────────────────────────────────── */

function updateStatus(data) {
  const el = document.getElementById('plStatus');
  if (!el) return;

  if (data.is_placeholder) {
    el.innerHTML = `<div class="card" style="grid-column:1/-1"><div class="ct">Status</div><div style="font-size:13px;color:var(--warn)">Ingen Layer 2-kjøring ennå. Trykk "Force Layer 2" for å starte.</div></div>`;
    return;
  }

  const metrics = [
    { name: 'Regime', val: data.regime || '-', col: data.regime === 'NORMAL' ? 'bull' : data.regime === 'CRISIS' ? 'bear' : 'warn' },
    { name: 'VaR 95%', val: data.var_95_pct != null ? (data.var_95_pct * 100).toFixed(2) + '%' : '-', col: data.var_95_pct > 0.02 ? 'bear' : 'bull' },
    { name: 'Stress OK', val: data.stress_survives ? 'Ja' : 'Nei', col: data.stress_survives ? 'bull' : 'bear' },
    { name: 'Ensemble', val: data.ensemble_quality || '-', col: data.ensemble_quality === 'healthy' ? 'bull' : 'warn' },
    { name: 'VIX', val: data.vix_price != null ? data.vix_price.toFixed(1) : '-', col: (data.vix_price || 0) > 25 ? 'bear' : (data.vix_price || 0) > 18 ? 'warn' : 'bull' },
    { name: 'Korr. maks', val: data.correlation_max != null ? data.correlation_max.toFixed(2) : '-', col: (data.correlation_max || 0) > 0.8 ? 'bear' : 'bull' },
    { name: 'Drift', val: data.drift_detected ? 'Ja' : 'Nei', col: data.drift_detected ? 'bear' : 'bull' },
    { name: 'Posisjoner', val: data.open_position_count ?? '-', col: 'neutral' },
  ];

  el.innerHTML = metrics
    .map((m) => `<div class="card card-stat"><div class="ct">${escapeHtml(m.name)}</div><div class="snum ${m.col} mono">${escapeHtml(String(m.val))}</div></div>`)
    .join('');

  const ts = document.getElementById('plUpdated');
  if (ts) {
    const l1 = data.layer1_last_run_at ? timeAgo(data.layer1_last_run_at) : '-';
    const l2 = data.layer2_last_run_at ? timeAgo(data.layer2_last_run_at) : '-';
    ts.textContent = `L1: ${l1} | L2: ${l2}`;
  }
}

function updateRuns(data) {
  const body = document.getElementById('plRunsBody');
  if (!body) return;

  const runs = data.runs || [];
  if (!runs.length) {
    body.innerHTML = '<tr><td colspan="5"><div class="empty-state" style="padding:16px"><div class="empty-state-title">Ingen kjøringer</div></div></td></tr>';
    return;
  }

  body.innerHTML = runs.map((r) => {
    const layerCol = r.layer === 'layer2' ? 'blue' : r.layer === 'retrain' ? 'warn' : 'bull';
    return `<tr>
      <td style="font-size:11px;white-space:nowrap">${r.started_at ? escapeHtml(timeAgo(r.started_at)) : '-'}</td>
      <td><span style="color:var(--${layerCol});font-weight:600;font-size:11px;text-transform:uppercase">${escapeHtml(r.layer || '-')}</span></td>
      <td>${statusBadge(r.status)}</td>
      <td class="tdr mono" style="font-size:11px">${durationStr(r.duration_sec)}</td>
      <td class="tdr mono" style="font-size:11px">${r.signals_processed ?? '-'}</td>
    </tr>`;
  }).join('');
}

async function updateGateLog() {
  const el = document.getElementById('plGateLog');
  if (!el) return;

  try {
    const signals = await fetchBotSignals();
    const arr = Array.isArray(signals) ? signals : [];
    const recent = arr.slice(0, 10);

    if (!recent.length) {
      el.innerHTML = '<div class="empty-state" style="padding:16px"><div class="empty-state-title">Ingen signaler</div><div class="empty-state-text">Gate-loggen viser resultater fra de siste signalene.</div></div>';
      return;
    }

    const cards = recent.map((s) => {
      const dirCol = (s.direction || '').toUpperCase() === 'LONG' ? 'bull' : 'bear';
      const gates = s.gate_log_parsed || [];
      const passCount = gates.filter((g) => g.passed).length;
      const totalGates = gates.length;

      const gateSteps = gates.map((g) => {
        const icon = g.passed ? '\u2714' : '\u2718';
        const color = g.passed ? 'var(--bull)' : 'var(--bear)';
        const name = g.gate_name || g.name || '?';
        const detail = g.detail || '';
        return `<div style="display:flex;align-items:flex-start;gap:6px;margin-bottom:3px">
          <span style="color:${color};flex-shrink:0;font-size:12px">${icon}</span>
          <div><span style="font-size:11px;font-weight:600">${escapeHtml(name)}</span>
          ${detail ? `<div style="font-size:10px;color:var(--m)">${escapeHtml(detail)}</div>` : ''}</div>
        </div>`;
      }).join('');

      return `<div class="card" style="margin-bottom:8px;padding:var(--sp-sm) var(--sp-md)">
        <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:6px">
          <span style="font-weight:600;font-size:12px">${escapeHtml(s.instrument || '-')} <span class="tbias ${dirCol}" style="font-size:10px">${escapeHtml(s.direction || '-')}</span></span>
          <span style="font-size:11px;color:var(--${passCount === totalGates ? 'bull' : 'warn'})">${passCount}/${totalGates} gates</span>
        </div>
        ${totalGates > 0 ? `<details><summary style="cursor:pointer;font-size:11px;color:var(--m)">Gate-detaljer</summary><div style="margin-top:4px">${gateSteps}</div></details>` : '<div style="font-size:11px;color:var(--m)">Ingen gate-data</div>'}
      </div>`;
    }).join('');

    el.innerHTML = cards;
  } catch (err) {
    el.innerHTML = `<div style="color:var(--bear);font-size:12px">Feil: ${escapeHtml(err.message)}</div>`;
  }
}

/* ── Data refresh ────────────────────────────────────────── */

export async function refreshAll() {
  const [statusResult, runsResult] = await Promise.allSettled([
    fetchPipelineStatus(),
    fetchPipelineRuns(null, 20),
  ]);

  if (statusResult.status === 'fulfilled') updateStatus(statusResult.value);
  if (runsResult.status === 'fulfilled') updateRuns(runsResult.value);

  await updateGateLog();
}
