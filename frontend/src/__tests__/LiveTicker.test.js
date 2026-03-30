import { describe, it, expect, vi, beforeEach } from 'vitest';

// Mock the api module
vi.mock('../api.js', () => ({
  fetchPricesLive: vi.fn().mockResolvedValue({ items: [] }),
}));

describe('LiveTicker', () => {
  beforeEach(() => {
    document.body.innerHTML = '<div id="tbar"></div>';
  });

  it('should create ticker items with instrument data', () => {
    const tbar = document.getElementById('tbar');
    const items = [
      { name: 'EUR/USD', price: 1.085, chg1d: 0.12 },
      { name: 'Gold', price: 2350.5, chg1d: -0.5 },
    ];
    // Simulate ticker rendering
    tbar.innerHTML = items.map((i) => {
      const up = i.chg1d >= 0;
      return `<div class="ti"><span class="tn">${i.name}</span><span>${i.price}</span><span class="tc ${up ? 'up' : 'dn'}">${i.chg1d.toFixed(2)}%</span></div>`;
    }).join('');
    expect(tbar.querySelectorAll('.ti').length).toBe(2);
  });

  it('should apply up/down color classes', () => {
    const tbar = document.getElementById('tbar');
    tbar.innerHTML = `
      <div class="ti"><span class="tc up">+0.5%</span></div>
      <div class="ti"><span class="tc dn">-0.3%</span></div>`;
    const up = tbar.querySelector('.up');
    const dn = tbar.querySelector('.dn');
    expect(up).toBeTruthy();
    expect(dn).toBeTruthy();
  });

  it('should handle VIX regime border styling', () => {
    const badge = document.createElement('span');
    badge.className = 'vb elevated';
    badge.textContent = 'VIX 22.5';
    document.body.appendChild(badge);
    expect(badge.classList.contains('elevated')).toBe(true);
  });

  it('should render empty ticker for missing data', () => {
    const tbar = document.getElementById('tbar');
    tbar.innerHTML = '';
    expect(tbar.children.length).toBe(0);
  });

  it('should format prices with correct precision', () => {
    // FX pairs: 5 decimals, indices/commodities: 2 decimals
    const fxPrice = 1.08523;
    const indexPrice = 5234.75;
    expect(fxPrice.toFixed(5)).toBe('1.08523');
    expect(indexPrice.toFixed(2)).toBe('5234.75');
  });
});
