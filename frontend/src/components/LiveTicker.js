/**
 * LiveTicker component — sticky scrolling price bar at top of page.
 * Shows VIX, DXY, SPX, NAS100, EURUSD, USDJPY, Brent, Gold with 1d % change.
 */

import { escapeHtml, formatPct, formatPrice } from '../utils.js';
import { subscribe } from '../state.js';

/* ── Regime border styling ────────────────────────────────── */

const REGIME_BORDER = {
  NORMAL:       '',
  RISK_OFF:     'border-bottom:2px solid rgba(210,153,34,0.4)',
  CRISIS:       'border-bottom:2px solid rgba(248,81,73,0.5)',
  WAR_FOOTING:  'border-bottom:2px solid var(--bear);animation:regime-pulse 2s ease-in-out infinite',
  ENERGY_SHOCK: 'border-bottom:2px solid rgba(232,115,14,0.4)',
  SANCTIONS:    'border-bottom:2px solid rgba(163,113,247,0.4)',
};

function applyRegimeStyle(regime) {
  const bar = document.getElementById('live-ticker');
  if (!bar) return;
  const style = REGIME_BORDER[(regime && regime.name) || 'NORMAL'] || '';
  bar.style.cssText = style ? style.split(';').reduce((acc, rule) => {
    const [prop, val] = rule.split(':').map((s) => s.trim());
    if (prop && val) {
      const camel = prop.replace(/-([a-z])/g, (_, c) => c.toUpperCase());
      acc[camel] = val;
    }
    return acc;
  }, bar.style) && '' : '';
  // Simpler approach: set via setAttribute
  bar.setAttribute('style', style);
}

const TICKER_KEYS = [
  ['VIX', 'VIX'],
  ['DXY', 'DXY'],
  ['SPX', 'SPX'],
  ['NAS100', 'NAS100'],
  ['EUR/USD', 'EURUSD'],
  ['USD/JPY', 'USDJPY'],
  ['Brent', 'Brent'],
  ['Gull', 'Gold'],
];

/**
 * Render the LiveTicker bar and insert it at the top of the given container.
 * @param {HTMLElement} container  Typically #app
 */
export function render(container) {
  const bar = document.createElement('div');
  bar.id = 'live-ticker';
  bar.className = 'live-ticker';
  bar.setAttribute('role', 'marquee');
  bar.setAttribute('aria-label', 'Sanntids pristicker');
  bar.innerHTML = '<div class="live-ticker__inner" id="live-ticker-inner">Laster priser...</div>';
  container.insertAdjacentElement('afterbegin', bar);

  // Subscribe to instrument updates
  subscribe('instruments', (data) => update(data));

  // Subscribe to regime changes for border styling
  subscribe('regime', (regime) => applyRegimeStyle(regime));
}

/**
 * Update ticker with fresh instrument data.
 * @param {Object} instruments  Map of instrument key -> { price, chg1d, ... }
 */
export function update(instruments) {
  if (!instruments) return;
  const inner = document.getElementById('live-ticker-inner');
  if (!inner) return;

  inner.innerHTML = TICKER_KEYS.map(([label, key]) => {
    const d = instruments[key];
    if (!d) return '';
    const up = (d.chg1d || 0) >= 0;
    const cls = up ? 'live-ticker__chg--up' : 'live-ticker__chg--dn';
    return `<div class="live-ticker__item">
      <span class="live-ticker__label">${escapeHtml(label)}</span>
      <span class="live-ticker__price">${escapeHtml(formatPrice(d.price))}</span>
      <span class="live-ticker__chg ${cls}">${escapeHtml(formatPct(d.chg1d || 0))}</span>
    </div>`;
  }).join('');
}
