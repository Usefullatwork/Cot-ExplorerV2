/**
 * CalendarPanel component — economic calendar with High/Medium/Low impact events.
 *
 * Ports the renderCal function from v1 index.html.
 * Enhanced with impact filtering, country filter, countdown to next event, color-coded badges.
 */
import { escapeHtml } from '../utils.js';

/** @type {Array} Cached calendar data for re-filtering */
let _calendarData = [];
/** @type {string} Active impact filter: 'all', 'High', 'Medium', 'Low' */
let _impactFilter = 'all';
/** @type {string} Active country filter: 'all' or a country code */
let _countryFilter = 'all';
/** @type {number|null} Countdown interval ID */
let _countdownInterval = null;

/**
 * Build the calendar panel skeleton with filter controls.
 * @param {HTMLElement} container  #panel-calendar
 */
export function render(container) {
  container.innerHTML = `
    <div class="sh"><h2 class="sh-t">Okonomisk kalender</h2><div class="sh-b">Denne uken</div></div>
    <div id="calCountdown" style="margin-bottom:14px" role="timer" aria-label="Nedtelling til neste hendelse" aria-live="polite"></div>
    <div class="sbar2" style="margin-bottom:14px" role="toolbar" aria-label="Kalenderfiltre">
      <button class="fc cal-impact-filter on" data-impact="all" aria-pressed="true" aria-label="Vis alle hendelser">Alle</button>
      <button class="fc cal-impact-filter" data-impact="High" aria-pressed="false" aria-label="Vis kun high impact">High</button>
      <button class="fc cal-impact-filter" data-impact="Medium" aria-pressed="false" aria-label="Vis kun medium impact">Medium</button>
      <button class="fc cal-impact-filter" data-impact="Low" aria-pressed="false" aria-label="Vis kun low impact">Low</button>
      <span style="width:1px;height:20px;background:var(--b);margin:0 4px" aria-hidden="true"></span>
      <label for="calCountryFilter" class="sr-only">Filtrer etter land</label>
      <select id="calCountryFilter" aria-label="Filtrer etter land" style="background:var(--s);border:1px solid var(--b);color:var(--t);font-family:'DM Sans',sans-serif;font-size:12px;padding:4px 8px;border-radius:6px;outline:none">
        <option value="all">Alle land</option>
      </select>
    </div>
    <div class="g2">
      <div class="card" role="region" aria-label="High impact hendelser"><div class="ct">High Impact</div><div id="calH" aria-live="polite"></div></div>
      <div class="card" role="region" aria-label="Medium impact hendelser"><div class="ct">Medium Impact</div><div id="calM" aria-live="polite"></div></div>
    </div>
    <div id="calLow" style="margin-top:12px" aria-live="polite"></div>`;

  // Impact filter click handler (delegated)
  container.addEventListener('click', (e) => {
    const btn = e.target.closest('.cal-impact-filter');
    if (!btn) return;
    _impactFilter = btn.dataset.impact;
    container.querySelectorAll('.cal-impact-filter').forEach((b) => {
      b.classList.remove('on');
      b.setAttribute('aria-pressed', 'false');
    });
    btn.classList.add('on');
    btn.setAttribute('aria-pressed', 'true');
    _renderFiltered();
  });

  // Country filter change handler
  const countrySelect = container.querySelector('#calCountryFilter');
  if (countrySelect) {
    countrySelect.addEventListener('change', (e) => {
      _countryFilter = e.target.value;
      _renderFiltered();
    });
  }
}

/**
 * Format a countdown string from now to a target date.
 * @param {Date} target
 * @returns {string}
 */
function formatCountdown(target) {
  const diff = target.getTime() - Date.now();
  if (diff <= 0) return 'Na';
  const hours = Math.floor(diff / 3600000);
  const mins = Math.floor((diff % 3600000) / 60000);
  const secs = Math.floor((diff % 60000) / 1000);
  if (hours > 24) {
    const days = Math.floor(hours / 24);
    return `${days}d ${hours % 24}t`;
  }
  return `${hours}t ${mins}m ${secs}s`;
}

/**
 * Start or restart the countdown timer to the next upcoming event.
 */
function updateCountdown() {
  if (_countdownInterval) clearInterval(_countdownInterval);

  const now = Date.now();
  const upcoming = _calendarData
    .filter((e) => new Date(e.date).getTime() > now)
    .sort((a, b) => new Date(a.date) - new Date(b.date));

  const cdEl = document.getElementById('calCountdown');
  if (!cdEl) return;

  if (!upcoming.length) {
    cdEl.innerHTML = '';
    return;
  }

  const next = upcoming[0];
  const nextDate = new Date(next.date);
  const impactCls = next.impact === 'High' ? 'bear' : next.impact === 'Medium' ? 'warn' : 'neutral';

  function tick() {
    cdEl.innerHTML = `
      <div class="card" style="display:flex;align-items:center;gap:14px;padding:12px 16px">
        <div>
          <div style="font-size:10px;color:var(--m);text-transform:uppercase;letter-spacing:1px;margin-bottom:4px">Neste hendelse</div>
          <div style="font-size:14px;font-weight:600">${escapeHtml(next.title)}</div>
          <div style="font-size:11px;color:var(--m);margin-top:2px">${escapeHtml(next.country)} <span class="calimp ${escapeHtml(next.impact)}" style="margin-left:6px">${escapeHtml(next.impact)}</span></div>
        </div>
        <div style="margin-left:auto;text-align:right">
          <div style="font-family:'DM Mono',monospace;font-size:22px;font-weight:600;color:var(--${impactCls})">${formatCountdown(nextDate)}</div>
          <div style="font-size:10px;color:var(--m);margin-top:2px">${nextDate.toLocaleString('nb-NO', { weekday: 'short', day: 'numeric', month: 'short', hour: '2-digit', minute: '2-digit' })}</div>
        </div>
      </div>`;
  }

  tick();
  _countdownInterval = setInterval(tick, 1000);
}

/**
 * Render a list of calendar events as HTML.
 * @param {Array} events
 * @returns {string}
 */
function renderEvents(events) {
  if (!events || !events.length) {
    return '<div style="color:var(--m);font-size:13px;padding:10px 0">Ingen</div>';
  }

  return events
    .map((e) => {
      const dt = new Date(e.date);
      const t = dt.toLocaleString('nb-NO', { weekday: 'short', hour: '2-digit', minute: '2-digit' });
      const isPast = dt.getTime() < Date.now();
      const opacity = isPast ? 'opacity:0.5' : '';
      return `<div class="cali" style="${opacity}" role="listitem" aria-label="${escapeHtml(e.title)}, ${escapeHtml(e.country)}, ${escapeHtml(e.impact)} impact">
        <div class="calt">${escapeHtml(t)}</div>
        <div><div class="calti">${escapeHtml(e.title)}</div><div class="calcc">${escapeHtml(e.country)} - Forecast: ${escapeHtml(e.forecast || '-')}${e.actual ? ' | Actual: ' + escapeHtml(e.actual) : ''}${e.previous ? ' | Prev: ' + escapeHtml(e.previous) : ''}</div></div>
        <span class="calimp ${escapeHtml(e.impact)}" aria-label="${escapeHtml(e.impact)} impact">${escapeHtml(e.impact)}</span>
      </div>`;
    })
    .join('');
}

/**
 * Re-render calendar events using current filters.
 */
function _renderFiltered() {
  let filtered = _calendarData;

  // Apply country filter
  if (_countryFilter !== 'all') {
    filtered = filtered.filter((e) => e.country === _countryFilter);
  }

  // Apply impact filter
  if (_impactFilter !== 'all') {
    filtered = filtered.filter((e) => e.impact === _impactFilter);
  }

  const high = filtered.filter((e) => e.impact === 'High');
  const medium = filtered.filter((e) => e.impact === 'Medium');
  const low = filtered.filter((e) => e.impact === 'Low');

  const hEl = document.getElementById('calH');
  const mEl = document.getElementById('calM');
  const lEl = document.getElementById('calLow');

  if (hEl) hEl.innerHTML = renderEvents(high);
  if (mEl) mEl.innerHTML = renderEvents(medium);
  if (lEl) {
    if (low.length && (_impactFilter === 'all' || _impactFilter === 'Low')) {
      lEl.innerHTML = `<div class="card"><div class="ct">Low Impact (${low.length})</div>${renderEvents(low)}</div>`;
    } else {
      lEl.innerHTML = '';
    }
  }
}

/**
 * Update the calendar panel with fresh event data.
 * @param {Object} macro  Full macro payload (uses macro.calendar)
 */
/** Stop countdown timer when leaving the tab. */
export function cleanup() {
  if (_countdownInterval) {
    clearInterval(_countdownInterval);
    _countdownInterval = null;
  }
}

export function update(macro) {
  if (!macro) return;

  _calendarData = macro.calendar || [];

  // Populate country filter dropdown
  const countries = [...new Set(_calendarData.map((e) => e.country).filter(Boolean))].sort();
  const countrySelect = document.getElementById('calCountryFilter');
  if (countrySelect) {
    const current = countrySelect.value;
    countrySelect.innerHTML = '<option value="all">Alle land</option>' +
      countries.map((c) => `<option value="${escapeHtml(c)}"${c === current ? ' selected' : ''}>${escapeHtml(c)}</option>`).join('');
  }

  _renderFiltered();
  updateCountdown();
}
