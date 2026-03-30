import { describe, it, expect, beforeEach } from 'vitest';
import { render, updateTickers, updateVix } from '../components/TopBar.js';

describe('TopBar', () => {
  let container;

  beforeEach(() => {
    document.body.innerHTML = '';
    container = document.createElement('div');
    container.id = 'app';
    document.body.appendChild(container);
  });

  it('should render the topbar with logo', () => {
    render(container);
    const logo = container.querySelector('.logo');
    expect(logo).toBeTruthy();
    expect(logo.textContent).toContain('Markeds');
  });

  it('should render all 14 tabs', () => {
    render(container);
    const tabs = container.querySelectorAll('.nt');
    expect(tabs.length).toBe(14);
  });

  it('should render ticker bar', () => {
    render(container);
    const tbar = container.querySelector('#tbar');
    expect(tbar).toBeTruthy();
  });

  it('should render VIX badge', () => {
    render(container);
    const badge = container.querySelector('#vbadge');
    expect(badge).toBeTruthy();
    expect(badge.textContent).toContain('VIX');
  });

  it('should render hamburger menu button', () => {
    render(container);
    const btn = container.querySelector('#hamburgerBtn');
    expect(btn).toBeTruthy();
    expect(btn.getAttribute('aria-label')).toContain('navigasjonsmeny');
  });

  it('should update tickers with instrument data', () => {
    render(container);
    updateTickers({ VIX: { price: '18.5', chg1d: -0.5 }, DXY: { price: '104.2', chg1d: 0.3 } });
    const tbar = container.querySelector('#tbar');
    expect(tbar.innerHTML).toContain('VIX');
    expect(tbar.innerHTML).toContain('DXY');
  });

  it('should handle null instruments gracefully', () => {
    render(container);
    updateTickers(null);
    // No error
  });

  it('should update VIX badge value and regime', () => {
    render(container);
    updateVix({ value: 22.5, regime: 'elevated', label: 'Elevated' });
    const badge = container.querySelector('#vbadge');
    expect(badge.textContent).toContain('22.5');
  });

  it('should include CHF and NOK in TICKER_ITEMS', () => {
    render(container);
    updateTickers({
      USDCHF: { price: '0.8850', chg1d: 0.1 },
      USDNOK: { price: '10.85', chg1d: -0.2 },
    });
    const tbar = container.querySelector('#tbar');
    expect(tbar.innerHTML).toContain('CHF');
    expect(tbar.innerHTML).toContain('NOK');
  });

  it('should have correct tab keys in order', () => {
    render(container);
    const tabs = Array.from(container.querySelectorAll('.nt'));
    expect(tabs[0].dataset.tab).toBe('setups');
    expect(tabs[1].dataset.tab).toBe('macro');
    expect(tabs[13].dataset.tab).toBe('krypto-intel');
  });

  it('should toggle mobile nav on hamburger click', () => {
    render(container);
    const hamburger = container.querySelector('#hamburgerBtn');
    const nav = container.querySelector('#main-nav');
    hamburger.click();
    expect(nav.classList.contains('mobile-open')).toBe(true);
    hamburger.click();
    expect(nav.classList.contains('mobile-open')).toBe(false);
  });
});
