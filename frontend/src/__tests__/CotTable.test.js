import { describe, it, expect, beforeEach } from 'vitest';
import { render, update, onOpenChart } from '../components/CotTable.js';

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

describe('CotTable', () => {
  let container;

  beforeEach(() => {
    document.body.innerHTML = '';
    container = document.createElement('div');
    container.id = 'panel-cot';
    document.body.appendChild(container);
  });

  it('renders the COT panel skeleton with search input', () => {
    render(container);

    expect(document.getElementById('cotS')).not.toBeNull();
    expect(document.getElementById('cotGrid')).not.toBeNull();
    expect(document.getElementById('fchips')).not.toBeNull();
  });

  it('renders section heading "COT-posisjoner"', () => {
    render(container);

    const heading = container.querySelector('.sh-t');
    expect(heading.textContent).toBe('COT-posisjoner');
  });

  it('renders table rows after update()', () => {
    render(container);
    update([makeRow(), makeRow({ symbol: 'GC', navn_no: 'Gull', kategori: 'ravarer' })]);

    const rows = document.querySelectorAll('#cotGrid tbody tr');
    expect(rows.length).toBe(2);
  });

  it('shows market count badge', () => {
    render(container);
    update([makeRow(), makeRow({ symbol: 'GC', navn_no: 'Gull', kategori: 'ravarer' }), makeRow({ symbol: 'EC', navn_no: 'Euro FX', kategori: 'valuta' })]);

    const cnt = document.getElementById('cotCnt');
    expect(cnt.textContent).toBe('3 markeder');
  });

  it('displays the Norwegian name in the first column', () => {
    render(container);
    update([makeRow()]);

    const name = document.querySelector('.tdname');
    expect(name.textContent).toBe('S&P 500 mini');
  });

  it('displays "forklaring" as subtitle', () => {
    render(container);
    update([makeRow()]);

    const sub = document.querySelector('.tdsub');
    expect(sub.textContent).toBe('Aksjeindeks');
  });

  it('renders filter chips for categories present in data', () => {
    render(container);
    update([makeRow(), makeRow({ symbol: 'GC', kategori: 'ravarer' })]);

    const chips = document.querySelectorAll('#fchips .fc');
    const labels = Array.from(chips).map((c) => c.dataset.cat);
    expect(labels).toContain('alle');
    expect(labels).toContain('aksjer');
    expect(labels).toContain('ravarer');
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

    // Should not throw; grid stays as-is
    const grid = document.getElementById('cotGrid');
    expect(grid).not.toBeNull();
  });

  it('filters by category when a chip is clicked', () => {
    render(container);
    update([
      makeRow({ symbol: 'ES', kategori: 'aksjer', navn_no: 'S&P' }),
      makeRow({ symbol: 'GC', kategori: 'ravarer', navn_no: 'Gull' }),
    ]);

    // Click the 'ravarer' filter chip
    const chips = document.querySelectorAll('#fchips .fc');
    const ravarerChip = Array.from(chips).find((c) => c.dataset.cat === 'ravarer');
    expect(ravarerChip).not.toBeNull();
    ravarerChip.click();

    const rows = document.querySelectorAll('#cotGrid tbody tr');
    expect(rows.length).toBe(1);
    expect(document.querySelector('.tdname').textContent).toBe('Gull');
  });

  it('calls onOpenChart callback when a row is clicked', () => {
    render(container);

    let called = null;
    onOpenChart((sym, report, name) => {
      called = { sym, report, name };
    });

    // Reset filter to 'alle' by clicking the 'alle' chip, then update data
    update([makeRow()]);

    // The previous filter test may have set activeFilter to 'ravarer',
    // so click 'alle' chip to reset before asserting on row presence.
    const alleChip = Array.from(document.querySelectorAll('#fchips .fc')).find(
      (c) => c.dataset.cat === 'alle'
    );
    if (alleChip) alleChip.click();

    const row = document.querySelector('tr[data-sym]');
    expect(row).not.toBeNull();
    row.click();

    expect(called).not.toBeNull();
    expect(called.sym).toBe('ES');
    expect(called.report).toBe('Legacy');
  });
});
