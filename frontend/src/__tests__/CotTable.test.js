import { describe, it, expect, beforeEach } from 'vitest';
import { render, update, onOpenChart, _reset } from '../components/CotTable.js';

/** Minimal COT market row data. */
function makeRow(overrides = {}) {
  return {
    symbol: 'ES',
    market: 'E-mini S&P 500',
    navn_no: 'S&P 500 mini',
    kategori: 'aksjer',
    forklaring: 'Aksjeindeks',
    report: 'Legacy',
    open_interest: 2500000,
    change_spec_net: 12000,
    spekulanter: { net: 80000, long: 300000, short: 220000 },
    ...overrides,
  };
}

describe('CotTable (Accordion)', () => {
  let container;

  beforeEach(() => {
    _reset();
    document.body.innerHTML = '';
    container = document.createElement('div');
    container.id = 'panel-cot';
    document.body.appendChild(container);
  });

  it('renders the COT panel skeleton with search input', () => {
    render(container);

    expect(document.getElementById('cotS')).not.toBeNull();
    expect(document.getElementById('cotGrid')).not.toBeNull();
  });

  it('renders section heading "COT-posisjoner"', () => {
    render(container);

    const heading = container.querySelector('.sh-t');
    expect(heading.textContent).toBe('COT-posisjoner');
  });

  it('shows market count badge', () => {
    render(container);
    update([
      makeRow(),
      makeRow({ symbol: 'GC', navn_no: 'Gull', kategori: 'ravarer' }),
      makeRow({ symbol: 'EC', navn_no: 'Euro FX', kategori: 'valuta' }),
    ]);

    const cnt = document.getElementById('cotCnt');
    expect(cnt.textContent).toBe('3 markeder');
  });

  it('renders accordion groups by category', () => {
    render(container);
    update([
      makeRow({ symbol: 'ES', kategori: 'aksjer' }),
      makeRow({ symbol: 'GC', kategori: 'ravarer' }),
    ]);

    const accordions = document.querySelectorAll('.cot-accordion');
    expect(accordions.length).toBe(2);
  });

  it('shows category labels with emoji', () => {
    render(container);
    update([makeRow({ kategori: 'aksjer' })]);

    const header = document.querySelector('.cot-accordion-header');
    expect(header.textContent).toContain('Aksjer');
  });

  it('shows stacked bar in category header', () => {
    render(container);
    update([makeRow({ kategori: 'aksjer', spekulanter: { net: 100000 }, open_interest: 500000 })]);

    const header = document.querySelector('.cot-accordion-header');
    expect(header.innerHTML).toContain('var(--bull)');
  });

  it('renders market cards inside accordion body', () => {
    render(container);
    update([makeRow(), makeRow({ symbol: 'NQ', navn_no: 'Nasdaq', kategori: 'aksjer' })]);

    // Click the aksjer header to open it (first category auto-opens)
    const cards = document.querySelectorAll('.cot-market-card');
    expect(cards.length).toBeGreaterThanOrEqual(1);
  });

  it('displays Norwegian name in market cards', () => {
    render(container);
    update([makeRow()]);

    const card = document.querySelector('.cot-market-card');
    expect(card.textContent).toContain('S&P 500 mini');
  });

  it('shows signal badge in market card', () => {
    render(container);
    update([makeRow({ spekulanter: { net: 500000 }, open_interest: 1000000 })]);

    const badge = document.querySelector('.sp2');
    expect(badge).not.toBeNull();
  });

  it('shows empty state when data is empty', () => {
    render(container);
    update([]);

    const grid = document.getElementById('cotGrid');
    expect(grid.textContent).toContain('Ingen COT-data');
  });

  it('handles non-array input gracefully', () => {
    render(container);
    update(null);

    const grid = document.getElementById('cotGrid');
    expect(grid).not.toBeNull();
  });

  it('auto-opens first category with data', () => {
    render(container);
    update([makeRow({ kategori: 'valuta' })]);

    const body = document.querySelector('.cot-accordion-body');
    // Auto-opened accordion shows as grid display
    expect(body.style.display).toBe('grid');
  });

  it('calls onOpenChart callback when a card is clicked', () => {
    render(container);

    let called = null;
    onOpenChart((sym, report, name) => {
      called = { sym, report, name };
    });

    update([makeRow()]);

    const card = document.querySelector('.cot-market-card');
    expect(card).not.toBeNull();
    card.click();

    expect(called).not.toBeNull();
    expect(called.sym).toBe('ES');
    expect(called.report).toBe('Legacy');
  });

  it('toggles accordion on header click', () => {
    render(container);
    update([makeRow({ kategori: 'aksjer' }), makeRow({ symbol: 'GC', kategori: 'ravarer' })]);

    // aksjer should be auto-opened, ravarer closed
    const headers = document.querySelectorAll('.cot-accordion-header');
    const ravarerHeader = Array.from(headers).find((h) => h.dataset.cat === 'ravarer');
    expect(ravarerHeader).not.toBeNull();

    // Click to open ravarer
    ravarerHeader.click();
    const ravarerBody = ravarerHeader.closest('.cot-accordion').querySelector('.cot-accordion-body');
    // After click, the accordion should re-render with ravarer open
    expect(document.querySelector('[data-cat="ravarer"] .cot-accordion-body').style.display).not.toBe('none');
  });

  it('shows net % in market card', () => {
    render(container);
    update([makeRow({ spekulanter: { net: 80000 }, open_interest: 2500000 })]);

    const card = document.querySelector('.cot-market-card');
    // 80000/2500000 = 3.2%
    expect(card.textContent).toContain('3.2%');
  });

  it('renders sparkline when cot_history is provided', () => {
    render(container);
    update([makeRow({ cot_history: [10, 20, 30, 40, 50] })]);

    const card = document.querySelector('.cot-market-card');
    expect(card.innerHTML).toContain('<svg');
  });
});
