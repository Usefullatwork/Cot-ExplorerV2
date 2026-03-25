/**
 * CalendarPanel component — economic calendar with High/Medium impact events.
 *
 * Ports the renderCal function from v1 index.html.
 */

/**
 * Build the static calendar panel skeleton.
 * @param {HTMLElement} container  #panel-calendar
 */
export function render(container) {
  container.innerHTML = `
    <div class="sh"><div class="sh-t">Okonomisk kalender</div><div class="sh-b">Denne uken</div></div>
    <div class="g2">
      <div class="card"><div class="ct">High Impact</div><div id="calH"></div></div>
      <div class="card"><div class="ct">Medium Impact</div><div id="calM"></div></div>
    </div>`;
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
      return `<div class="cali">
        <div class="calt">${t}</div>
        <div><div class="calti">${e.title}</div><div class="calcc">${e.country} - Forecast: ${e.forecast || '-'}</div></div>
        <span class="calimp ${e.impact}">${e.impact}</span>
      </div>`;
    })
    .join('');
}

/**
 * Update the calendar panel with fresh event data.
 * @param {Object} macro  Full macro payload (uses macro.calendar)
 */
export function update(macro) {
  if (!macro) return;

  const cal = macro.calendar || [];
  const high = cal.filter((e) => e.impact === 'High');
  const medium = cal.filter((e) => e.impact === 'Medium');

  const hEl = document.getElementById('calH');
  const mEl = document.getElementById('calM');

  if (hEl) hEl.innerHTML = renderEvents(high);
  if (mEl) mEl.innerHTML = renderEvents(medium);
}
