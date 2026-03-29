/**
 * SignalLogPanel component — signal performance tracker.
 * Stats bar + table of last 100 signals with result badges.
 * Follows MacroPanel pattern: render() builds skeleton, update() fills data.
 */

import { escapeHtml, timeAgo, formatPrice } from '../utils.js';
import { fetchSignalLog } from '../api.js';
import { setState } from '../state.js';

/* ── Helpers ─────────────────────────────────────────────── */

const RESULT_STYLES = {
  hit:     { bg: 'var(--bull)', label: 'HIT' },
  miss:    { bg: 'var(--bear)', label: 'MISS' },
  pending: { bg: 'var(--warn)', label: 'PENDING' },
  neutral: { bg: 'var(--m)',    label: 'NEUTRAL' },
};

function resultBadge(result) {
  const r = RESULT_STYLES[(result || '').toLowerCase()] || RESULT_STYLES.neutral;
  return `<span style="display:inline-block;padding:2px 8px;border-radius:4px;font-size:10px;font-weight:600;background:${r.bg};color:#000">${escapeHtml(r.label)}</span>`;
}

function gradeBadge(grade) {
  const colors = { 'A+': 'var(--bull)', 'A': 'var(--bull)', 'B': 'var(--warn)', 'C': 'var(--m)', 'D': 'var(--bear)' };
  const bg = colors[grade] || 'var(--m)';
  return `<span class="tgrade" style="background:${bg};color:#000">${escapeHtml(grade || '-')}</span>`;
}

function dirBadge(dir) {
  const up = (dir || '').toLowerCase();
  if (up === 'long' || up === 'bull') return `<span style="color:var(--bull);font-weight:600">\u25B2 ${escapeHtml(dir)}</span>`;
  if (up === 'short' || up === 'bear') return `<span style="color:var(--bear);font-weight:600">\u25BC ${escapeHtml(dir)}</span>`;
  return `<span style="color:var(--m)">${escapeHtml(dir || '-')}</span>`;
}

function pctStr(n, total) {
  if (!total) return '0%';
  return ((n / total) * 100).toFixed(1) + '%';
}

/* ── Render ──────────────────────────────────────────────── */

/** @param {HTMLElement} container  #panel-signal-log */
export function render(container) {
  container.innerHTML = `
    <div class="sh"><h2 class="sh-t">Signal-logg</h2><div class="sh-b">Ytelse og historikk</div></div>
    <div class="g4" id="sl-stats" role="group" aria-label="Signalstatistikk"></div>
    <div class="card" style="margin-top:12px;overflow-x:auto" role="region" aria-label="Signaltabell">
      <table class="tt" id="sl-table" style="width:100%">
        <thead>
          <tr>
            <th>Tid</th>
            <th>Instrument</th>
            <th>Retning</th>
            <th>Grad</th>
            <th>Score</th>
            <th>Entry</th>
            <th>Resultat</th>
          </tr>
        </thead>
        <tbody id="sl-tbody">
          <tr><td colspan="7" style="text-align:center;color:var(--m)">Laster signaler...</td></tr>
        </tbody>
      </table>
    </div>`;
}

/** Update stats bar and signal table. */
export function update(data) {
  if (!data) return;
  updateStats(data);
  updateTable(data);
}

/** Fetch signal log and push to state. */
export async function refreshAll() {
  try {
    const data = await fetchSignalLog();
    setState('signalLog', data);
  } catch (e) {
    console.warn('[SignalLogPanel] fetch error:', e.message);
  }
}

/* ── Stats bar ───────────────────────────────────────────── */

function updateStats(data) {
  const el = document.getElementById('sl-stats');
  if (!el) return;

  const signals = data.signals || data || [];
  if (!Array.isArray(signals)) { el.innerHTML = ''; return; }

  const total = signals.length;
  const hits = signals.filter((s) => (s.result || '').toLowerCase() === 'hit').length;
  const hitRate = total > 0 ? ((hits / total) * 100).toFixed(1) : '0.0';

  // Per-grade breakdown
  const grades = {};
  signals.forEach((s) => {
    const g = s.grade || '?';
    if (!grades[g]) grades[g] = { total: 0, hits: 0 };
    grades[g].total++;
    if ((s.result || '').toLowerCase() === 'hit') grades[g].hits++;
  });

  const gradeCards = ['A+', 'A', 'B'].map((g) => {
    const d = grades[g] || { total: 0, hits: 0 };
    return `<div class="card">
      <div class="ct">${escapeHtml(g)}</div>
      <div class="snum" style="font-size:20px">${escapeHtml(pctStr(d.hits, d.total))}</div>
      <div style="font-size:11px;color:var(--m)">${escapeHtml(String(d.total))} signaler</div>
    </div>`;
  }).join('');

  el.innerHTML = `
    <div class="card">
      <div class="ct">Totalt</div>
      <div class="snum" style="font-size:20px">${escapeHtml(String(total))}</div>
      <div style="font-size:11px;color:var(--m)">signaler</div>
    </div>
    <div class="card">
      <div class="ct">Treffrate</div>
      <div class="snum" style="font-size:20px;color:var(--bull)">${escapeHtml(hitRate)}%</div>
      <div style="font-size:11px;color:var(--m)">${escapeHtml(String(hits))} treff</div>
    </div>
    ${gradeCards}`;
}

/* ── Signal table ────────────────────────────────────────── */

function updateTable(data) {
  const tbody = document.getElementById('sl-tbody');
  if (!tbody) return;

  const signals = data.signals || data || [];
  if (!Array.isArray(signals) || signals.length === 0) {
    tbody.innerHTML = '<tr><td colspan="7" style="text-align:center;color:var(--m)">Ingen signaler</td></tr>';
    return;
  }

  // Show last 100 signals
  const last100 = signals.slice(-100).reverse();

  tbody.innerHTML = last100.map((s) => `<tr>
    <td style="white-space:nowrap">${escapeHtml(s.time ? timeAgo(s.time) : '-')}</td>
    <td style="font-weight:600">${escapeHtml(s.instrument || '-')}</td>
    <td>${dirBadge(s.direction)}</td>
    <td>${gradeBadge(s.grade)}</td>
    <td style="font-family:'DM Mono',monospace">${escapeHtml(s.score != null ? String(s.score) : '-')}</td>
    <td style="font-family:'DM Mono',monospace">${escapeHtml(s.entry != null ? formatPrice(s.entry) : '-')}</td>
    <td>${resultBadge(s.result)}</td>
  </tr>`).join('');
}
