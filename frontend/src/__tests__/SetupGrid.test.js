import { describe, it, expect, beforeEach } from 'vitest';
import { render, update } from '../components/SetupGrid.js';

/** Create a minimal signal data object. */
function makeSignal(overrides = {}) {
  return {
    name: 'EURUSD',
    label: 'EUR/USD',
    grade: 'A+',
    score: 7,
    score_pct: 87,
    grade_color: 'bull',
    class: 'A',
    dir_color: 'bull',
    current: 1.088,
    timeframe_bias: 'MAKRO',
    session: { active: true },
    binary_risk: [],
    cot: { net: 50000, color: 'bull', bias: 'BULLISH', report: 'Legacy', date: '2026-03-25' },
    score_details: [{ kryss: 'COT', verdi: true }],
    resistances: [],
    supports: [],
    ...overrides,
  };
}

describe('SetupGrid', () => {
  let container;

  beforeEach(() => {
    document.body.innerHTML = '';
    container = document.createElement('div');
    container.id = 'panel-setups';
    document.body.appendChild(container);
  });

  it('renders the skeleton with filter bar', () => {
    render(container);
    expect(document.getElementById('ideStats')).not.toBeNull();
    expect(document.getElementById('ideGrid')).not.toBeNull();
    expect(document.getElementById('setupFilters')).not.toBeNull();
  });

  it('renders stat cards on update', () => {
    render(container);
    update({
      trading_levels: { EURUSD: makeSignal() },
      vix_regime: { label: 'Full', color: 'bull' },
    });

    const stats = document.getElementById('ideStats');
    expect(stats.innerHTML).toContain('A+ Setups');
    expect(stats.innerHTML).toContain('1');
  });

  it('renders setup cards in grid', () => {
    render(container);
    update({
      trading_levels: {
        EURUSD: makeSignal(),
        GOLD: makeSignal({ name: 'Gold', grade: 'B', timeframe_bias: 'SWING', class: 'B' }),
      },
    });

    const grid = document.getElementById('ideGrid');
    const cards = grid.querySelectorAll('.tic');
    expect(cards.length).toBe(2);
  });

  it('renders filter chips after update', () => {
    render(container);
    update({
      trading_levels: {
        EURUSD: makeSignal(),
        GOLD: makeSignal({ name: 'Gold', grade: 'B', class: 'B' }),
      },
    });

    const chips = document.getElementById('setupFilterChips');
    expect(chips.innerHTML).toContain('Klasse');
    expect(chips.innerHTML).toContain('A+');
    expect(chips.innerHTML).toContain('B');
  });

  it('shows empty state when no data', () => {
    render(container);
    update({ trading_levels: {} });

    const grid = document.getElementById('ideGrid');
    expect(grid.innerHTML).toContain('Ingen trading setups');
  });

  it('sorts A+ before B', () => {
    render(container);
    update({
      trading_levels: {
        GOLD: makeSignal({ name: 'Gold', grade: 'B', score: 5 }),
        EURUSD: makeSignal({ name: 'EURUSD', grade: 'A+', score: 7 }),
      },
    });

    const cards = document.querySelectorAll('.tic');
    expect(cards[0].textContent).toContain('EURUSD');
  });

  it('shows A grade count in stats', () => {
    render(container);
    update({
      trading_levels: {
        EURUSD: makeSignal({ grade: 'A' }),
      },
    });

    const stats = document.getElementById('ideStats');
    expect(stats.innerHTML).toContain('A Setups');
  });
});
