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

/* ── Component imports ───────────────────────────────────── */
import * as TopBar from './components/TopBar.js';
import * as SetupGrid from './components/SetupGrid.js';
import * as MacroPanel from './components/MacroPanel.js';
import * as CotTable from './components/CotTable.js';
import * as CotChart from './components/CotChart.js';
import * as CalendarPanel from './components/CalendarPanel.js';
import * as ScoreRadar from './components/ScoreRadar.js';
import * as PinePanel from './components/PinePanel.js';
import * as CompetitorPanel from './components/CompetitorPanel.js';
import * as BotPanel from './components/BotPanel.js';
import * as LiveTicker from './components/LiveTicker.js';
import * as MetalsIntelPanel from './components/MetalsIntelPanel.js';
import * as CorrelationPanel from './components/CorrelationPanel.js';
import * as SignalLogPanel from './components/SignalLogPanel.js';
import * as GeoEventsPanel from './components/GeoEventsPanel.js';
import * as PricesPanel from './components/PricesPanel.js';
import * as BacktestDashboard from './components/BacktestDashboard.js';
import * as CryptoPanel from './components/CryptoPanel.js';

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

  // Backtest dashboard
  const backtestPanel = document.getElementById('panel-backtest');
  safeCall('BacktestDashboard', () => BacktestDashboard.render(backtestPanel), backtestPanel);

  // Pine panel
  const pinePanel = document.getElementById('panel-pine');
  safeCall('PinePanel', () => PinePanel.render(pinePanel), pinePanel);

  // Competitor panel
  const compPanel = document.getElementById('panel-competitor');
  safeCall('CompetitorPanel', () => CompetitorPanel.render(compPanel), compPanel);

  // Trading bot panel
  const tradingPanel = document.getElementById('panel-trading');
  safeCall('BotPanel', () => BotPanel.render(tradingPanel), tradingPanel);

  // Metals Intel panel
  const miPanel = document.getElementById('panel-metals-intel');
  safeCall('MetalsIntelPanel', () => MetalsIntelPanel.render(miPanel), miPanel);

  // Correlation panel
  const corrPanel = document.getElementById('panel-correlations');
  safeCall('CorrelationPanel', () => CorrelationPanel.render(corrPanel), corrPanel);

  // Signal Log panel
  const slPanel = document.getElementById('panel-signal-log');
  safeCall('SignalLogPanel', () => SignalLogPanel.render(slPanel), slPanel);

  // Geo Events panel
  const geoPanel = document.getElementById('panel-geo-events');
  safeCall('GeoEventsPanel', () => GeoEventsPanel.render(geoPanel), geoPanel);

  // Prices panel
  const pricesPanel = document.getElementById('panel-prices');
  safeCall('PricesPanel', () => PricesPanel.render(pricesPanel), pricesPanel);

  // Krypto Intel panel
  const kryptoPanel = document.getElementById('panel-krypto-intel');
  safeCall('CryptoPanel', () => CryptoPanel.render(kryptoPanel), kryptoPanel);
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

  // Trading tab -> BotPanel: fetch data when tab becomes active
  subscribe('activeTab', (tab) => {
    if (tab === 'trading') {
      safeAsync('BotPanel.refreshAll', () => BotPanel.refreshAll());
    } else {
      // Clean up charts when leaving trading tab
      safeCall('BotPanel.cleanup', () => BotPanel.cleanup());
    }
    if (tab === 'metals-intel') {
      safeAsync('MetalsIntelPanel.refreshAll', () => MetalsIntelPanel.refreshAll());
    }
    if (tab === 'correlations') {
      safeAsync('CorrelationPanel.refreshAll', () => CorrelationPanel.refreshAll());
    }
    if (tab === 'backtest') {
      safeAsync('BacktestDashboard.refreshAll', () => BacktestDashboard.refreshAll());
    }
    if (tab === 'signal-log') {
      safeAsync('SignalLogPanel.refreshAll', () => SignalLogPanel.refreshAll());
    }
    if (tab === 'geo-events') {
      safeAsync('GeoEventsPanel.refreshAll', () => GeoEventsPanel.refreshAll());
    } else {
      safeCall('GeoEventsPanel.cleanup', () => GeoEventsPanel.cleanup());
    }
    if (tab === 'prices') {
      safeAsync('PricesPanel.refreshAll', () => PricesPanel.refreshAll());
    } else {
      safeCall('PricesPanel.stopPolling', () => PricesPanel.stopPolling());
    }
    if (tab === 'krypto-intel') {
      safeAsync('CryptoPanel.refreshAll', () => CryptoPanel.refreshAll());
    } else {
      safeCall('CryptoPanel.stopPolling', () => CryptoPanel.stopPolling());
    }
  });

  // Geointel -> MetalsIntelPanel
  subscribe('geointel', (data) => {
    safeCall('MetalsIntelPanel.update', () => MetalsIntelPanel.update(data), document.getElementById('panel-metals-intel'));
  });

  // Correlations -> CorrelationPanel
  subscribe('correlations', (data) => {
    safeCall('CorrelationPanel.update', () => CorrelationPanel.update(data), document.getElementById('panel-correlations'));
  });

  // Signal Log -> SignalLogPanel
  subscribe('signalLog', (data) => {
    safeCall('SignalLogPanel.update', () => SignalLogPanel.update(data), document.getElementById('panel-signal-log'));
  });

  // Geo-events data -> GeoEventsPanel
  const geoUpdateFn = () => {
    const { regime, geoSignals, geoEvents } = state;
    safeCall('GeoEventsPanel.update', () => GeoEventsPanel.update({ regime, geoSignals, geoEvents }), document.getElementById('panel-geo-events'));
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
    if (state.activeTab === 'trading') {
      safeAsync('BotPanel.refresh', () => BotPanel.refreshAll());
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
