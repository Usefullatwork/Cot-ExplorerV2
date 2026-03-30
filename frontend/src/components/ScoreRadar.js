/**
 * ScoreRadar component — Chart.js radar chart for 12-point confluence scoring.
 *
 * New component (not in v1). Subscribes to state.selectedInstrument.
 * Enhanced with hover tooltips showing score breakdown, click-to-detail modal,
 * color legend, and axis labels.
 */

import { createRadarChart } from '../charts/radarChart.js';
import { escapeHtml } from '../utils.js';

let chartInstance = null;
/** @type {Object|null} Cached instrument data for modal */
let _currentInstrument = null;

/**
 * Build the radar chart container with legend and detail modal.
 * @param {HTMLElement} container  A panel or sub-element to host the radar
 */
export function render(container) {
  container.innerHTML = `
    <div class="card" id="radarCard" style="display:none" role="region" aria-label="Konfluens-radar">
      <div style="display:flex;justify-content:space-between;align-items:center">
        <div class="ct" style="margin-bottom:0">Konfluens-radar</div>
        <button class="fc" id="radarDetailBtn" style="font-size:10px" aria-label="Vis konfluens-detaljer">Vis detaljer</button>
      </div>
      <div style="height:300px;position:relative;margin-top:12px" role="img" aria-label="Radardiagram for konfluensscore">
        <canvas id="radarCanvas" aria-hidden="true"></canvas>
      </div>
      <div id="radarLegend" style="display:flex;gap:16px;justify-content:center;margin-top:10px;font-size:11px" role="group" aria-label="Fargelegende"></div>
      <div id="radarSummary" style="font-size:12px;color:var(--m);margin-top:8px;text-align:center" aria-live="polite"></div>
      <div id="radarBreakdown" style="margin-top:12px" role="list" aria-label="Score-oppdeling"></div>
    </div>
    <div id="radarModal" role="dialog" aria-modal="true" aria-labelledby="radarModalTitle" aria-hidden="true" style="display:none;position:fixed;top:0;left:0;width:100%;height:100%;background:rgba(0,0,0,0.85);z-index:1000;align-items:center;justify-content:center">
      <div style="background:var(--s);border:1px solid var(--b);border-radius:12px;padding:20px;width:90%;max-width:600px;max-height:90vh;overflow-y:auto">
        <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:16px">
          <h3 style="font-size:16px;font-weight:700" id="radarModalTitle">Konfluens-detaljer</h3>
          <button class="fc" id="radarModalClose" style="font-size:14px;padding:4px 10px" aria-label="Lukk detaljer">
            <span aria-hidden="true">X</span>
          </button>
        </div>
        <div id="radarModalBody"></div>
      </div>
    </div>`;

  // Detail button -> open modal
  const detailBtn = container.querySelector('#radarDetailBtn');
  if (detailBtn) {
    detailBtn.addEventListener('click', () => { openRadarModal(); });
  }

  // Modal close
  const modal = document.getElementById('radarModal');
  if (modal) {
    modal.addEventListener('click', (e) => {
      if (e.target === modal || e.target.id === 'radarModalClose' || e.target.closest('#radarModalClose')) {
        modal.style.display = 'none';
        modal.setAttribute('aria-hidden', 'true');
      }
    });
    // Escape key to close
    document.addEventListener('keydown', (e) => {
      if (e.key === 'Escape' && modal.style.display === 'flex') {
        modal.style.display = 'none';
        modal.setAttribute('aria-hidden', 'true');
      }
    });
  }
}

/**
 * Open the radar detail modal showing full score breakdown.
 */
function openRadarModal() {
  const modal = document.getElementById('radarModal');
  const body = document.getElementById('radarModalBody');
  const title = document.getElementById('radarModalTitle');
  if (!modal || !body || !_currentInstrument) return;

  const inst = _currentInstrument;
  const details = inst.score_details || [];
  const passing = details.filter((d) => d.verdi).length;

  title.textContent = `${inst.name || inst.instrument || 'Instrument'} — Konfluens ${passing}/${details.length}`;

  const rows = details.map((d) => {
    const pass = d.verdi;
    const icon = pass ? '\u2705' : '\u274C';
    const cls = pass ? 'bull' : 'bear';
    const desc = escapeHtml(d.beskrivelse || d.description || d.kryss || '');
    return `<div style="display:flex;align-items:center;gap:10px;padding:8px 0;border-bottom:1px solid var(--b)">
      <span style="font-size:16px;flex-shrink:0">${icon}</span>
      <div style="flex:1">
        <div style="font-size:13px;font-weight:500;color:var(--${cls})">${escapeHtml(d.kryss || d.label || 'Kriterium')}</div>
        <div style="font-size:11px;color:var(--m);margin-top:2px">${desc}</div>
      </div>
      <span style="font-family:'DM Mono',monospace;font-size:12px;color:var(--${cls});flex-shrink:0">${pass ? 'PASS' : 'FAIL'}</span>
    </div>`;
  }).join('');

  const scorePct = inst.score_pct || 0;
  const scoreColor = scorePct >= 70 ? 'var(--bull)' : scorePct >= 40 ? 'var(--warn)' : 'var(--bear)';

  body.innerHTML = `
    <div style="text-align:center;margin-bottom:16px">
      <div style="font-family:'DM Mono',monospace;font-size:36px;font-weight:700;color:${scoreColor}">${scorePct}%</div>
      <div style="font-size:12px;color:var(--m);margin-top:4px">${passing} av ${details.length} kriterier oppfylt</div>
      <div class="score-bar-wrap" style="margin-top:10px"><div class="score-bar"><div class="score-fill" style="width:${scorePct}%;background:${scoreColor}"></div></div></div>
    </div>
    ${rows}`;

  modal.style.display = 'flex';
  modal.setAttribute('aria-hidden', 'false');
  const closeBtn = document.getElementById('radarModalClose');
  if (closeBtn) closeBtn.focus();
}

/**
 * Update the radar chart for a selected instrument.
 * @param {Object|null} instrument  Signal data with score_details array
 */
export function update(instrument) {
  const card = document.getElementById('radarCard');
  if (!card) return;

  if (!instrument || !instrument.score_details || !instrument.score_details.length) {
    card.style.display = 'none';
    _currentInstrument = null;
    return;
  }

  card.style.display = 'block';
  _currentInstrument = instrument;

  const details = instrument.score_details;
  const labels = details.map((d) => d.kryss || d.label || 'Kriterium');
  const values = details.map((d) => (d.verdi ? 1 : 0));
  const passing = values.filter((v) => v).length;

  // Destroy previous chart
  if (chartInstance) {
    chartInstance.destroy();
    chartInstance = null;
  }

  const canvas = document.getElementById('radarCanvas');
  if (canvas) {
    chartInstance = createRadarChart(canvas, labels, values);
  }

  // Color legend
  const legendEl = document.getElementById('radarLegend');
  if (legendEl) {
    legendEl.innerHTML = `
      <div style="display:flex;align-items:center;gap:4px"><div style="width:10px;height:10px;border-radius:50%;background:var(--bull)"></div><span style="color:var(--m)">Oppfylt</span></div>
      <div style="display:flex;align-items:center;gap:4px"><div style="width:10px;height:10px;border-radius:50%;background:var(--b2)"></div><span style="color:var(--m)">Ikke oppfylt</span></div>`;
  }

  // Summary
  const summaryEl = document.getElementById('radarSummary');
  if (summaryEl) {
    const pct = instrument.score_pct || 0;
    const col = pct >= 70 ? 'bull' : pct >= 40 ? 'warn' : 'bear';
    summaryEl.innerHTML = `<span class="${col}" style="font-weight:600">${passing}/${details.length}</span> kriterier oppfylt <span class="${col}" style="font-weight:600">(${pct}%)</span>`;
  }

  // Inline breakdown grid
  const breakdownEl = document.getElementById('radarBreakdown');
  if (breakdownEl) {
    breakdownEl.innerHTML = `<div class="score-items">${details.map((d) => {
      const pass = d.verdi;
      return `<div class="score-item" title="${escapeHtml(d.beskrivelse || d.description || d.kryss || '')}"><div class="score-dot" style="background:${pass ? 'var(--bull)' : 'var(--b2)'}"></div><span style="color:${pass ? 'var(--bull)' : 'var(--m)'}">${escapeHtml(d.kryss || d.label || '')}</span></div>`;
    }).join('')}</div>`;
  }
}
