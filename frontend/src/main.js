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

/* ── App shell ────────────────────────────────────────────── */

/** Build the static DOM skeleton */
function buildShell() {
  const app = document.getElementById('app');

  // TopBar (header + nav)
  TopBar.render(app);

  // Main content area with panel placeholders
  app.insertAdjacentHTML('beforeend', `
    <div class="main">
      <div class="panel active" id="panel-setups">
        <div class="loading"><div class="spinner"></div>Laster setups...</div>
      </div>
      <div class="panel" id="panel-macro">
        <div class="loading"><div class="spinner"></div>Laster makro...</div>
      </div>
      <div class="panel" id="panel-cot">
        <div class="loading"><div class="spinner"></div>Laster COT...</div>
      </div>
      <div class="panel" id="panel-calendar">
        <div class="loading"><div class="spinner"></div>Laster kalender...</div>
      </div>
      <div class="panel" id="panel-backtest">
        <div class="loading"><div class="spinner"></div>Laster backtest...</div>
      </div>
      <div class="panel" id="panel-pine">
        <div class="loading"><div class="spinner"></div>Laster Pine Scripts...</div>
      </div>
      <div class="panel" id="panel-competitor">
        <div class="loading"><div class="spinner"></div>Laster konkurrentanalyse...</div>
      </div>
    </div>
    <footer>
      <span>Kilde: <a href="https://cftc.gov" target="_blank">CFTC.gov</a> &middot; Yahoo Finance &middot; ForexFactory</span>
    </footer>
  `);
}

/** Initialize all component panels */
function initComponents() {
  // Setups panel — SetupGrid + ScoreRadar
  const setupsPanel = document.getElementById('panel-setups');
  SetupGrid.render(setupsPanel);

  // Add radar chart below the setup grid
  const radarWrap = document.createElement('div');
  radarWrap.id = 'radar-wrap';
  radarWrap.style.marginTop = '18px';
  setupsPanel.appendChild(radarWrap);
  ScoreRadar.render(radarWrap);

  // Macro panel
  const macroPanel = document.getElementById('panel-macro');
  MacroPanel.render(macroPanel);

  // COT panel
  const cotPanel = document.getElementById('panel-cot');
  CotTable.render(cotPanel);

  // COT Chart modal (appended to body)
  CotChart.render();

  // Wire CotTable row clicks to CotChart.open
  CotTable.onOpenChart((symbol, report, name) => {
    CotChart.open(symbol, report, name);
  });

  // Calendar panel
  const calPanel = document.getElementById('panel-calendar');
  CalendarPanel.render(calPanel);

  // Pine panel
  const pinePanel = document.getElementById('panel-pine');
  PinePanel.render(pinePanel);

  // Competitor panel
  const compPanel = document.getElementById('panel-competitor');
  CompetitorPanel.render(compPanel);
}

/* ── State subscriptions ──────────────────────────────────── */

function wireSubscriptions() {
  // TopBar tickers
  subscribe('instruments', (data) => {
    TopBar.updateTickers(data);
  });

  // Macro updates -> TopBar VIX + timestamp, MacroPanel, CalendarPanel
  subscribe('macro', (data) => {
    if (data?.vix_regime) TopBar.updateVix(data.vix_regime);
    if (data?.date) TopBar.updateTimestamp(data.date);
    MacroPanel.update(data);
    CalendarPanel.update(data);
  });

  // Signals -> SetupGrid
  subscribe('signals', (data) => {
    SetupGrid.update(data);
  });

  // COT data -> CotTable
  subscribe('cot', (data) => {
    CotTable.update(data);
  });

  // Health -> timestamp
  subscribe('health', (data) => {
    if (data?.timestamp) TopBar.updateTimestamp(data.timestamp);
  });

  // Selected instrument -> ScoreRadar
  subscribe('selectedInstrument', (data) => {
    ScoreRadar.update(data);
  });
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
