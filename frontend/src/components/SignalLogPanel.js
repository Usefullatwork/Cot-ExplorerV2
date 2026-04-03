/**
 * SignalLogPanel component — signal performance tracker.
 * Stats bar + table of last 100 signals with result badges.
 * Follows MacroPanel pattern: render() builds skeleton, update() fills data.
 */

import { escapeHtml, timeAgo, formatPrice, colorClass } from '../utils.js';
import { fetchSignalLog, fetchSignalAnalytics } from '../api.js';
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
    <div class="sh" style="margin-top:16px"><h2 class="sh-t">Analytikk</h2><div class="sh-b">Per instrument &amp; klasse</div></div>
    <div id="sl-analytics" class="sl-analytics-grid" role="region" aria-label="Signal-analytikk">
      <div class="loading" role="status"><div class="spinner" aria-hidden="true"></div>Laster analytikk...</div>
    </div>
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
            <th>R:R</th>
            <th>Resultat</th>
          </tr>
        </thead>
        <tbody id="sl-tbody">
          <tr><td colspan="8" style="text-align:center"><div class="loading" role="status"><div class="spinner" aria-hidden="true"></div>Laster signaler...</div></td></tr>
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
    const [data, analytics] = await Promise.all([
      fetchSignalLog(),
      fetchSignalAnalytics().catch(() => null),
    ]);
    setState('signalLog', data);
    renderAnalytics(analytics);
  } catch (e) {
    console.warn('[SignalLogPanel] fetch error:', e.message);
  }
}

function renderAnalytics(data) {
  const el = document.getElementById('sl-analytics');
  if (!el || !data) {
    if (el) el.innerHTML = '<div style="color:var(--m);font-size:12px">Ingen analytikk-data</div>';
    return;
  }

  // By instrument
  const instHtml = data.by_instrument && data.by_instrument.length
    ? '<div class="card"><div class="ct">Per instrument</div>' +
      data.by_instrument.map((r) =>
        `<div style="display:flex;justify-content:space-between;font-size:12px;margin-bottom:4px"><span>${escapeHtml(r.instrument)}</span><span>${r.trades}t &middot; <span class="${r.hit_rate >= 50 ? 'bull' : 'bear'}">${r.hit_rate.toFixed(0)}%</span> &middot; ${r.avg_pnl >= 0 ? '+' : ''}${r.avg_pnl.toFixed(1)}p</span></div>`
      ).join('') + '</div>'
    : '<div class="card"><div class="ct">Per instrument</div><div style="color:var(--m);font-size:12px">Ingen data</div></div>';

  // By grade
  const gradeHtml = data.by_grade && data.by_grade.length
    ? '<div class="card"><div class="ct">Per klasse</div>' +
      data.by_grade.map((g) =>
        `<div style="display:flex;justify-content:space-between;font-size:12px;margin-bottom:4px"><span style="font-weight:600">${escapeHtml(g.grade)}</span><span>${g.trades}t &middot; <span class="${g.hit_rate >= 50 ? 'bull' : 'bear'}">${g.hit_rate.toFixed(0)}%</span></span></div>`
      ).join('') + '</div>'
    : '<div class="card"><div class="ct">Per klasse</div><div style="color:var(--m);font-size:12px">Ingen data</div></div>';

  // Streaks
  const s = data.streak || {};
  const streakHtml = `<div class="card"><div class="ct">Rekker</div>
    <div style="font-size:12px;line-height:2">
      <div>Lengste gevinst: <span class="bull" style="font-weight:600">${s.longest_win || 0}</span></div>
      <div>Lengste tap: <span class="bear" style="font-weight:600">${s.longest_loss || 0}</span></div>
      <div>Nåværende: <span class="${s.current_type === 'win' ? 'bull' : s.current_type === 'loss' ? 'bear' : ''}" style="font-weight:600">${s.current_streak || 0} ${s.current_type === 'win' ? 'gevinster' : s.current_type === 'loss' ? 'tap' : ''}</span></div>
      <div>Totalt lukket: ${data.total_closed || 0} / ${data.total_signals || 0}</div>
    </div>
  </div>`;

  el.innerHTML = instHtml + gradeHtml + streakHtml;
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
    tbody.innerHTML = '<tr><td colspan="8"><div class="empty-state" style="padding:20px 12px"><div class="empty-state-icon">\uD83D\uDCCA</div><div class="empty-state-title">Ingen signaler logget</div><div class="empty-state-text">Signal-loggen oppdateres automatisk når nye handelssignaler genereres av analysemotoren.</div></div></td></tr>';
    return;
  }

  // Show last 100 signals
  const last100 = signals.slice(-100).reverse();

  tbody.innerHTML = last100.map((s) => {
    const mainRow = `<tr>
    <td style="white-space:nowrap">${escapeHtml(s.time ? timeAgo(s.time) : (s.created_at ? timeAgo(s.created_at) : '-'))}</td>
    <td style="font-weight:600">${escapeHtml(s.instrument || '-')}</td>
    <td>${dirBadge(s.direction)}</td>
    <td>${gradeBadge(s.grade)}</td>
    <td class="data-value">${escapeHtml(s.score != null ? String(s.score) : '-')}</td>
    <td class="data-value">${escapeHtml(s.entry != null ? formatPrice(s.entry) : (s.entry_price != null ? formatPrice(s.entry_price) : '-'))}</td>
    <td class="data-value" style="color:${s.risk_reward != null && s.risk_reward >= 1.5 ? 'var(--bull)' : 'var(--m)'}">${escapeHtml(s.risk_reward != null ? s.risk_reward.toFixed(1) + ':1' : '-')}</td>
    <td>${resultBadge(s.result)}</td>
  </tr>`;

    // Expandable reasoning row
    if (!s.reasoning) return mainRow;
    const r = s.reasoning;
    const met = (r.criteria_met || []).map((c) =>
      `<span style="color:var(--bull);font-size:11px;margin-right:8px">\u2714 ${escapeHtml(c.narrative)}</span>`
    ).join('');
    const missed = (r.criteria_missed || []).map((c) =>
      `<span style="color:var(--bear);font-size:11px;margin-right:8px">\u2718 ${escapeHtml(c.narrative)}</span>`
    ).join('');
    const reasoningRow = `<tr class="sl-reasoning-row"><td colspan="8" style="padding:4px 12px;background:var(--s2)">
      <details><summary style="cursor:pointer;font-size:11px;color:var(--m);font-weight:600">Reasoning: ${escapeHtml(r.confidence || '')} confidence</summary>
      <div style="margin-top:6px;font-size:12px;line-height:1.8">
        <div style="margin-bottom:4px;color:var(--f)">${escapeHtml(r.narrative || '')}</div>
        <div style="margin-bottom:4px"><strong style="color:var(--bull)">Strengths:</strong> ${met || '<span style="color:var(--m)">none</span>'}</div>
        <div><strong style="color:var(--bear)">Risks:</strong> ${missed || '<span style="color:var(--m)">none</span>'}</div>
      </div></details>
    </td></tr>`;
    return mainRow + reasoningRow;
  }).join('');
}
