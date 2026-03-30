import { describe, it, expect, beforeEach, vi } from 'vitest';

// Mock Chart.js before importing the component
vi.mock('chart.js', () => {
  class MockChart {
    constructor() {
      this.destroy = vi.fn();
      this.update = vi.fn();
    }
  }
  MockChart.register = vi.fn();
  return {
    Chart: MockChart,
    LineController: {},
    LineElement: {},
    PointElement: {},
    CategoryScale: {},
    LinearScale: {},
    Tooltip: {},
    Filler: {},
  };
});

// Mock pnlChart
vi.mock('../charts/pnlChart.js', () => ({
  createPnlChart: vi.fn(),
  destroyPnlChart: vi.fn(),
}));

// Mock API calls
vi.mock('../api.js', () => ({
  fetchBotStatus: vi.fn(),
  fetchBotPositions: vi.fn(),
  fetchBotSignals: vi.fn(),
  fetchBotHistory: vi.fn(),
  fetchBotConfig: vi.fn(),
  updateBotConfig: vi.fn(),
  invalidateBot: vi.fn(),
  startBot: vi.fn(),
  stopBot: vi.fn(),
}));

import { render, update } from '../components/BotPanel.js';
import { updateBotConfig, invalidateBot } from '../api.js';

describe('BotPanel', () => {
  let container;

  beforeEach(() => {
    document.body.innerHTML = '';
    container = document.createElement('div');
    container.id = 'panel-trading';
    document.body.appendChild(container);
  });

  it('renders skeleton with all sections', () => {
    render(container);

    // Status banner
    expect(document.getElementById('botStatusBanner')).not.toBeNull();
    expect(document.getElementById('botStatusBody')).not.toBeNull();

    // Positions table
    expect(document.getElementById('positionsBody')).not.toBeNull();
    expect(document.getElementById('posCount')).not.toBeNull();

    // Signals table
    expect(document.getElementById('signalsBody')).not.toBeNull();
    expect(document.getElementById('sigCount')).not.toBeNull();

    // P&L stats
    expect(document.getElementById('pnlToday')).not.toBeNull();
    expect(document.getElementById('pnlTrades')).not.toBeNull();
    expect(document.getElementById('pnlWinRate')).not.toBeNull();
    expect(document.getElementById('pnlBestWorst')).not.toBeNull();
    expect(document.getElementById('pnlCanvas')).not.toBeNull();

    // Kill switch
    expect(document.getElementById('killSwitchBtn')).not.toBeNull();
    expect(document.getElementById('killConfirmDialog')).not.toBeNull();

    // Config
    expect(document.getElementById('cfgActive')).not.toBeNull();
    expect(document.getElementById('cfgMode')).not.toBeNull();
    expect(document.getElementById('cfgMaxPos')).not.toBeNull();
    expect(document.getElementById('cfgRisk')).not.toBeNull();
    expect(document.getElementById('cfgMinGrade')).not.toBeNull();
    expect(document.getElementById('cfgMinScore')).not.toBeNull();
    expect(document.getElementById('cfgSaveBtn')).not.toBeNull();

    // Trade log
    expect(document.getElementById('tradeLogBody')).not.toBeNull();

    // Section headings
    const headings = container.querySelectorAll('.sh-t');
    const texts = Array.from(headings).map((h) => h.textContent);
    expect(texts).toContain('Aktive Posisjoner');
    expect(texts).toContain('Signalkoe');
    expect(texts).toContain('Daglig P&L');
    expect(texts).toContain('Kill Switch');
    expect(texts).toContain('Konfigurasjon');
    expect(texts).toContain('Handelslogg');
  });

  it('update populates positions table', () => {
    render(container);
    update({
      positions: [
        {
          instrument: 'EURUSD',
          direction: 'LONG',
          entry: 1.08500,
          current: 1.08750,
          pnl_pips: 25.0,
          pnl_usd: 250.00,
          lots: 1.0,
          candles: 12,
          t1_hit: true,
          status: 'active',
        },
        {
          instrument: 'GBPUSD',
          direction: 'SHORT',
          entry: 1.26000,
          current: 1.25800,
          pnl_pips: 20.0,
          pnl_usd: 200.00,
          lots: 0.5,
          candles: 8,
          t1_hit: false,
          status: 'active',
        },
      ],
    });

    const body = document.getElementById('positionsBody');
    const rows = body.querySelectorAll('tr');
    expect(rows.length).toBe(2);

    // First row contains EURUSD
    expect(rows[0].textContent).toContain('EURUSD');
    expect(rows[0].textContent).toContain('LONG');

    // Second row contains GBPUSD
    expect(rows[1].textContent).toContain('GBPUSD');
    expect(rows[1].textContent).toContain('SHORT');

    // Position count badge
    const posCount = document.getElementById('posCount');
    expect(posCount.textContent).toBe('2');
  });

  it('update handles empty positions', () => {
    render(container);
    update({ positions: [] });

    const body = document.getElementById('positionsBody');
    expect(body.textContent).toContain('Ingen åpne posisjoner');

    const posCount = document.getElementById('posCount');
    expect(posCount.textContent).toBe('0');
  });

  it('update populates signals table', () => {
    render(container);
    update({
      signals: [
        {
          instrument: 'AUDUSD',
          direction: 'LONG',
          grade: 'A+',
          score: 7,
          entry_zone: '0.6550-0.6570',
          status: 'pending',
          received: new Date().toISOString(),
        },
      ],
    });

    const body = document.getElementById('signalsBody');
    const rows = body.querySelectorAll('tr');
    expect(rows.length).toBe(1);
    expect(rows[0].textContent).toContain('AUDUSD');
    expect(rows[0].textContent).toContain('LONG');
    expect(rows[0].textContent).toContain('A+');

    const sigCount = document.getElementById('sigCount');
    expect(sigCount.textContent).toBe('1');
  });

  it('update populates P&L stats', () => {
    render(container);
    update({
      pnl: {
        today: 350.50,
        trades: 7,
        win_rate: 71.4,
        best: 150.00,
        worst: -45.00,
      },
    });

    const todayEl = document.getElementById('pnlToday');
    expect(todayEl.textContent).toBe('+$350.50');
    expect(todayEl.className).toContain('bull');

    const tradesEl = document.getElementById('pnlTrades');
    expect(tradesEl.textContent).toBe('7');

    const winEl = document.getElementById('pnlWinRate');
    expect(winEl.textContent).toBe('71.4%');
    expect(winEl.className).toContain('bull');

    const bwEl = document.getElementById('pnlBestWorst');
    expect(bwEl.textContent).toContain('+$150.00');
    expect(bwEl.textContent).toContain('$-45.00');
  });

  it('update populates config form', () => {
    render(container);
    update({
      config: {
        active: true,
        broker_mode: 'demo',
        max_positions: 8,
        risk_pct: 2.5,
        min_grade: 'A',
        min_score: 6,
      },
    });

    expect(document.getElementById('cfgActive').value).toBe('true');
    expect(document.getElementById('cfgMode').value).toBe('demo');
    expect(document.getElementById('cfgMaxPos').value).toBe('8');
    expect(document.getElementById('cfgRisk').value).toBe('2.5');
    expect(document.getElementById('cfgMinGrade').value).toBe('A');
    expect(document.getElementById('cfgMinScore').value).toBe('6');
  });

  it('update populates trade log', () => {
    render(container);
    update({
      history: [
        { time: '2026-03-27 10:00', event: 'fill', instrument: 'EURUSD', details: 'Buy 1.0 lot at 1.0850' },
        { time: '2026-03-27 09:30', event: 'signal', instrument: 'GBPUSD', details: 'Grade A+ score 7' },
        { time: '2026-03-27 09:00', event: 'error', instrument: 'USDJPY', details: 'Connection timeout' },
      ],
    });

    const body = document.getElementById('tradeLogBody');
    const rows = body.querySelectorAll('tr');
    expect(rows.length).toBe(3);
    expect(rows[0].textContent).toContain('EURUSD');
    expect(rows[0].textContent).toContain('fill');
    expect(rows[1].textContent).toContain('GBPUSD');
    expect(rows[2].textContent).toContain('USDJPY');
    expect(rows[2].textContent).toContain('error');
  });

  it('kill switch shows confirm dialog', () => {
    render(container);

    const dialog = document.getElementById('killConfirmDialog');
    // Initially hidden via inline style attribute
    expect(dialog.getAttribute('style')).toContain('display:none');

    // Click kill switch button
    const btn = document.getElementById('killSwitchBtn');
    btn.click();

    expect(dialog.style.display).toBe('block');

    // Click cancel to hide
    const cancelBtn = document.getElementById('killConfirmNo');
    cancelBtn.click();

    expect(dialog.style.display).toBe('none');
  });

  it('config save calls API', async () => {
    updateBotConfig.mockResolvedValue({});
    render(container);

    // Set some config values
    document.getElementById('cfgActive').value = 'true';
    document.getElementById('cfgMode').value = 'paper';
    document.getElementById('cfgMaxPos').value = '5';
    document.getElementById('cfgRisk').value = '1.0';
    document.getElementById('cfgMinGrade').value = 'B';
    document.getElementById('cfgMinScore').value = '5';

    // Click save
    const saveBtn = document.getElementById('cfgSaveBtn');
    saveBtn.click();

    // Wait for async handler
    await vi.waitFor(() => {
      expect(updateBotConfig).toHaveBeenCalledWith({
        active: true,
        broker_mode: 'paper',
        max_positions: 5,
        risk_pct: 1.0,
        min_grade: 'B',
        min_score: 5,
      });
    });

    // Success message should appear
    const msg = document.getElementById('cfgSaveMsg');
    expect(msg.textContent).toBe('Lagret!');
  });

  it('handles null data in update() gracefully', () => {
    render(container);
    update(null);

    // Should not throw; skeleton stays intact
    expect(document.getElementById('botStatusBanner')).not.toBeNull();
  });

  it('update handles empty signals', () => {
    render(container);
    update({ signals: [] });

    const body = document.getElementById('signalsBody');
    expect(body.textContent).toContain('Ingen signaler');

    const sigCount = document.getElementById('sigCount');
    expect(sigCount.textContent).toBe('0');
  });

  it('update handles empty trade log', () => {
    render(container);
    update({ history: [] });

    const body = document.getElementById('tradeLogBody');
    expect(body.textContent).toContain('Ingen hendelser');
  });
});
