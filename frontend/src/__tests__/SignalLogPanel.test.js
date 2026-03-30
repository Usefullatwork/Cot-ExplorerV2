import { describe, it, expect, beforeEach, vi } from 'vitest';

// Mock API calls
vi.mock('../api.js', () => ({
  fetchSignalLog: vi.fn(),
  fetchSignalAnalytics: vi.fn(),
}));

// Mock state
vi.mock('../state.js', () => ({
  setState: vi.fn(),
  subscribe: vi.fn(),
}));

import { render, update } from '../components/SignalLogPanel.js';

/** Build a sample signals array. */
function makeSignals(overrides = []) {
  if (overrides.length) return overrides;
  return [
    { time: new Date(Date.now() - 3600000).toISOString(), instrument: 'EURUSD', direction: 'long', grade: 'A+', score: 14, entry: 1.0845, risk_reward: 2.1, result: 'hit' },
    { time: new Date(Date.now() - 7200000).toISOString(), instrument: 'XAUUSD', direction: 'short', grade: 'B', score: 10, entry: 2045.5, risk_reward: 1.3, result: 'miss' },
    { time: new Date(Date.now() - 10800000).toISOString(), instrument: 'GBPUSD', direction: 'long', grade: 'A', score: 12, entry: 1.265, risk_reward: 1.8, result: 'pending' },
  ];
}

/** Build a data payload matching the component's expected format. */
function makeData(overrides = {}) {
  return { signals: makeSignals(), ...overrides };
}

describe('SignalLogPanel', () => {
  let container;

  beforeEach(() => {
    document.body.innerHTML = '';
    container = document.createElement('div');
    container.id = 'panel-signal-log';
    document.body.appendChild(container);
  });

  it('renders the skeleton with section headings', () => {
    render(container);

    const headings = container.querySelectorAll('.sh-t');
    const texts = Array.from(headings).map((h) => h.textContent);
    expect(texts).toContain('Signal-logg');
    expect(texts).toContain('Analytikk');
  });

  it('renders the stats container', () => {
    render(container);

    const stats = document.getElementById('sl-stats');
    expect(stats).not.toBeNull();
  });

  it('renders the signal table with correct headers', () => {
    render(container);

    const table = document.getElementById('sl-table');
    expect(table).not.toBeNull();

    const headers = Array.from(table.querySelectorAll('thead th')).map((th) => th.textContent);
    expect(headers).toContain('Tid');
    expect(headers).toContain('Instrument');
    expect(headers).toContain('Retning');
    expect(headers).toContain('Grad');
    expect(headers).toContain('Score');
    expect(headers).toContain('Entry');
    expect(headers).toContain('R:R');
    expect(headers).toContain('Resultat');
  });

  it('shows loading placeholder in tbody before update()', () => {
    render(container);

    const tbody = document.getElementById('sl-tbody');
    expect(tbody.textContent).toContain('Laster signaler');
  });

  it('renders analytics placeholder on initial render', () => {
    render(container);

    const analytics = document.getElementById('sl-analytics');
    expect(analytics).not.toBeNull();
    expect(analytics.textContent).toContain('Laster analytikk');
  });

  it('populates stats cards after update()', () => {
    render(container);
    update(makeData());

    const stats = document.getElementById('sl-stats');
    // Should show total count
    expect(stats.textContent).toContain('3');
    // Should show "Totalt" label
    expect(stats.textContent).toContain('Totalt');
    // Should show "Treffrate" label
    expect(stats.textContent).toContain('Treffrate');
  });

  it('calculates hit rate correctly', () => {
    render(container);
    // 1 hit out of 3 signals
    update(makeData());

    const stats = document.getElementById('sl-stats');
    // 1/3 = 33.3%
    expect(stats.textContent).toContain('33.3%');
  });

  it('populates table rows with signal data', () => {
    render(container);
    update(makeData());

    const tbody = document.getElementById('sl-tbody');
    const rows = tbody.querySelectorAll('tr');
    expect(rows.length).toBe(3);

    // Check instrument names appear
    expect(tbody.textContent).toContain('EURUSD');
    expect(tbody.textContent).toContain('XAUUSD');
    expect(tbody.textContent).toContain('GBPUSD');
  });

  it('renders result badges (HIT, MISS, PENDING)', () => {
    render(container);
    update(makeData());

    const tbody = document.getElementById('sl-tbody');
    expect(tbody.textContent).toContain('HIT');
    expect(tbody.textContent).toContain('MISS');
    expect(tbody.textContent).toContain('PENDING');
  });

  it('renders grade badges (A+, B, A)', () => {
    render(container);
    update(makeData());

    const tbody = document.getElementById('sl-tbody');
    const grades = tbody.querySelectorAll('.tgrade');
    const gradeTexts = Array.from(grades).map((g) => g.textContent);
    expect(gradeTexts).toContain('A+');
    expect(gradeTexts).toContain('B');
    expect(gradeTexts).toContain('A');
  });

  it('renders R:R values with :1 suffix', () => {
    render(container);
    update(makeData());

    const tbody = document.getElementById('sl-tbody');
    expect(tbody.textContent).toContain('2.1:1');
    expect(tbody.textContent).toContain('1.3:1');
  });

  it('shows empty state when signals array is empty', () => {
    render(container);
    update({ signals: [] });

    const tbody = document.getElementById('sl-tbody');
    expect(tbody.textContent).toContain('Ingen signaler');
  });

  it('handles null data in update() gracefully', () => {
    render(container);
    // Should not throw
    update(null);

    // Skeleton should still be intact
    expect(document.getElementById('sl-stats')).not.toBeNull();
    expect(document.getElementById('sl-table')).not.toBeNull();
  });

  it('handles undefined data in update() gracefully', () => {
    render(container);
    // Should not throw
    update(undefined);

    expect(document.getElementById('sl-stats')).not.toBeNull();
  });

  it('renders per-grade breakdown cards for A+, A, B', () => {
    render(container);
    update(makeData());

    const stats = document.getElementById('sl-stats');
    // Should show grade labels
    expect(stats.textContent).toContain('A+');
    expect(stats.textContent).toContain('A');
    expect(stats.textContent).toContain('B');
    // Should show "signaler" label per grade card
    expect(stats.textContent).toContain('signaler');
  });

  it('clears stats when signals is not an array', () => {
    render(container);
    update({ signals: 'invalid' });

    const stats = document.getElementById('sl-stats');
    expect(stats.innerHTML).toBe('');
  });
});
