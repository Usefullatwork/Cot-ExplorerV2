import { describe, it, expect, beforeEach, vi } from 'vitest';
import { render, update } from '../components/CompetitorPanel.js';

/** Sample competitor data row. */
function makeCompetitor(overrides = {}) {
  return {
    source: 'Markedspuls',
    winRate: 58.5,
    avgRR: 1.85,
    totalSignals: 120,
    ...overrides,
  };
}

describe('CompetitorPanel', () => {
  let container;

  beforeEach(() => {
    document.body.innerHTML = '';
    container = document.createElement('div');
    container.id = 'panel-competitor';
    document.body.appendChild(container);
  });

  it('renders the panel skeleton with heading "Konkurrentanalyse"', () => {
    render(container);

    const heading = container.querySelector('.sh-t');
    expect(heading).not.toBeNull();
    expect(heading.textContent).toBe('Konkurrentanalyse');
  });

  it('renders the refresh button', () => {
    render(container);

    const btn = document.getElementById('compRefreshBtn');
    expect(btn).not.toBeNull();
    expect(btn.textContent).toBe('Oppdater');
  });

  it('renders Myfxbook sentiment section with pairs', () => {
    render(container);

    const sentimentEl = document.getElementById('compSentiment');
    expect(sentimentEl).not.toBeNull();
    expect(sentimentEl.textContent).toContain('EUR/USD');
    expect(sentimentEl.textContent).toContain('GBP/USD');
    expect(sentimentEl.textContent).toContain('USD/JPY');
  });

  it('renders sentiment bars with long/short percentages', () => {
    render(container);

    const sentimentEl = document.getElementById('compSentiment');
    expect(sentimentEl.textContent).toContain('Long');
    expect(sentimentEl.textContent).toContain('Short');
    expect(sentimentEl.textContent).toContain('62%');
    expect(sentimentEl.textContent).toContain('38%');
  });

  it('renders TradingView ideas section', () => {
    render(container);

    const ideasEl = document.getElementById('compIdeas');
    expect(ideasEl).not.toBeNull();
    expect(ideasEl.textContent).toContain('EURUSD potensielt bunn');
    expect(ideasEl.textContent).toContain('@TraderX');
  });

  it('shows empty state when update() receives null data', () => {
    render(container);

    const compTable = document.getElementById('compTable');
    expect(compTable.textContent).toContain('Ingen konkurrentdata ennå');
  });

  it('shows empty state when update() receives empty array', () => {
    render(container);
    update([]);

    const compTable = document.getElementById('compTable');
    expect(compTable.textContent).toContain('Ingen konkurrentdata ennå');
  });

  it('renders competitor table when data is provided', () => {
    render(container);
    update([
      makeCompetitor({ source: 'Markedspuls', winRate: 58.5, avgRR: 1.85, totalSignals: 120 }),
      makeCompetitor({ source: 'FxSignals', winRate: 52.0, avgRR: 1.50, totalSignals: 200 }),
    ]);

    const compTable = document.getElementById('compTable');
    expect(compTable.textContent).toContain('Markedspuls');
    expect(compTable.textContent).toContain('FxSignals');
    expect(compTable.textContent).toContain('58.5%');
    expect(compTable.textContent).toContain('52.0%');
  });

  it('sorts competitors by win rate descending and marks best', () => {
    render(container);
    update([
      makeCompetitor({ source: 'Low', winRate: 45.0 }),
      makeCompetitor({ source: 'High', winRate: 62.0 }),
      makeCompetitor({ source: 'Mid', winRate: 55.0 }),
    ]);

    const compTable = document.getElementById('compTable');
    const rows = compTable.querySelectorAll('tbody tr');
    expect(rows.length).toBe(3);

    // First row should be the best (highest win rate)
    expect(rows[0].textContent).toContain('High');
    expect(rows[0].textContent).toContain('BEST');
  });

  it('renders summary stat cards (Kilder, Totalt signaler, Snitt Win Rate, Snitt R:R)', () => {
    render(container);
    update([
      makeCompetitor({ totalSignals: 100 }),
      makeCompetitor({ source: 'Other', totalSignals: 200 }),
    ]);

    const compTable = document.getElementById('compTable');
    const statCards = compTable.querySelectorAll('.card');
    expect(statCards.length).toBe(4);

    const texts = Array.from(statCards).map((c) => c.textContent);
    expect(texts.some((t) => t.includes('Kilder') && t.includes('2'))).toBe(true);
    expect(texts.some((t) => t.includes('300'))).toBe(true);
  });

  it('sets refresh button to "Oppdaterer..." during refresh', () => {
    vi.useFakeTimers();
    render(container);

    const btn = document.getElementById('compRefreshBtn');
    btn.click();

    expect(btn.textContent).toBe('Oppdaterer...');
    expect(btn.classList.contains('on')).toBe(true);

    // After timeout, should revert
    vi.advanceTimersByTime(1500);
    expect(btn.textContent).toBe('Oppdater');
    expect(btn.classList.contains('on')).toBe(false);

    vi.useRealTimers();
  });
});
