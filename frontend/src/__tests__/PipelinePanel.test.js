import { describe, it, expect, beforeEach, vi } from 'vitest';

// Mock api.js before importing PipelinePanel
vi.mock('../api.js', () => ({
  fetchPipelineStatus: vi.fn().mockResolvedValue({
    regime: 'NORMAL',
    vix_price: 16.5,
    var_95_pct: 0.018,
    stress_survives: true,
    ensemble_quality: 'healthy',
    correlation_max: 0.65,
    drift_detected: false,
    open_position_count: 3,
    layer1_last_run_at: new Date().toISOString(),
    layer2_last_run_at: new Date().toISOString(),
  }),
  fetchPipelineRuns: vi.fn().mockResolvedValue({
    count: 2,
    runs: [
      { id: 1, started_at: new Date().toISOString(), layer: 'layer1', status: 'ok', duration_sec: 12.3, signals_processed: 5 },
      { id: 2, started_at: new Date().toISOString(), layer: 'layer2', status: 'ok', duration_sec: 3.1, signals_processed: 5 },
    ],
  }),
  fetchBotSignals: vi.fn().mockResolvedValue([]),
  fetchGateLog: vi.fn().mockResolvedValue({ gates: [] }),
  forceLayer2: vi.fn().mockResolvedValue({ layer2: { regime: 'NORMAL' }, signals_processed: 3, signals_passed: 2 }),
}));

import { render, refreshAll } from '../components/PipelinePanel.js';

describe('PipelinePanel', () => {
  let container;

  beforeEach(() => {
    document.body.innerHTML = '';
    container = document.createElement('div');
    container.id = 'panel-pipeline';
    document.body.appendChild(container);
  });

  it('renders skeleton with heading', () => {
    render(container);
    const heading = container.querySelector('.sh-t');
    expect(heading.textContent).toBe('Pipeline Monitor');
  });

  it('renders force layer 2 button', () => {
    render(container);
    const btn = document.getElementById('plForceBtn');
    expect(btn).toBeTruthy();
    expect(btn.textContent).toBe('Force Layer 2');
  });

  it('renders runs table header', () => {
    render(container);
    const header = container.querySelector('thead');
    expect(header.textContent).toContain('Layer');
    expect(header.textContent).toContain('Status');
  });

  it('renders gate log section', () => {
    render(container);
    const gateLog = document.getElementById('plGateLog');
    expect(gateLog).toBeTruthy();
  });

  it('populates status cards after refresh', async () => {
    render(container);
    await refreshAll();

    const status = document.getElementById('plStatus');
    expect(status.innerHTML).toContain('NORMAL');
    expect(status.innerHTML).toContain('16.5');
  });

  it('populates runs table after refresh', async () => {
    render(container);
    await refreshAll();

    const body = document.getElementById('plRunsBody');
    expect(body.innerHTML).toContain('layer1');
    expect(body.innerHTML).toContain('layer2');
  });

  it('shows placeholder when no L2 data', async () => {
    const api = await import('../api.js');
    // Set mock BEFORE render() since render calls refreshAll
    api.fetchPipelineStatus.mockResolvedValue({ is_placeholder: true, message: 'No data' });
    api.fetchPipelineRuns.mockResolvedValue({ count: 0, runs: [] });

    render(container);
    // Wait for render's internal refreshAll to complete
    await new Promise((r) => setTimeout(r, 50));

    const status = document.getElementById('plStatus');
    expect(status.innerHTML).toContain('Ingen Layer 2');
  });
});
