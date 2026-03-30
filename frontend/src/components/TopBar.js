/**
 * TopBar component — logo, instrument tickers, VIX badge, nav tabs, last update.
 *
 * Renders into the provided container.  Call render() once to build the DOM,
 * then call update() when state.instruments or state.health changes.
 */

import { formatPct, escapeHtml } from '../utils.js';

// ── Tab definitions ─────────────────────────────────────────
const TABS = [
  { key: 'setups',     label: 'Setups' },
  { key: 'macro',      label: 'Makro' },
  { key: 'cot',        label: 'COT' },
  { key: 'calendar',   label: 'Kalender' },
  { key: 'backtest',   label: 'Backtest' },
  { key: 'pine',       label: 'Pine' },
  { key: 'competitor', label: 'Konkurrent' },
  { key: 'trading',    label: 'Trading' },
  { key: 'metals-intel', label: '\u26CF Metals Intel' },
  { key: 'correlations', label: '\uD83D\uDD17 Korrelasjoner' },
  { key: 'signal-log',   label: '\uD83D\uDCCB Signal-logg' },
  { key: 'geo-events',   label: '\uD83C\uDF0D Geo-Signaler' },
  { key: 'prices',       label: '\uD83D\uDCB0 Priser' },
  { key: 'krypto-intel', label: '\u20BF Krypto' },
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
  ['Sølv',    'Silver'],
  ['WTI',     'WTI'],
  ['CHF',     'USDCHF'],
  ['NOK',     'USDNOK'],
];

/**
 * Build the initial TopBar DOM inside `container`.
 * @param {HTMLElement} container  Typically `document.getElementById('app')` or a wrapper
 */
export function render(container) {
  const html = `
    <a href="#main-content" class="skip-link">Hopp til hovedinnhold</a>
    <header class="topbar" role="banner">
      <div class="logo" aria-label="Markedspuls dashboard">Markeds<em>puls</em></div>
      <div class="tbar" id="tbar" role="marquee" aria-label="Instrumentticker"></div>
      <div class="topbar-r">
        <span class="vb" id="vbadge" role="status" aria-live="polite" aria-label="VIX verdi">VIX -</span>
        <span class="upd" id="upd" role="status" aria-live="polite">-</span>
        <button class="hamburger" id="hamburgerBtn" aria-label="Åpne navigasjonsmeny" aria-expanded="false" aria-controls="main-nav">
          <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M3 6h18v2H3V6zm0 5h18v2H3v-2zm0 5h18v2H3v-2z"/></svg>
        </button>
      </div>
    </header>
    <nav class="nav" id="main-nav" role="tablist" aria-label="Hovednavigasjon">
      ${TABS.map((t, i) => `<button class="nt" data-tab="${t.key}" role="tab" aria-selected="${i === 0 ? 'true' : 'false'}" aria-controls="panel-${t.key}" id="tab-${t.key}" tabindex="${i === 0 ? '0' : '-1'}">${t.label}</button>`).join('')}
    </nav>
  `;

  // Prepend topbar + nav before any existing children
  container.insertAdjacentHTML('afterbegin', html);

  // Hamburger toggle
  const hamburger = document.getElementById('hamburgerBtn');
  const nav = document.getElementById('main-nav');
  if (hamburger && nav) {
    hamburger.addEventListener('click', () => {
      const isOpen = nav.classList.toggle('mobile-open');
      hamburger.setAttribute('aria-expanded', String(isOpen));
      hamburger.setAttribute('aria-label', isOpen ? 'Lukk navigasjonsmeny' : 'Åpne navigasjonsmeny');
    });

    // Close mobile nav when a tab is clicked
    nav.addEventListener('click', (e) => {
      if (e.target.closest('.nt')) {
        nav.classList.remove('mobile-open');
        hamburger.setAttribute('aria-expanded', 'false');
        hamburger.setAttribute('aria-label', 'Åpne navigasjonsmeny');
      }
    });

    // Keyboard navigation for tabs (arrow keys)
    nav.addEventListener('keydown', (e) => {
      const tabs = Array.from(nav.querySelectorAll('.nt'));
      const current = tabs.indexOf(e.target);
      if (current === -1) return;

      let next = -1;
      if (e.key === 'ArrowRight' || e.key === 'ArrowDown') {
        next = (current + 1) % tabs.length;
      } else if (e.key === 'ArrowLeft' || e.key === 'ArrowUp') {
        next = (current - 1 + tabs.length) % tabs.length;
      } else if (e.key === 'Home') {
        next = 0;
      } else if (e.key === 'End') {
        next = tabs.length - 1;
      }

      if (next >= 0) {
        e.preventDefault();
        tabs[current].setAttribute('tabindex', '-1');
        tabs[next].setAttribute('tabindex', '0');
        tabs[next].focus();
      }
    });
  }
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
      <span>${escapeHtml(String(d.price))}</span>
      <span class="tc ${up ? 'up' : 'dn'}">${escapeHtml(formatPct(d.chg1d))}</span>
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
    const val = (vixRegime.value || 0).toFixed(1);
    badge.textContent = `VIX ${val}`;
    badge.className = `vb ${vixRegime.regime || 'normal'}`;
    badge.setAttribute('aria-label', `VIX verdi ${val}, regime ${vixRegime.label || vixRegime.regime || 'normal'}`);
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
