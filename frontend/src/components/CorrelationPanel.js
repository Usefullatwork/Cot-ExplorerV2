/**
 * CorrelationPanel component — correlation matrix heatmap using CSS grid.
 * Follows MacroPanel pattern: render() builds skeleton, update() fills data.
 */

import { escapeHtml } from '../utils.js';
import { fetchCorrelations } from '../api.js';
import { setState } from '../state.js';

/* ── Helpers ─────────────────────────────────────────────── */

/**
 * Map correlation value (-1 to +1) to a background color.
 * Green for positive, red for negative, gray for diagonal.
 */
function corrColor(val, isDiag) {
  if (isDiag) return 'var(--s2)';
  if (val == null) return 'var(--s)';
  const abs = Math.min(Math.abs(val), 1);
  const alpha = (abs * 0.8 + 0.1).toFixed(2);
  if (val > 0) return `rgba(63,185,80,${alpha})`;
  if (val < 0) return `rgba(248,81,73,${alpha})`;
  return 'var(--s)';
}

function corrTextColor(val) {
  const abs = Math.abs(val || 0);
  return abs > 0.5 ? '#fff' : 'var(--t)';
}

/* ── Render ──────────────────────────────────────────────── */

/** @param {HTMLElement} container  #panel-correlations */
export function render(container) {
  container.innerHTML = `
    <div class="sh"><h2 class="sh-t">Korrelasjonsmatrise</h2><div class="sh-b">12 instrumenter, daglig korrelasjon</div></div>
    <div class="card" id="corr-matrix-wrap" role="region" aria-label="Korrelasjonsmatrise" style="overflow-x:auto">
      <div style="color:var(--m);font-size:13px">Laster korrelasjoner...</div>
    </div>`;
}

/** Update the matrix with fresh correlation data. */
export function update(data) {
  const wrap = document.getElementById('corr-matrix-wrap');
  if (!wrap || !data) return;

  const instruments = data.instruments || [];
  const matrix = data.matrix || [];

  if (instruments.length === 0) {
    wrap.innerHTML = '<div style="color:var(--m);font-size:13px">Ingen korrelasjonsdata</div>';
    return;
  }

  const n = instruments.length;

  let html = `<div class="corr-grid mono" style="display:grid;grid-template-columns:80px repeat(${n}, 1fr);gap:1px;font-size:11px;min-width:${n * 56 + 80}px">`;

  // Header row: empty corner + instrument labels
  html += '<div style="background:var(--bg)"></div>';
  for (let j = 0; j < n; j++) {
    html += `<div style="text-align:center;padding:6px 2px;background:var(--s);color:var(--t);font-weight:600;font-size:10px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis" title="${escapeHtml(instruments[j])}">${escapeHtml(instruments[j])}</div>`;
  }

  // Data rows
  for (let i = 0; i < n; i++) {
    // Row label
    html += `<div style="padding:6px 4px;background:var(--s);color:var(--t);font-weight:600;font-size:10px;display:flex;align-items:center;white-space:nowrap;overflow:hidden;text-overflow:ellipsis" title="${escapeHtml(instruments[i])}">${escapeHtml(instruments[i])}</div>`;

    const row = matrix[i] || [];
    for (let j = 0; j < n; j++) {
      const val = row[j] != null ? row[j] : (i === j ? 1 : null);
      const isDiag = i === j;
      const bg = corrColor(val, isDiag);
      const fg = isDiag ? 'var(--m)' : corrTextColor(val);
      const display = val != null ? val.toFixed(2) : '-';
      html += `<div style="text-align:center;padding:6px 2px;background:${bg};color:${fg};cursor:default" title="${escapeHtml(instruments[i])} / ${escapeHtml(instruments[j])}: ${escapeHtml(display)}">${escapeHtml(display)}</div>`;
    }
  }

  html += '</div>';

  // Legend
  html += `<div style="display:flex;gap:16px;margin-top:12px;font-size:11px;color:var(--m);align-items:center">
    <span>Sterk negativ</span>
    <div style="display:flex;gap:1px">
      <div style="width:20px;height:12px;background:rgba(248,81,73,0.9);border-radius:2px"></div>
      <div style="width:20px;height:12px;background:rgba(248,81,73,0.5);border-radius:2px"></div>
      <div style="width:20px;height:12px;background:var(--s2);border-radius:2px"></div>
      <div style="width:20px;height:12px;background:rgba(63,185,80,0.5);border-radius:2px"></div>
      <div style="width:20px;height:12px;background:rgba(63,185,80,0.9);border-radius:2px"></div>
    </div>
    <span>Sterk positiv</span>
  </div>`;

  wrap.innerHTML = html;
}

/** Fetch correlations and push to state. */
export async function refreshAll() {
  try {
    const data = await fetchCorrelations();
    setState('correlations', data);
  } catch (e) {
    console.warn('[CorrelationPanel] fetch error:', e.message);
  }
}
