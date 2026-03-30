/** GeoEventsPanel — geopolitical pre-trading system. */
import { escapeHtml, timeAgo } from '../utils.js';
import { fetchGeoSignals, fetchGeoEvents, fetchRegime, fetchEnergyInfra, fetchMineLocations } from '../api.js';
import { setState } from '../state.js';
import * as GeoMapPanel from './GeoMapPanel.js';

const REGIME_COLORS = {
  NORMAL:       { bg: 'var(--bull)',  label: 'NORMAL',        icon: '\u2705' },
  RISK_OFF:     { bg: 'var(--warn)',  label: 'RISK-OFF',      icon: '\u26A0\uFE0F' },
  CRISIS:       { bg: '#e8730e',      label: 'KRISE',         icon: '\uD83D\uDD34' },
  WAR_FOOTING:  { bg: 'var(--bear)',  label: 'KRIGSFOOTING',  icon: '\uD83D\uDD34' },
  ENERGY_SHOCK: { bg: '#e8730e',      label: 'ENERGISJOKK',   icon: '\u26A1' },
  SANCTIONS:    { bg: '#a371f7',      label: 'SANKSJONER',    icon: '\uD83D\uDFE3' },
};

const EVENT_TYPE_COLORS = {
  conflict:     'var(--bear)',
  sanctions:    '#a371f7',
  supply:       '#e8730e',
  maritime:     'var(--blue)',
  disaster:     '#8b6914',
  political:    '#b62324',
  'trade-war':  'var(--warn)',
  energy:       '#e8730e',
};

let activeEventFilter = 'all';

/** @param {HTMLElement} container */
export function render(container) {
  container.innerHTML = `
    <div id="geo-regime-banner" role="status" aria-label="Markedsregime"></div>
    <div class="sh" style="margin-top:18px"><h2 class="sh-t">Aktive Geo-Signaler</h2><div class="sh-b">Handelsignaler fra geopolitiske hendelser</div></div>
    <div id="geo-signals" role="region" aria-label="Geo-signaler" style="display:grid;gap:12px"></div>
    <div class="sh" style="margin-top:18px"><h2 class="sh-t">Hendelsestidslinje</h2><div class="sh-b">Klassifiserte hendelser siste 7 dager</div></div>
    <div class="card" id="geo-timeline" role="region" aria-label="Tidslinje">
      <div id="geo-timeline-filters" style="display:flex;gap:6px;margin-bottom:12px;flex-wrap:wrap"></div>
      <div id="geo-timeline-list" style="max-height:420px;overflow-y:auto"></div>
    </div>
    <div class="sh" style="margin-top:18px"><h2 class="sh-t">Geopolitisk kart</h2><div class="sh-b">Gruver, rørledninger, chokepoints og energi-infrastruktur</div></div>
    <div class="card" id="geo-map-container" style="height:500px;padding:0"></div>
    <div class="sh" style="margin-top:18px"><h2 class="sh-t">Impact-kart</h2><div class="sh-b">Instrumenter påvirket av aktive hendelser</div></div>
    <div class="card" id="geo-impact-map" role="region" aria-label="Impact-kart" style="overflow-x:auto"></div>`;
}

/** Update all sections. */
export function update({ regime, geoSignals, geoEvents } = {}) {
  updateRegime(regime);
  updateSignals(geoSignals);
  updateTimeline(geoEvents);
  updateImpactMap(geoSignals);
}

/** Fetch all geo data and push to state. */
export async function refreshAll() {
  const results = await Promise.allSettled([
    fetchRegime(), fetchGeoSignals(), fetchGeoEvents(),
  ]);
  if (results[0].status === 'fulfilled') setState('regime', results[0].value);
  if (results[1].status === 'fulfilled') setState('geoSignals', results[1].value);
  if (results[2].status === 'fulfilled') setState('geoEvents', results[2].value);
  const failed = results.filter((r) => r.status === 'rejected');
  if (failed.length) console.warn('[GeoEventsPanel] partial fetch errors:', failed.length);

  // Fetch map data and render Leaflet map
  const mapResults = await Promise.allSettled([
    fetchEnergyInfra(), fetchMineLocations(),
  ]);
  const mapContainer = document.getElementById('geo-map-container');
  if (mapContainer) {
    GeoMapPanel.render(mapContainer);
    const mapData = {};
    if (mapResults[0].status === 'fulfilled') {
      const ei = mapResults[0].value;
      mapData.pipelines = ei.pipelines;
      mapData.lngTerminals = ei.lng_terminals;
      mapData.shippingLanes = ei.shipping_lanes;
    }
    if (mapResults[1].status === 'fulfilled') {
      mapData.mines = mapResults[1].value.mines;
    }
    GeoMapPanel.update(mapData);
  }
}

function updateRegime(regime) {
  const el = document.getElementById('geo-regime-banner');
  if (!el) return;
  if (!regime) { el.innerHTML = '<div class="card" style="color:var(--m)">Ingen regime-data</div>'; return; }
  const r = REGIME_COLORS[regime.name] || REGIME_COLORS.NORMAL;
  el.innerHTML = `<div class="card" style="border-left:4px solid ${r.bg};padding:14px 18px">
    <div style="font-size:16px;font-weight:700;color:${r.bg}">${r.icon} ${escapeHtml(r.label)} REGIME</div>
    <div style="font-size:13px;color:var(--t);margin-top:4px">${escapeHtml(regime.description || '')}</div>
    ${regime.adjustments ? `<div style="font-size:11px;color:var(--m);margin-top:6px">${escapeHtml(regime.adjustments)}</div>` : ''}
  </div>`;
}

function typeBadge(type) {
  const bg = EVENT_TYPE_COLORS[type] || 'var(--m)';
  return `<span style="display:inline-block;padding:2px 8px;border-radius:4px;font-size:10px;font-weight:600;background:${bg};color:#fff">${escapeHtml(type || 'ukjent')}</span>`;
}

function confidenceBar(pct) {
  const p = Math.min(100, Math.max(0, pct || 0));
  const color = p >= 75 ? 'var(--bull)' : p >= 50 ? 'var(--warn)' : 'var(--bear)';
  return `<div style="height:6px;border-radius:3px;background:var(--s2);margin-top:6px">
    <div style="width:${p}%;height:100%;border-radius:3px;background:${color}"></div>
  </div><div style="font-size:10px;color:var(--m);margin-top:2px">${escapeHtml(String(p))}% konfidens</div>`;
}

function strengthDots(strength) {
  const map = { strong: 3, moderate: 2, weak: 1 };
  const n = map[(strength || '').toLowerCase()] || 1;
  return '<span style="color:var(--warn)">' + '\u25CF'.repeat(n) + '<span style="color:var(--b2)">' + '\u25CF'.repeat(3 - n) + '</span></span>';
}

function updateSignals(signals) {
  const el = document.getElementById('geo-signals');
  if (!el) return;
  if (!Array.isArray(signals) || signals.length === 0) {
    el.innerHTML = '<div class="card" style="color:var(--m)">Ingen aktive geo-signaler</div>';
    return;
  }
  const sorted = [...signals].sort((a, b) => (b.confidence || 0) - (a.confidence || 0));
  el.innerHTML = sorted.map((s) => {
    const instruments = (s.instruments || []).map((i) => {
      const arrow = i.direction === 'bull' ? '\u2191' : i.direction === 'bear' ? '\u2193' : '\u2014';
      const color = i.direction === 'bull' ? 'var(--bull)' : i.direction === 'bear' ? 'var(--bear)' : 'var(--m)';
      return `<span class="mono" style="color:${color};font-size:12px;margin-right:8px">${escapeHtml(i.symbol || '')} ${arrow}</span>`;
    }).join('');
    const sources = (s.sources || []).map((src) =>
      `<a href="${escapeHtml(src.url || '#')}" target="_blank" rel="noopener noreferrer" style="color:var(--blue);font-size:11px;text-decoration:none;margin-right:8px">${escapeHtml(src.title || 'Kilde')}</a>`
    ).join('');
    return `<div class="card">
      <div style="display:flex;align-items:center;gap:8px;margin-bottom:8px">${typeBadge(s.event_type)} ${strengthDots(s.strength)}</div>
      ${confidenceBar(s.confidence)}
      <div style="margin-top:8px;font-size:13px;color:var(--t)">${escapeHtml(s.reasoning || '')}</div>
      <div style="margin-top:8px">${instruments}</div>
      ${s.expires_at ? `<div style="font-size:10px;color:var(--m);margin-top:6px">Utloper: ${escapeHtml(timeAgo(s.expires_at))}</div>` : ''}
      ${sources ? `<div style="margin-top:6px">${sources}</div>` : ''}
    </div>`;
  }).join('');
}

function updateTimeline(events) {
  const filtersEl = document.getElementById('geo-timeline-filters');
  const listEl = document.getElementById('geo-timeline-list');
  if (!filtersEl || !listEl) return;
  if (!Array.isArray(events) || events.length === 0) {
    filtersEl.innerHTML = '';
    listEl.innerHTML = '<div style="color:var(--m);font-size:13px">Ingen hendelser</div>';
    return;
  }
  const types = ['all', ...new Set(events.map((e) => e.event_type).filter(Boolean))];
  filtersEl.innerHTML = types.map((t) => {
    const active = activeEventFilter === t;
    const label = t === 'all' ? 'Alle' : t;
    return `<button class="fc geo-filter-btn${active ? ' geo-filter-active' : ''}" data-type="${escapeHtml(t)}" style="font-size:11px;${active ? 'background:var(--blue);color:#fff' : ''}">${escapeHtml(label)}</button>`;
  }).join('');
  filtersEl.querySelectorAll('.geo-filter-btn').forEach((btn) => {
    btn.addEventListener('click', () => {
      activeEventFilter = btn.dataset.type;
      updateTimeline(events);
    });
  });
  const filtered = activeEventFilter === 'all' ? events : events.filter((e) => e.event_type === activeEventFilter);
  const sorted = [...filtered].sort((a, b) => new Date(b.timestamp || 0) - new Date(a.timestamp || 0));
  listEl.innerHTML = sorted.map((ev) => {
    const href = ev.url ? ` href="${escapeHtml(ev.url)}" target="_blank" rel="noopener noreferrer"` : '';
    return `<div style="padding:8px 0;border-bottom:1px solid var(--b);display:flex;align-items:center;gap:10px">
      <div class="mono" style="min-width:70px;font-size:10px;color:var(--m)">${escapeHtml(ev.timestamp ? new Date(ev.timestamp).toLocaleDateString('nb-NO', { day: '2-digit', month: 'short' }) : '')}</div>
      ${typeBadge(ev.event_type)}
      <a${href} style="flex:1;color:var(--blue);font-size:13px;text-decoration:none">${escapeHtml(ev.title || 'Uten tittel')}</a>
      <span style="font-size:10px;color:var(--m)">${escapeHtml(ev.source || '')}</span>
      <span style="font-size:11px;color:var(--t);min-width:36px;text-align:right">${escapeHtml(String(ev.confidence || 0))}%</span>
    </div>`;
  }).join('');
}

const IMPACT_INSTRUMENTS = ['XAUUSD', 'USOIL', 'EURUSD', 'SPX', 'USDJPY', 'Brent', 'NAS100', 'GBPUSD'];

function updateImpactMap(signals) {
  const el = document.getElementById('geo-impact-map');
  if (!el) return;
  if (!Array.isArray(signals) || signals.length === 0) {
    el.innerHTML = '<div style="color:var(--m);font-size:13px;padding:8px">Ingen aktive signaler</div>';
    return;
  }
  const types = [...new Set(signals.map((s) => s.event_type).filter(Boolean))];
  const lookup = {};
  signals.forEach((s) => (s.instruments || []).forEach((i) => {
    const key = `${s.event_type}|${i.symbol}`;
    if (!lookup[key]) lookup[key] = i.direction;
  }));
  const header = `<div style="font-weight:600;font-size:10px;color:var(--m)"></div>` +
    IMPACT_INSTRUMENTS.map((i) => `<div style="font-weight:600;font-size:10px;color:var(--m);text-align:center">${escapeHtml(i)}</div>`).join('');
  const rows = types.map((t) => {
    const cells = IMPACT_INSTRUMENTS.map((i) => {
      const dir = lookup[`${t}|${i}`];
      const sym = dir === 'bull' ? '\u2191' : dir === 'bear' ? '\u2193' : '\u2014';
      const color = dir === 'bull' ? 'var(--bull)' : dir === 'bear' ? 'var(--bear)' : 'var(--m)';
      return `<div class="mono" style="text-align:center;font-size:14px;color:${color}">${sym}</div>`;
    }).join('');
    return `<div style="font-size:11px;color:var(--t);display:flex;align-items:center">${typeBadge(t)}</div>${cells}`;
  }).join('');
  el.innerHTML = `<div style="display:grid;grid-template-columns:100px repeat(${IMPACT_INSTRUMENTS.length},1fr);gap:6px;align-items:center">${header}${rows}</div>`;
}

/** Clean up Leaflet map to prevent memory leaks. */
export function cleanup() {
  GeoMapPanel.destroy();
}
