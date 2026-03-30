/* ── CSS imports ──────────────────────────────────────────── */
import './styles/variables.css';
import './styles/base.css';
import './styles/layout.css';
import './styles/topbar.css';
import './styles/cards.css';
import './styles/tables.css';
import './styles/charts.css';
import './styles/panels.css';
import './styles/utilities.css';

/* ── Module imports ───────────────────────────────────────── */
import {
  fetchSignals,
  fetchInstruments,
  fetchMacro,
  fetchCot,
  fetchCotSummary,
  fetchHealth,
  fetchMetrics,
} from './api.js';

import { state, subscribe, setState } from './state.js';
import { initRouter } from './router.js';

/* ── Component imports (static — first-load essentials) ──── */
import * as TopBar from './components/TopBar.js';
import * as SetupGrid from './components/SetupGrid.js';
import * as MacroPanel from './components/MacroPanel.js';
import * as CotTable from './components/CotTable.js';
import * as CotChart from './components/CotChart.js';
import * as CalendarPanel from './components/CalendarPanel.js';
import * as ScoreRadar from './components/ScoreRadar.js';
import * as PinePanel from './components/PinePanel.js';
import * as LiveTicker from './components/LiveTicker.js';

/* ── Lazy-loaded panels (loaded on first tab switch) ─────── */
const lazyPanels = {
  'backtest':      () => import('./components/BacktestDashboard.js'),
  'trading':       () => import('./components/BotPanel.js'),
  'competitor':    () => import('./components/CompetitorPanel.js'),
  'krypto-intel':  () => import('./components/CryptoPanel.js'),
  'geo-events':    () => import('./components/GeoEventsPanel.js'),
  'metals-intel':  () => import('./components/MetalsIntelPanel.js'),
  'correlations':  () => import('./components/CorrelationPanel.js'),
  'prices':        () => import('./components/PricesPanel.js'),
  'signal-log':    () => import('./components/SignalLogPanel.js'),
};

/** Loaded module cache — maps tab key to resolved module */
const loadedModules = {};

/**
 * Load a lazy panel module. Returns the cached module if already loaded.
 * @param {string} tab  Tab key
 * @returns {Promise<Object|null>}
 */
async function loadPanel(tab) {
  if (loadedModules[tab]) return loadedModules[tab];
  const loader = lazyPanels[tab];
  if (!loader) return null;
  const mod = await loader();
  loadedModules[tab] = mod;
  return mod;
}

/* ── Error boundary ──────────────────────────────────────── */

/**
 * Wrap a component function call in a try/catch to prevent one component
 * error from crashing the entire dashboard.
 * @param {string} name       Component name for logging
 * @param {Function} fn       The function to call
 * @param {HTMLElement} [el]  Optional element to show error in
 */
function safeCall(name, fn, el) {
  try {
    fn();
  } catch (err) {
    console.error(`[${name}] Render error:`, err);
    if (el) {
      el.innerHTML = `<div class="error-boundary">
        <div class="error-boundary-icon">\u26A0</div>
        <div class="error-boundary-title">Komponent-feil: ${name}</div>
        <div class="error-boundary-text">${err.message || 'Ukjent feil'}</div>
        <button class="fc error-boundary-retry" onclick="location.reload()">Last inn pa nytt</button>
      </div>`;
    }
  }
}

/**
 * Wrap an async function in error handling.
 * @param {string} name
 * @param {Function} fn
 */
function safeAsync(name, fn) {
  try {
    const result = fn();
    if (result && typeof result.catch === 'function') {
      result.catch((err) => console.error(`[${name}] Async error:`, err));
    }
  } catch (err) {
    console.error(`[${name}] Error:`, err);
  }
}

/* ── App shell ────────────────────────────────────────────── */

/** Build the static DOM skeleton */
function buildShell() {
  const app = document.getElementById('app');

  // LiveTicker (sticky price bar — rendered first, above everything)
  LiveTicker.render(app);

  // TopBar (header + nav)
  TopBar.render(app);

  // Main content area with panel placeholders
  app.insertAdjacentHTML('beforeend', `
    <main class="main" id="main-content" role="main" aria-label="Dashboard-innhold">
      <div class="panel active" id="panel-setups" role="tabpanel" aria-labelledby="tab-setups" aria-hidden="false">
        <div class="loading" role="status"><div class="spinner" aria-hidden="true"></div>Laster setups...</div>
      </div>
      <div class="panel" id="panel-macro" role="tabpanel" aria-labelledby="tab-macro" aria-hidden="true">
        <div class="loading" role="status"><div class="spinner" aria-hidden="true"></div>Laster makro...</div>
      </div>
      <div class="panel" id="panel-cot" role="tabpanel" aria-labelledby="tab-cot" aria-hidden="true">
        <div class="loading" role="status"><div class="spinner" aria-hidden="true"></div>Laster COT...</div>
      </div>
      <div class="panel" id="panel-calendar" role="tabpanel" aria-labelledby="tab-calendar" aria-hidden="true">
        <div class="loading" role="status"><div class="spinner" aria-hidden="true"></div>Laster kalender...</div>
      </div>
      <div class="panel" id="panel-backtest" role="tabpanel" aria-labelledby="tab-backtest" aria-hidden="true">
        <div class="loading" role="status"><div class="spinner" aria-hidden="true"></div>Laster backtest...</div>
      </div>
      <div class="panel" id="panel-pine" role="tabpanel" aria-labelledby="tab-pine" aria-hidden="true">
        <div class="loading" role="status"><div class="spinner" aria-hidden="true"></div>Laster Pine Scripts...</div>
      </div>
      <div class="panel" id="panel-competitor" role="tabpanel" aria-labelledby="tab-competitor" aria-hidden="true">
        <div class="loading" role="status"><div class="spinner" aria-hidden="true"></div>Laster konkurrentanalyse...</div>
      </div>
      <div class="panel" id="panel-trading" role="tabpanel" aria-labelledby="tab-trading" aria-hidden="true">
        <div class="loading" role="status"><div class="spinner" aria-hidden="true"></div>Laster trading bot...</div>
      </div>
      <div class="panel" id="panel-metals-intel" role="tabpanel" aria-labelledby="tab-metals-intel" aria-hidden="true">
        <div class="loading" role="status"><div class="spinner" aria-hidden="true"></div>Laster metals intel...</div>
      </div>
      <div class="panel" id="panel-correlations" role="tabpanel" aria-labelledby="tab-correlations" aria-hidden="true">
        <div class="loading" role="status"><div class="spinner" aria-hidden="true"></div>Laster korrelasjoner...</div>
      </div>
      <div class="panel" id="panel-signal-log" role="tabpanel" aria-labelledby="tab-signal-log" aria-hidden="true">
        <div class="loading" role="status"><div class="spinner" aria-hidden="true"></div>Laster signal-logg...</div>
      </div>
      <div class="panel" id="panel-geo-events" role="tabpanel" aria-labelledby="tab-geo-events" aria-hidden="true">
        <div class="loading" role="status"><div class="spinner" aria-hidden="true"></div>Laster geo-signaler...</div>
      </div>
      <div class="panel" id="panel-prices" role="tabpanel" aria-labelledby="tab-prices" aria-hidden="true">
        <div class="loading" role="status"><div class="spinner" aria-hidden="true"></div>Laster priser...</div>
      </div>
      <div class="panel" id="panel-krypto-intel" role="tabpanel" aria-labelledby="tab-krypto-intel" aria-hidden="true">
        <div class="loading" role="status"><div class="spinner" aria-hidden="true"></div>Laster krypto...</div>
      </div>
    </main>
    <footer role="contentinfo">
      <span>Kilde: <a href="https://cftc.gov" target="_blank" rel="noopener noreferrer">CFTC.gov</a> &middot; Yahoo Finance &middot; ForexFactory</span>
    </footer>
  `);
}

/** Initialize all component panels with error boundaries */
function initComponents() {
  // Setups panel — SetupGrid + ScoreRadar
  const setupsPanel = document.getElementById('panel-setups');
  safeCall('SetupGrid', () => {
    SetupGrid.render(setupsPanel);

    // Add radar chart below the setup grid
    const radarWrap = document.createElement('div');
    radarWrap.id = 'radar-wrap';
    radarWrap.style.marginTop = '18px';
    setupsPanel.appendChild(radarWrap);
    ScoreRadar.render(radarWrap);
  }, setupsPanel);

  // Macro panel
  const macroPanel = document.getElementById('panel-macro');
  safeCall('MacroPanel', () => MacroPanel.render(macroPanel), macroPanel);

  // COT panel
  const cotPanel = document.getElementById('panel-cot');
  safeCall('CotTable', () => {
    CotTable.render(cotPanel);

    // COT Chart modal (appended to body)
    CotChart.render();

    // Wire CotTable row clicks to CotChart.open
    CotTable.onOpenChart((symbol, report, name) => {
      CotChart.open(symbol, report, name);
    });
  }, cotPanel);

  // Calendar panel
  const calPanel = document.getElementById('panel-calendar');
  safeCall('CalendarPanel', () => CalendarPanel.render(calPanel), calPanel);

  // Pine panel (static — lightweight, no lazy benefit)
  const pinePanel = document.getElementById('panel-pine');
  safeCall('PinePanel', () => PinePanel.render(pinePanel), pinePanel);

  // Lazy panels are rendered on first tab switch — spinner skeleton shows until then
}

/* ── State subscriptions ──────────────────────────────────── */

function wireSubscriptions() {
  // TopBar tickers
  subscribe('instruments', (data) => {
    safeCall('TopBar.updateTickers', () => TopBar.updateTickers(data));
  });

  // Macro updates -> TopBar VIX + timestamp, MacroPanel, CalendarPanel
  subscribe('macro', (data) => {
    safeCall('TopBar.updateVix', () => {
      if (data?.vix_regime) TopBar.updateVix(data.vix_regime);
      if (data?.date) TopBar.updateTimestamp(data.date);
    });
    safeCall('MacroPanel.update', () => MacroPanel.update(data), document.getElementById('panel-macro'));
    safeCall('CalendarPanel.update', () => CalendarPanel.update(data), document.getElementById('panel-calendar'));
  });

  // Macro -> SetupGrid (needs trading_levels, vix_regime, cot_date from macro payload)
  subscribe('macro', (data) => {
    safeCall('SetupGrid.update', () => SetupGrid.update(data), document.getElementById('panel-setups'));
  });

  // COT data -> CotTable
  subscribe('cot', (data) => {
    safeCall('CotTable.update', () => CotTable.update(data), document.getElementById('panel-cot'));
  });

  // Health -> timestamp
  subscribe('health', (data) => {
    safeCall('TopBar.updateTimestamp', () => {
      if (data?.timestamp) TopBar.updateTimestamp(data.timestamp);
    });
  });

  // Selected instrument -> ScoreRadar
  subscribe('selectedInstrument', (data) => {
    safeCall('ScoreRadar.update', () => ScoreRadar.update(data));
  });

  // Tab switch -> lazy load panel on first visit, then refresh/cleanup
  subscribe('activeTab', async (tab) => {
    // Lazy-load panel if not yet loaded
    if (lazyPanels[tab] && !loadedModules[tab]) {
      const mod = await loadPanel(tab);
      if (mod) {
        const el = document.getElementById(`panel-${tab}`);
        safeCall(tab, () => mod.render(el), el);
      }
    }

    const m = loadedModules;
    if (tab === 'trading') {
      if (m['trading']) safeAsync('BotPanel.refreshAll', () => m['trading'].refreshAll());
    } else {
      if (m['trading']) safeCall('BotPanel.cleanup', () => m['trading'].cleanup());
    }
    if (tab === 'metals-intel') {
      if (m['metals-intel']) safeAsync('MetalsIntelPanel.refreshAll', () => m['metals-intel'].refreshAll());
    }
    if (tab === 'correlations') {
      if (m['correlations']) safeAsync('CorrelationPanel.refreshAll', () => m['correlations'].refreshAll());
    }
    if (tab === 'backtest') {
      if (m['backtest']) safeAsync('BacktestDashboard.refreshAll', () => m['backtest'].refreshAll());
    }
    if (tab === 'signal-log') {
      if (m['signal-log']) safeAsync('SignalLogPanel.refreshAll', () => m['signal-log'].refreshAll());
    }
    if (tab === 'geo-events') {
      if (m['geo-events']) safeAsync('GeoEventsPanel.refreshAll', () => m['geo-events'].refreshAll());
    } else {
      if (m['geo-events']) safeCall('GeoEventsPanel.cleanup', () => m['geo-events'].cleanup());
    }
    if (tab === 'prices') {
      if (m['prices']) safeAsync('PricesPanel.refreshAll', () => m['prices'].refreshAll());
    } else {
      if (m['prices']) safeCall('PricesPanel.stopPolling', () => m['prices'].stopPolling());
    }
    if (tab === 'krypto-intel') {
      if (m['krypto-intel']) safeAsync('CryptoPanel.refreshAll', () => m['krypto-intel'].refreshAll());
    } else {
      if (m['krypto-intel']) safeCall('CryptoPanel.stopPolling', () => m['krypto-intel'].stopPolling());
    }
  });

  // Geointel -> MetalsIntelPanel (lazy — only update if loaded)
  subscribe('geointel', (data) => {
    const mod = loadedModules['metals-intel'];
    if (mod) safeCall('MetalsIntelPanel.update', () => mod.update(data), document.getElementById('panel-metals-intel'));
  });

  // Correlations -> CorrelationPanel (lazy)
  subscribe('correlations', (data) => {
    const mod = loadedModules['correlations'];
    if (mod) safeCall('CorrelationPanel.update', () => mod.update(data), document.getElementById('panel-correlations'));
  });

  // Signal Log -> SignalLogPanel (lazy)
  subscribe('signalLog', (data) => {
    const mod = loadedModules['signal-log'];
    if (mod) safeCall('SignalLogPanel.update', () => mod.update(data), document.getElementById('panel-signal-log'));
  });

  // Geo-events data -> GeoEventsPanel (lazy)
  const geoUpdateFn = () => {
    const mod = loadedModules['geo-events'];
    if (!mod) return;
    const { regime, geoSignals, geoEvents } = state;
    safeCall('GeoEventsPanel.update', () => mod.update({ regime, geoSignals, geoEvents }), document.getElementById('panel-geo-events'));
  };
  subscribe('regime', geoUpdateFn);
  subscribe('geoSignals', geoUpdateFn);
  subscribe('geoEvents', geoUpdateFn);
}

/* ── Data fetching ────────────────────────────────────────── */

/** Fetch all data sources in parallel. Errors are caught individually. */
async function fetchAll() {
  const safe = (fn, key) =>
    fn()
      .then((d) => setState(key, d))
      .catch((e) => console.warn(`[${key}]`, e.message));

  await Promise.allSettled([
    safe(fetchInstruments, 'instruments'),
    safe(fetchSignals,     'signals'),
    safe(fetchMacro,       'macro'),
    safe(fetchCot,         'cot'),
    safe(fetchCotSummary,  'cotSummary'),
    safe(fetchHealth,      'health'),
    safe(fetchMetrics,     'metrics'),
  ]);
}

/** Periodic polling — health every 60 s, full data every 300 s */
function startPolling() {
  setInterval(() => {
    fetchHealth()
      .then((d) => setState('health', d))
      .catch(() => {});
  }, 60_000);

  setInterval(() => {
    fetchAll();
  }, 300_000);

  // Bot status polling — every 10s when trading tab is active
  setInterval(() => {
    const mod = loadedModules['trading'];
    if (state.activeTab === 'trading' && mod) {
      safeAsync('BotPanel.refresh', () => mod.refreshAll());
    }
  }, 10_000);
}

/* ── Bootstrap ────────────────────────────────────────────── */

document.addEventListener('DOMContentLoaded', () => {
  buildShell();
  initComponents();

  const nav = document.getElementById('main-nav');
  initRouter(nav);

  wireSubscriptions();
  fetchAll();
  startPolling();
});
