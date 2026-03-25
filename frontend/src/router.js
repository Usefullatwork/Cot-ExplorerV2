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
];

const DEFAULT_TAB = 'setups';

/** Resolve current tab from window.location.hash */
function currentTab() {
  const hash = window.location.hash.replace('#', '');
  return TABS.includes(hash) ? hash : DEFAULT_TAB;
}

/**
 * Activate a tab: toggle .active on nav buttons and panels.
 * @param {string} tab
 */
function activateTab(tab) {
  // Nav buttons
  document.querySelectorAll('.nt').forEach((btn) => {
    btn.classList.toggle('active', btn.dataset.tab === tab);
  });

  // Panels
  document.querySelectorAll('.panel').forEach((p) => {
    p.classList.toggle('active', p.id === `panel-${tab}`);
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
