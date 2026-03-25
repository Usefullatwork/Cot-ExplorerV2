/**
 * TopBar component — logo, instrument tickers, VIX badge, nav tabs, last update.
 *
 * Renders into the provided container.  Call render() once to build the DOM,
 * then call update() when state.instruments or state.health changes.
 */

import { formatPct } from '../utils.js';

// ── Tab definitions ─────────────────────────────────────────
const TABS = [
  { key: 'setups',     label: 'Setups' },
  { key: 'macro',      label: 'Makro' },
  { key: 'cot',        label: 'COT' },
  { key: 'calendar',   label: 'Kalender' },
  { key: 'backtest',   label: 'Backtest' },
  { key: 'pine',       label: 'Pine' },
  { key: 'competitor', label: 'Konkurrent' },
];

// ── Ticker display names ────────────────────────────────────
const TICKER_ITEMS = [
  ['VIX',     'VIX'],
  ['DXY',     'DXY'],
  ['S&P',     'SPX'],
  ['NAS',     'NAS100'],
  ['EUR/USD', 'EURUSD'],
  ['USD/JPY', 'USDJPY'],
  ['GBP/USD', 'GBPUSD'],
  ['AUD/USD', 'AUDUSD'],
  ['Brent',   'Brent'],
  ['Gull',    'Gold'],
  ['Solv',    'Silver'],
  ['WTI',     'WTI'],
];

/**
 * Build the initial TopBar DOM inside `container`.
 * @param {HTMLElement} container  Typically `document.getElementById('app')` or a wrapper
 */
export function render(container) {
  const html = `
    <header class="topbar">
      <div class="logo">Markeds<em>puls</em></div>
      <div class="tbar" id="tbar"></div>
      <div class="topbar-r">
        <span class="vb" id="vbadge">VIX -</span>
        <span class="upd" id="upd">-</span>
      </div>
    </header>
    <nav class="nav" id="main-nav">
      ${TABS.map((t) => `<button class="nt" data-tab="${t.key}">${t.label}</button>`).join('')}
    </nav>
  `;

  // Prepend topbar + nav before any existing children
  container.insertAdjacentHTML('afterbegin', html);
}

/**
 * Update tickers and VIX badge with fresh instrument data.
 * @param {Object} instruments  Map of instrument key → { price, chg1d, … }
 */
export function updateTickers(instruments) {
  if (!instruments) return;

  const tbar = document.getElementById('tbar');
  if (!tbar) return;

  tbar.innerHTML = TICKER_ITEMS.map(([label, key]) => {
    const d = instruments[key];
    if (!d) return '';
    const up = d.chg1d >= 0;
    return `<div class="ti">
      <span class="tn">${label}</span>
      <span>${d.price}</span>
      <span class="tc ${up ? 'up' : 'dn'}">${formatPct(d.chg1d)}</span>
    </div>`;
  }).join('');
}

/**
 * Update VIX badge color/value.
 * @param {Object} vixRegime  { value, regime, label, color }
 */
export function updateVix(vixRegime) {
  if (!vixRegime) return;

  const badge = document.getElementById('vbadge');
  if (badge) {
    badge.textContent = `VIX ${(vixRegime.value || 0).toFixed(1)}`;
    badge.className = `vb ${vixRegime.regime || 'normal'}`;
  }
}

/**
 * Update the "last updated" label.
 * @param {string} dateStr  Human-readable date string
 */
export function updateTimestamp(dateStr) {
  const el = document.getElementById('upd');
  if (el) el.textContent = dateStr ? `Oppdatert: ${dateStr}` : '-';
}
