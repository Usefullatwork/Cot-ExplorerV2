import { describe, it, expect, beforeEach } from 'vitest';
import { render, update } from '../components/BacktestDashboard.js';

function makeStats(overrides = {}) {
  return {
    total_trades: 50,
    wins: 30,
    losses: 20,
    win_rate: 60.0,
    avg_win_rr: 1.85,
    avg_loss_rr: -0.95,
    profit_factor: 2.92,
    max_drawdown_rr: 3.5,
    avg_rr: 0.73,
    best_trade_rr: 4.2,
    worst_trade_rr: -1.0,
    avg_duration_hours: 36,
    equity_curve: [0.5, 1.2, 0.8, 1.5, 2.3, 3.0],
    by_instrument: [
      { instrument: 'EURUSD', trades: 20, wins: 14, win_rate: 70.0, avg_pnl: 0.95, total_pnl: 19.0 },
      { instrument: 'GOLD', trades: 15, wins: 8, win_rate: 53.3, avg_pnl: 0.42, total_pnl: 6.3 },
    ],
    by_grade: [
      { grade: 'A+', trades: 15, wins: 12, win_rate: 80.0 },
      { grade: 'A', trades: 20, wins: 12, win_rate: 60.0 },
      { grade: 'B', trades: 15, wins: 6, win_rate: 40.0 },
    ],
    ...overrides,
  };
}

describe('BacktestDashboard', () => {
  let container;

  beforeEach(() => {
    document.body.innerHTML = '';
    container = document.createElement('div');
    container.id = 'panel-backtest';
    document.body.appendChild(container);
  });

  it('renders skeleton with heading', () => {
    render(container);
    const heading = container.querySelector('.sh-t');
    expect(heading.textContent).toBe('Backtest Dashboard');
  });

  it('renders 12 stat cards', () => {
    render(container);
    update(makeStats());

    const cards = document.querySelectorAll('#btStats .card');
    expect(cards.length).toBe(12);
  });

  it('shows win rate with correct color', () => {
    render(container);
    update(makeStats({ win_rate: 65.0 }));

    const stats = document.getElementById('btStats');
    expect(stats.innerHTML).toContain('65.0%');
    expect(stats.innerHTML).toContain('bull');
  });

  it('shows loss count with bear color', () => {
    render(container);
    update(makeStats({ losses: 20 }));

    const stats = document.getElementById('btStats');
    expect(stats.innerHTML).toContain('20');
  });

  it('renders equity curve SVG', () => {
    render(container);
    update(makeStats());

    const eq = document.getElementById('btEquity');
    expect(eq.innerHTML).toContain('<svg');
  });

  it('shows empty equity message when no data', () => {
    render(container);
    update(makeStats({ equity_curve: [] }));

    const eq = document.getElementById('btEquity');
    expect(eq.textContent).toContain('Ingen backtest-data');
  });

  it('renders instrument breakdown table', () => {
    render(container);
    update(makeStats());

    const inst = document.getElementById('btInstruments');
    expect(inst.innerHTML).toContain('EURUSD');
    expect(inst.innerHTML).toContain('GOLD');
  });

  it('renders grade breakdown bars', () => {
    render(container);
    update(makeStats());

    const grades = document.getElementById('btGrades');
    expect(grades.innerHTML).toContain('A+');
    expect(grades.innerHTML).toContain('80%');
  });

  it('shows trade count in header', () => {
    render(container);
    update(makeStats({ total_trades: 42 }));

    const ts = document.getElementById('btUpdated');
    expect(ts.textContent).toContain('42');
  });

  it('handles null data gracefully', () => {
    render(container);
    update(null);

    const stats = document.getElementById('btStats');
    expect(stats.innerHTML).toBe('');
  });
});
