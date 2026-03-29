/**
 * MetalsIntelPanel component — COMEX warehouse, seismic events, intel feed.
 * Follows MacroPanel pattern: render() builds skeleton, update() fills data.
 */

import { escapeHtml, formatNumber, timeAgo } from '../utils.js';
import { fetchGeoIntel } from '../api.js';
import { setState, subscribe } from '../state.js';

/* ── Regime awareness ─────────────────────────────────────── */

const MI_REGIME_COLORS = {
  NORMAL:       'var(--bull)',
  RISK_OFF:     'var(--warn)',
  CRISIS:       '#e8730e',
  WAR_FOOTING:  'var(--bear)',
  ENERGY_SHOCK: '#e8730e',
  SANCTIONS:    '#a371f7',
};

function renderRegimeBadge(regime) {
  const el = document.getElementById('mi-regime-badge');
  if (!el) return;
  if (!regime) { el.innerHTML = ''; return; }
  const color = MI_REGIME_COLORS[regime.name] || 'var(--m)';
  const isCrisis = regime.name === 'CRISIS' || regime.name === 'WAR_FOOTING';
  el.innerHTML = `<div style="display:inline-flex;align-items:center;gap:8px;padding:6px 12px;border-radius:6px;background:${color}22;border:1px solid ${color};margin-bottom:12px">
    <span style="font-size:11px;font-weight:600;color:${color}">${escapeHtml(regime.name || 'UNKNOWN')}</span>
    ${isCrisis ? '<span style="font-size:11px;color:var(--bear)">\uD83D\uDD34 Krisemodus aktiv \u2014 kun trygge havner</span>' : ''}
  </div>`;
}

/* ── Helpers ─────────────────────────────────────────────── */

function stressColor(v) {
  if (v >= 75) return 'var(--bear)';
  if (v >= 50) return 'var(--warn)';
  if (v >= 25) return '#d29922';
  return 'var(--bull)';
}

function magColor(m) {
  if (m >= 7) return 'var(--bear)';
  if (m >= 6) return 'var(--warn)';
  if (m >= 5) return '#d2d922';
  return 'var(--m)';
}

function catBadge(cat) {
  const map = {
    gold: '#FFD700', silver: '#C0C0C0', copper: '#B87333', geopolitics: 'var(--bear)',
  };
  const bg = map[(cat || '').toLowerCase()] || 'var(--m)';
  const fg = cat === 'silver' ? 'var(--bg)' : '#000';
  return `<span style="display:inline-block;padding:2px 8px;border-radius:4px;font-size:10px;font-weight:600;background:${bg};color:${fg}">${escapeHtml(cat || 'Ukjent')}</span>`;
}

/* ── Active filter state ─────────────────────────────────── */
let activeFilter = 'all';

/* ── Render ──────────────────────────────────────────────── */

/** @param {HTMLElement} container  #panel-metals-intel */
export function render(container) {
  container.innerHTML = `
    <div id="mi-regime-badge"></div>
    <div class="sh"><h2 class="sh-t">COMEX Lager</h2><div class="sh-b">Gull, Solv, Kobber</div></div>
    <div class="g3" id="mi-comex" role="group" aria-label="COMEX lager"></div>

    <div class="sh" style="margin-top:18px"><h2 class="sh-t">Seismiske hendelser</h2><div class="sh-b">Jordskjelv naer gruveregioner</div></div>
    <div class="card" id="mi-seismic" role="region" aria-label="Seismiske hendelser" style="max-height:360px;overflow-y:auto"></div>

    <div class="sh" style="margin-top:18px"><h2 class="sh-t">Intel-feed</h2><div class="sh-b">Nyheter og analyse</div></div>
    <div class="card" id="mi-intel" role="region" aria-label="Intel-feed">
      <div id="mi-intel-filters" style="display:flex;gap:6px;margin-bottom:12px;flex-wrap:wrap"></div>
      <div id="mi-intel-list" style="max-height:420px;overflow-y:auto"></div>
    </div>`;

  // Subscribe to regime updates for the badge
  subscribe('regime', (regime) => renderRegimeBadge(regime));
}

/** Update all three sections with fresh geointel data. */
export function update(data) {
  if (!data) return;
  updateComex(data.comex);
  updateSeismic(data.seismic);
  updateIntel(data.intel);
}

/** Fetch geointel and push to state. */
export async function refreshAll() {
  try {
    const data = await fetchGeoIntel();
    setState('geointel', data);
  } catch (e) {
    console.warn('[MetalsIntelPanel] fetch error:', e.message);
  }
}

/* ── COMEX ───────────────────────────────────────────────── */

function updateComex(comex) {
  const el = document.getElementById('mi-comex');
  if (!el || !comex) { if (el) el.innerHTML = '<div class="card" style="color:var(--m)">Ingen COMEX-data</div>'; return; }

  const metals = [
    { key: 'gold', label: 'Gull', color: '#FFD700' },
    { key: 'silver', label: 'Solv', color: '#C0C0C0' },
    { key: 'copper', label: 'Kobber', color: '#B87333' },
  ];

  el.innerHTML = metals.map((m) => {
    const d = comex[m.key] || {};
    const total = d.total || 0;
    const reg = d.registered || 0;
    const elig = d.eligible || 0;
    const chg = d.daily_change || 0;
    const stress = d.stress || 0;
    const regPct = total > 0 ? (reg / total * 100).toFixed(1) : 0;
    const eligPct = total > 0 ? (elig / total * 100).toFixed(1) : 0;
    return `<div class="card" style="border-top:3px solid ${m.color}">
      <div class="ct" style="color:${m.color}">${escapeHtml(m.label)}</div>
      <div class="snum" style="font-size:18px">${escapeHtml(formatNumber(total))} oz</div>
      <div style="margin:10px 0">
        <div style="display:flex;height:8px;border-radius:4px;overflow:hidden;background:var(--s2)">
          <div style="width:${regPct}%;background:${m.color};opacity:0.9" title="Registrert"></div>
          <div style="width:${eligPct}%;background:${m.color};opacity:0.4" title="Kvalifisert"></div>
        </div>
        <div style="display:flex;justify-content:space-between;font-size:10px;color:var(--m);margin-top:4px">
          <span>Reg: ${escapeHtml(regPct)}%</span><span>Elig: ${escapeHtml(eligPct)}%</span>
        </div>
      </div>
      <div style="font-size:12px;color:var(--${chg >= 0 ? 'bull' : 'bear'})">Daglig: ${chg >= 0 ? '+' : ''}${escapeHtml(formatNumber(chg))}</div>
      <div style="margin-top:10px">
        <div style="font-size:10px;color:var(--m);margin-bottom:4px">Stress: ${escapeHtml(String(stress))}/100</div>
        <div style="height:6px;border-radius:3px;background:var(--s2)">
          <div style="width:${Math.min(100, stress)}%;height:100%;border-radius:3px;background:${stressColor(stress)}"></div>
        </div>
      </div>
    </div>`;
  }).join('');
}

/* ── Seismic ─────────────────────────────────────────────── */

function updateSeismic(seismic) {
  const el = document.getElementById('mi-seismic');
  if (!el) return;
  const events = (seismic?.events || seismic || []);
  if (!Array.isArray(events) || events.length === 0) {
    el.innerHTML = '<div style="color:var(--m);font-size:13px;padding:8px">Ingen seismiske hendelser</div>';
    return;
  }
  const sorted = [...events].sort((a, b) => (b.magnitude || 0) - (a.magnitude || 0));
  el.innerHTML = sorted.map((ev) => {
    const mag = ev.magnitude || 0;
    return `<div style="display:flex;align-items:center;gap:12px;padding:8px 0;border-bottom:1px solid var(--b)">
      <div style="min-width:44px;text-align:center;font-family:'DM Mono',monospace;font-size:18px;font-weight:600;color:${magColor(mag)}">${escapeHtml(mag.toFixed(1))}</div>
      <div style="flex:1;font-size:13px">
        <div style="color:var(--t)">${escapeHtml(ev.place || 'Ukjent sted')}</div>
        <div style="color:var(--m);font-size:11px">${escapeHtml(ev.region || '')} &middot; ${escapeHtml(ev.time ? timeAgo(ev.time) : '')}</div>
      </div>
    </div>`;
  }).join('');
}

/* ── Intel feed ──────────────────────────────────────────── */

function updateIntel(intel) {
  const filtersEl = document.getElementById('mi-intel-filters');
  const listEl = document.getElementById('mi-intel-list');
  if (!filtersEl || !listEl) return;

  const articles = (intel?.articles || intel || []);
  if (!Array.isArray(articles) || articles.length === 0) {
    filtersEl.innerHTML = '';
    listEl.innerHTML = '<div style="color:var(--m);font-size:13px">Ingen artikler</div>';
    return;
  }

  const cats = ['All', 'Gold', 'Silver', 'Copper', 'Geopolitics'];
  filtersEl.innerHTML = cats.map((c) => {
    const active = activeFilter === c.toLowerCase();
    return `<button class="fc mi-filter-btn${active ? ' mi-filter-active' : ''}" data-cat="${c.toLowerCase()}" style="font-size:11px;${active ? 'background:var(--blue);color:#fff' : ''}">${escapeHtml(c)}</button>`;
  }).join('');

  filtersEl.querySelectorAll('.mi-filter-btn').forEach((btn) => {
    btn.addEventListener('click', () => {
      activeFilter = btn.dataset.cat;
      updateIntel(intel);
    });
  });

  const filtered = activeFilter === 'all'
    ? articles
    : articles.filter((a) => (a.category || '').toLowerCase() === activeFilter);

  listEl.innerHTML = filtered.map((a) => {
    const href = a.url ? ` href="${escapeHtml(a.url)}" target="_blank" rel="noopener noreferrer"` : '';
    return `<div style="padding:8px 0;border-bottom:1px solid var(--b)">
      <div style="display:flex;align-items:center;gap:8px;margin-bottom:4px">
        ${catBadge(a.category)}
        <span style="font-size:10px;color:var(--m)">${escapeHtml(a.source || '')}</span>
        <span style="font-size:10px;color:var(--m)">${escapeHtml(a.time ? timeAgo(a.time) : '')}</span>
      </div>
      <a${href} style="color:var(--blue);font-size:13px;text-decoration:none">${escapeHtml(a.title || 'Uten tittel')}</a>
    </div>`;
  }).join('');
}
