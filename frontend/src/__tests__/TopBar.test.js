import { describe, it, expect, beforeEach } from 'vitest';
import { render, updateTickers, updateVix, updateTimestamp } from '../components/TopBar.js';

describe('TopBar', () => {
  let container;

  beforeEach(() => {
    document.body.innerHTML = '';
    container = document.createElement('div');
    container.id = 'app';
    document.body.appendChild(container);
  });

  it('renders the header and nav into the container', () => {
    render(container);

    const header = container.querySelector('header.topbar');
    expect(header).not.toBeNull();

    const nav = container.querySelector('nav.nav');
    expect(nav).not.toBeNull();
  });

  it('shows the logo text "Markedspuls"', () => {
    render(container);

    const logo = container.querySelector('.logo');
    expect(logo).not.toBeNull();
    expect(logo.textContent).toContain('Markeds');
    expect(logo.textContent).toContain('puls');
  });

  it('renders all 7 navigation tabs', () => {
    render(container);

    const tabs = container.querySelectorAll('.nt');
    expect(tabs.length).toBe(7);

    const labels = Array.from(tabs).map((t) => t.textContent);
    expect(labels).toContain('Setups');
    expect(labels).toContain('Makro');
    expect(labels).toContain('COT');
    expect(labels).toContain('Kalender');
    expect(labels).toContain('Backtest');
    expect(labels).toContain('Pine');
    expect(labels).toContain('Konkurrent');
  });

  it('renders ticker bar container', () => {
    render(container);

    const tbar = document.getElementById('tbar');
    expect(tbar).not.toBeNull();
  });

  it('renders VIX badge with default text', () => {
    render(container);

    const vbadge = document.getElementById('vbadge');
    expect(vbadge).not.toBeNull();
    expect(vbadge.textContent).toBe('VIX -');
  });

  describe('updateTickers', () => {
    it('populates ticker items from instrument data', () => {
      render(container);

      updateTickers({
        VIX: { price: 15.2, chg1d: -0.5 },
        EURUSD: { price: 1.085, chg1d: 0.12 },
      });

      const tbar = document.getElementById('tbar');
      const items = tbar.querySelectorAll('.ti');
      expect(items.length).toBeGreaterThanOrEqual(2);
    });

    it('does nothing when instruments is null', () => {
      render(container);
      updateTickers(null);

      const tbar = document.getElementById('tbar');
      expect(tbar.innerHTML).toBe('');
    });
  });

  describe('updateVix', () => {
    it('updates VIX badge text and class', () => {
      render(container);

      updateVix({ value: 22.5, regime: 'elevated' });

      const badge = document.getElementById('vbadge');
      expect(badge.textContent).toBe('VIX 22.5');
      expect(badge.className).toBe('vb elevated');
    });

    it('does nothing when vixRegime is null', () => {
      render(container);
      updateVix(null);

      const badge = document.getElementById('vbadge');
      expect(badge.textContent).toBe('VIX -');
    });
  });

  describe('updateTimestamp', () => {
    it('sets the update label', () => {
      render(container);

      updateTimestamp('2026-03-25 14:00');

      const upd = document.getElementById('upd');
      expect(upd.textContent).toBe('Oppdatert: 2026-03-25 14:00');
    });

    it('shows dash when dateStr is empty', () => {
      render(container);

      updateTimestamp('');

      const upd = document.getElementById('upd');
      expect(upd.textContent).toBe('-');
    });
  });
});
