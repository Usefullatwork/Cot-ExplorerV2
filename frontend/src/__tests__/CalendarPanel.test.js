import { describe, it, expect, beforeEach, vi, afterEach } from 'vitest';
import { render, update } from '../components/CalendarPanel.js';

/** Create a future event (offset hours from now). */
function makeEvent(overrides = {}) {
  const d = new Date();
  d.setHours(d.getHours() + 2);
  return {
    title: 'Non-Farm Payrolls',
    country: 'US',
    impact: 'High',
    date: d.toISOString(),
    forecast: '180K',
    actual: null,
    previous: '175K',
    ...overrides,
  };
}

/** Create a past event (offset hours ago). */
function makePastEvent(overrides = {}) {
  const d = new Date();
  d.setHours(d.getHours() - 5);
  return {
    title: 'CPI',
    country: 'US',
    impact: 'High',
    date: d.toISOString(),
    forecast: '3.2%',
    actual: '3.1%',
    previous: '3.3%',
    ...overrides,
  };
}

describe('CalendarPanel', () => {
  let container;

  beforeEach(() => {
    vi.useFakeTimers({ shouldAdvanceTime: false });
    document.body.innerHTML = '';
    container = document.createElement('div');
    container.id = 'panel-calendar';
    document.body.appendChild(container);
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it('renders the calendar panel skeleton with heading', () => {
    render(container);

    const heading = container.querySelector('.sh-t');
    expect(heading).not.toBeNull();
    expect(heading.textContent).toBe('Økonomisk kalender');
  });

  it('renders impact filter buttons (Alle, High, Medium, Low)', () => {
    render(container);

    const buttons = container.querySelectorAll('.cal-impact-filter');
    expect(buttons.length).toBe(4);

    const labels = Array.from(buttons).map((b) => b.textContent);
    expect(labels).toContain('Alle');
    expect(labels).toContain('High');
    expect(labels).toContain('Medium');
    expect(labels).toContain('Low');
  });

  it('renders "Ingen" when events array is empty', () => {
    render(container);
    update({ calendar: [] });

    const calH = document.getElementById('calH');
    expect(calH.textContent).toContain('Ingen');
  });

  it('renders High impact events in the High section', () => {
    render(container);
    update({
      calendar: [
        makeEvent({ impact: 'High', title: 'NFP' }),
        makeEvent({ impact: 'Medium', title: 'PMI' }),
      ],
    });

    const calH = document.getElementById('calH');
    expect(calH.textContent).toContain('NFP');
    expect(calH.textContent).not.toContain('PMI');
  });

  it('renders Medium impact events in the Medium section', () => {
    render(container);
    update({
      calendar: [
        makeEvent({ impact: 'Medium', title: 'PMI' }),
      ],
    });

    const calM = document.getElementById('calM');
    expect(calM.textContent).toContain('PMI');
  });

  it('filters events by impact when a filter button is clicked', () => {
    render(container);
    update({
      calendar: [
        makeEvent({ impact: 'High', title: 'NFP' }),
        makeEvent({ impact: 'Medium', title: 'PMI' }),
        makeEvent({ impact: 'Low', title: 'Building Permits' }),
      ],
    });

    // Click "Medium" filter
    const mediumBtn = Array.from(container.querySelectorAll('.cal-impact-filter'))
      .find((b) => b.dataset.impact === 'Medium');
    mediumBtn.click();

    // High section should show "Ingen" since we filtered to Medium only
    const calH = document.getElementById('calH');
    expect(calH.textContent).toContain('Ingen');

    // Medium section should show PMI
    const calM = document.getElementById('calM');
    expect(calM.textContent).toContain('PMI');
  });

  it('shows countdown area for upcoming events', () => {
    vi.useRealTimers(); // need real Date.now for countdown
    render(container);

    const futureDate = new Date();
    futureDate.setHours(futureDate.getHours() + 3);

    update({
      calendar: [
        makeEvent({ date: futureDate.toISOString(), title: 'FOMC' }),
      ],
    });

    const cdEl = document.getElementById('calCountdown');
    expect(cdEl).not.toBeNull();
    expect(cdEl.innerHTML).toContain('Neste hendelse');
    expect(cdEl.innerHTML).toContain('FOMC');
  });

  it('shows empty countdown when no upcoming events', () => {
    vi.useRealTimers();
    render(container);
    update({
      calendar: [makePastEvent()],
    });

    const cdEl = document.getElementById('calCountdown');
    expect(cdEl.innerHTML).toBe('');
  });

  it('populates country filter dropdown from event data', () => {
    render(container);
    update({
      calendar: [
        makeEvent({ country: 'US' }),
        makeEvent({ country: 'EU' }),
        makeEvent({ country: 'JP' }),
      ],
    });

    const select = document.getElementById('calCountryFilter');
    const options = Array.from(select.querySelectorAll('option'));
    const values = options.map((o) => o.value);
    expect(values).toContain('all');
    expect(values).toContain('US');
    expect(values).toContain('EU');
    expect(values).toContain('JP');
  });

  it('displays forecast and previous values in event rows', () => {
    render(container);

    // Ensure "Alle" filter is active (module state may persist from prior tests)
    const alleBtn = Array.from(container.querySelectorAll('.cal-impact-filter'))
      .find((b) => b.dataset.impact === 'all');
    if (alleBtn) alleBtn.click();

    update({
      calendar: [makeEvent({ impact: 'High', forecast: '180K', previous: '175K' })],
    });

    const calH = document.getElementById('calH');
    expect(calH.textContent).toContain('Forecast: 180K');
    expect(calH.textContent).toContain('Prev: 175K');
  });

  it('handles null macro data in update() gracefully', () => {
    render(container);
    update(null);

    // Should not throw; skeleton stays intact
    expect(container.querySelector('.sh-t')).not.toBeNull();
  });
});
