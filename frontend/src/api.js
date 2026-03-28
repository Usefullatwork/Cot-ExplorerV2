/**
 * API client — one function per backend endpoint.
 *
 * Base URL defaults to '' (same origin via Vite proxy in dev, or relative
 * path in production).  Override by setting window.__API_BASE.
 */

const base = () => window.__API_BASE ?? '';

/**
 * Thin fetch wrapper with JSON parsing and error normalisation.
 */
async function post(path, body = {}) {
  const url = new URL(path, base() || window.location.origin);
  const res = await fetch(url.toString(), {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });
  if (!res.ok) {
    const text = await res.text().catch(() => '');
    throw new Error(`API ${res.status}: ${text || res.statusText}`);
  }
  return res.json();
}

async function get(path, params = {}) {
  const url = new URL(path, base() || window.location.origin);
  Object.entries(params).forEach(([k, v]) => {
    if (v !== undefined && v !== null) url.searchParams.set(k, v);
  });

  const res = await fetch(url.toString());
  if (!res.ok) {
    const text = await res.text().catch(() => '');
    throw new Error(`API ${res.status}: ${text || res.statusText}`);
  }
  return res.json();
}

// ── Signals ─────────────────────────────────────────────────

/**
 * @param {Object} [filters] - Optional query params (grade, bias, etc.)
 */
export function fetchSignals(filters = {}) {
  return get('/api/v1/signals', filters);
}

export function fetchSignal(key) {
  return get(`/api/v1/signals/${encodeURIComponent(key)}`);
}

// ── Instruments ─────────────────────────────────────────────

export function fetchInstruments() {
  return get('/api/v1/instruments');
}

export function fetchInstrument(key) {
  return get(`/api/v1/instruments/${encodeURIComponent(key)}`);
}

// ── COT ─────────────────────────────────────────────────────

export function fetchCot() {
  return get('/api/v1/cot');
}

/**
 * @param {string} symbol
 * @param {string} [start]  ISO date
 * @param {string} [end]    ISO date
 * @param {string} [reportType]
 */
export function fetchCotHistory(symbol, start, end, reportType) {
  return get(`/api/v1/cot/${encodeURIComponent(symbol)}/history`, {
    start,
    end,
    report_type: reportType,
  });
}

export function fetchCotSummary() {
  return get('/api/v1/cot/summary');
}

// ── Macro ───────────────────────────────────────────────────

export function fetchMacro() {
  return get('/api/v1/macro');
}

export function fetchMacroIndicators() {
  return get('/api/v1/macro/indicators');
}

export function fetchVixTerm() {
  return get('/api/v1/macro/vix-term');
}

export function fetchADR() {
  return get('/api/v1/macro/adr');
}

// ── Prices ─────────────────────────────────────────────────

export function fetchPricesLive() {
  return get('/api/v1/prices/live');
}

// ── Backtests ──────────────────────────────────────────────

export function fetchBacktestStats() {
  return get('/api/v1/backtests/stats');
}

// ── Regime History ─────────────────────────────────────────

export function fetchRegimeHistory(days = 30) {
  return get('/api/v1/macro/regime-history', { days });
}

// ── Health / Metrics ────────────────────────────────────────

export function fetchHealth() {
  return get('/health');
}

export function fetchMetrics() {
  return get('/metrics');
}

// ── Trading Bot ──────────────────────────────────────────────

export function fetchBotStatus() {
  return get('/api/v1/trading/status');
}

export function fetchBotPositions() {
  return get('/api/v1/trading/positions');
}

export function fetchBotSignals() {
  return get('/api/v1/trading/signals');
}

/**
 * @param {number} [limit=50]
 */
export function fetchBotHistory(limit = 50) {
  return get('/api/v1/trading/history', { limit });
}

export function fetchBotConfig() {
  return get('/api/v1/trading/config');
}

/**
 * @param {Object} config  Bot configuration payload
 */
export function updateBotConfig(config) {
  return post('/api/v1/trading/config', config);
}

/**
 * @param {string} reason  Reason for kill switch activation
 */
export function invalidateBot(reason) {
  return post('/api/v1/trading/invalidate', { reason });
}

export function startBot() {
  return post('/api/v1/trading/start');
}

export function stopBot() {
  return post('/api/v1/trading/stop');
}

// ── Geo-Intel ───────────────────────────────────────────────

/**
 * Fetch all geo-intelligence data in parallel (seismic, comex, intel, chokepoints).
 * @returns {Promise<{seismic: Object, comex: Object, intel: Object, chokepoints: Object}>}
 */
export async function fetchGeoIntel() {
  const [seismic, comex, intel, chokepoints] = await Promise.all([
    get('/api/v1/geointel/seismic'),
    get('/api/v1/geointel/comex'),
    get('/api/v1/geointel/intel'),
    get('/api/v1/geointel/chokepoints'),
  ]);
  return { seismic, comex, intel, chokepoints };
}

// ── Geo-Signals / Events / Regime ───────────────────────

export function fetchGeoSignals() {
  return get('/api/v1/geointel/signals');
}

export function fetchGeoEvents() {
  return get('/api/v1/geointel/events');
}

export function fetchRegime() {
  return get('/api/v1/geointel/regime');
}

// ── Correlations ────────────────────────────────────────────

export function fetchCorrelations() {
  return get('/api/v1/correlations');
}

// ── Signal Log ──────────────────────────────────────────────

export function fetchSignalLog() {
  return get('/api/v1/signal-log');
}
