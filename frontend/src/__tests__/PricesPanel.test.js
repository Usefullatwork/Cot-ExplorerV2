import { describe, it, expect, beforeEach } from 'vitest';
import { render, update, stopPolling } from '../components/PricesPanel.js';

function makeItem(overrides = {}) {
  return {
    instrument: 'EURUSD',
    name: 'EUR/USD',
    group: 'Valuta',
    price: 1.08800,
    chg_1d: 0.15,
    chg_5d: -0.32,
    ...overrides,
  };
}

describe('PricesPanel', () => {
  let container;

  beforeEach(() => {
    stopPolling();
    document.body.innerHTML = '';
    container = document.createElement('div');
    container.id = 'panel-prices';
    document.body.appendChild(container);
  });

  it('renders skeleton with heading', () => {
    render(container);
    const heading = container.querySelector('.sh-t');
    expect(heading.textContent).toBe('Priser');
  });

  it('renders price cards after update', () => {
    render(container);
    update({ items: [makeItem(), makeItem({ instrument: 'GOLD', name: 'Gull', group: 'Ravarer', price: 2050.50 })] });

    const cards = container.querySelectorAll('.card');
    expect(cards.length).toBe(2);
  });

  it('groups items by category', () => {
    render(container);
    update({
      items: [
        makeItem({ group: 'Valuta' }),
        makeItem({ instrument: 'SPX', name: 'S&P 500', group: 'Indekser', price: 5200.50 }),
      ],
    });

    const headings = container.querySelectorAll('.sh-t');
    const labels = Array.from(headings).map((h) => h.textContent);
    expect(labels.some((l) => l.includes('Valuta'))).toBe(true);
    expect(labels.some((l) => l.includes('Indekser'))).toBe(true);
  });

  it('shows price with data-value class', () => {
    render(container);
    update({ items: [makeItem({ price: 1.08800 })] });

    const num = container.querySelector('.snum');
    expect(num.classList.contains('data-value')).toBe(true);
    expect(num.textContent).toBe('1.08800');
  });

  it('shows 1d and 5d changes', () => {
    render(container);
    update({ items: [makeItem({ chg_1d: 0.5, chg_5d: -1.2 })] });

    const card = container.querySelector('.card');
    expect(card.textContent).toContain('+0.50%');
    expect(card.textContent).toContain('-1.20%');
  });

  it('handles missing change data', () => {
    render(container);
    update({ items: [makeItem({ chg_1d: null, chg_5d: null })] });

    const card = container.querySelector('.card');
    expect(card.textContent).toContain('--');
  });

  it('updates timestamp on update', () => {
    render(container);
    update({ items: [makeItem()] });

    const ts = document.getElementById('pricesUpdated');
    expect(ts.textContent).toContain('Oppdatert');
  });

  it('handles empty items gracefully', () => {
    render(container);
    update({ items: [] });

    const content = document.getElementById('pricesContent');
    expect(content.textContent).toContain('Ingen prisdata');
  });
});
