import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import {
  fetchSignals,
  fetchSignal,
  fetchInstruments,
  fetchInstrument,
  fetchCot,
  fetchCotHistory,
  fetchCotSummary,
  fetchMacro,
  fetchMacroIndicators,
  fetchHealth,
  fetchMetrics,
} from '../api.js';

describe('API client', () => {
  let mockFetch;

  beforeEach(() => {
    // Set base URL so URL construction works in jsdom
    window.__API_BASE = 'http://localhost:8000';

    mockFetch = vi.fn().mockResolvedValue({
      ok: true,
      json: () => Promise.resolve({ data: 'test' }),
      text: () => Promise.resolve(''),
    });
    globalThis.fetch = mockFetch;
  });

  afterEach(() => {
    vi.restoreAllMocks();
    delete window.__API_BASE;
  });

  // ── Signals ─────────────────────────────────────────────────

  it('fetchSignals calls /api/v1/signals', async () => {
    await fetchSignals();
    expect(mockFetch).toHaveBeenCalledOnce();
    const url = mockFetch.mock.calls[0][0];
    expect(url).toContain('/api/v1/signals');
  });

  it('fetchSignals passes filter params', async () => {
    await fetchSignals({ grade: 'A+', bias: 'bull' });
    const url = mockFetch.mock.calls[0][0];
    expect(url).toContain('grade=A%2B');
    expect(url).toContain('bias=bull');
  });

  it('fetchSignals omits null/undefined params', async () => {
    await fetchSignals({ grade: undefined, bias: null });
    const url = mockFetch.mock.calls[0][0];
    expect(url).not.toContain('grade');
    expect(url).not.toContain('bias');
  });

  it('fetchSignal calls /api/v1/signals/:key', async () => {
    await fetchSignal('EURUSD');
    const url = mockFetch.mock.calls[0][0];
    expect(url).toContain('/api/v1/signals/EURUSD');
  });

  // ── Instruments ────────────────────────────────────────────

  it('fetchInstruments calls /api/v1/instruments', async () => {
    await fetchInstruments();
    const url = mockFetch.mock.calls[0][0];
    expect(url).toContain('/api/v1/instruments');
  });

  it('fetchInstrument calls /api/v1/instruments/:key', async () => {
    await fetchInstrument('Gold');
    const url = mockFetch.mock.calls[0][0];
    expect(url).toContain('/api/v1/instruments/Gold');
  });

  // ── COT ────────────────────────────────────────────────────

  it('fetchCot calls /api/v1/cot', async () => {
    await fetchCot();
    const url = mockFetch.mock.calls[0][0];
    expect(url).toContain('/api/v1/cot');
  });

  it('fetchCotHistory includes symbol and date params', async () => {
    await fetchCotHistory('ES', '2026-01-01', '2026-03-01', 'Legacy');
    const url = mockFetch.mock.calls[0][0];
    expect(url).toContain('/api/v1/cot/ES/history');
    expect(url).toContain('start=2026-01-01');
    expect(url).toContain('end=2026-03-01');
    expect(url).toContain('report_type=Legacy');
  });

  it('fetchCotSummary calls /api/v1/cot/summary', async () => {
    await fetchCotSummary();
    const url = mockFetch.mock.calls[0][0];
    expect(url).toContain('/api/v1/cot/summary');
  });

  // ── Macro ──────────────────────────────────────────────────

  it('fetchMacro calls /api/v1/macro', async () => {
    await fetchMacro();
    const url = mockFetch.mock.calls[0][0];
    expect(url).toContain('/api/v1/macro');
  });

  it('fetchMacroIndicators calls /api/v1/macro/indicators', async () => {
    await fetchMacroIndicators();
    const url = mockFetch.mock.calls[0][0];
    expect(url).toContain('/api/v1/macro/indicators');
  });

  // ── Health / Metrics ───────────────────────────────────────

  it('fetchHealth calls /health', async () => {
    await fetchHealth();
    const url = mockFetch.mock.calls[0][0];
    expect(url).toContain('/health');
  });

  it('fetchMetrics calls /metrics', async () => {
    await fetchMetrics();
    const url = mockFetch.mock.calls[0][0];
    expect(url).toContain('/metrics');
  });

  // ── Error handling ─────────────────────────────────────────

  it('throws on non-ok response', async () => {
    mockFetch.mockResolvedValueOnce({
      ok: false,
      status: 500,
      statusText: 'Internal Server Error',
      text: () => Promise.resolve('server error'),
    });

    await expect(fetchHealth()).rejects.toThrow('API 500');
  });

  it('includes response text in error message', async () => {
    mockFetch.mockResolvedValueOnce({
      ok: false,
      status: 404,
      statusText: 'Not Found',
      text: () => Promise.resolve('route not found'),
    });

    await expect(fetchSignals()).rejects.toThrow('route not found');
  });

  it('returns parsed JSON on success', async () => {
    mockFetch.mockResolvedValueOnce({
      ok: true,
      json: () => Promise.resolve({ signals: [1, 2, 3] }),
      text: () => Promise.resolve(''),
    });

    const result = await fetchSignals();
    expect(result).toEqual({ signals: [1, 2, 3] });
  });
});
