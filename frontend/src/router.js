/**
 * Hash-based router.
 *
 * Maps hash fragments to panel IDs:
 *   #setups  → panel-setups   (default)
 *   #macro   → panel-macro
 *   #cot     → panel-cot
 *   etc.
 */

import { setState } from './state.js';

const TABS = [
  'setups',
  'macro',
  'cot',
  'calendar',
  'backtest',
  'pine',
  'competitor',
  'trading',
  'metals-intel',
  'correlations',
  'signal-log',
  'geo-events',
  'prices',
  'krypto-intel',
  'signal-health',
  'risk',
  'intelligence',
  'attribution',
  'pipeline',
];

const DEFAULT_TAB = 'setups';

/** Resolve current tab from window.location.hash */
function currentTab() {
  const hash = window.location.hash.replace('#', '');
  return TABS.includes(hash) ? hash : DEFAULT_TAB;
}

/**
 * Activate a tab: toggle .active on nav buttons and panels, sync ARIA state.
 * @param {string} tab
 */
function activateTab(tab) {
  // Nav buttons — sync ARIA selected + tabindex
  document.querySelectorAll('.nt').forEach((btn) => {
    const isActive = btn.dataset.tab === tab;
    btn.classList.toggle('active', isActive);
    btn.setAttribute('aria-selected', String(isActive));
    btn.setAttribute('tabindex', isActive ? '0' : '-1');
  });

  // Panels — sync ARIA role + hidden
  document.querySelectorAll('.panel').forEach((p) => {
    const isActive = p.id === `panel-${tab}`;
    p.classList.toggle('active', isActive);
    p.setAttribute('role', 'tabpanel');
    p.setAttribute('aria-hidden', String(!isActive));
    if (isActive) {
      p.setAttribute('aria-labelledby', `tab-${tab}`);
    }
  });

  setState('activeTab', tab);
}

/**
 * Initialise the router.  Wires up nav clicks and hashchange events.
 * @param {HTMLElement} navContainer  The <nav> element containing .nt buttons
 */
export function initRouter(navContainer) {
  // Click handlers on nav buttons
  navContainer.querySelectorAll('.nt').forEach((btn) => {
    btn.addEventListener('click', () => {
      window.location.hash = btn.dataset.tab;
    });
  });

  // React to hash changes (back/forward navigation)
  window.addEventListener('hashchange', () => {
    activateTab(currentTab());
  });

  // Initial activation
  activateTab(currentTab());
}
