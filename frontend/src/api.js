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

// ── Health / Metrics ────────────────────────────────────────

export function fetchHealth() {
  return get('/health');
}

export function fetchMetrics() {
  return get('/metrics');
}
