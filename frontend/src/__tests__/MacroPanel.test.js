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

// Mock miniSparkline
vi.mock('../charts/miniSparkline.js', () => ({
  createSparkline: vi.fn(() => ({ chart: { remove: vi.fn() }, series: {} })),
}));

// Mock priceLineChart
vi.mock('../charts/priceLineChart.js', () => ({
  createPriceChart: vi.fn(() => ({ chart: { remove: vi.fn() }, series: {}, _ro: { disconnect: vi.fn() } })),
}));

import { render, update } from '../components/MacroPanel.js';

/** Minimal macro data payload. */
function makeMacro(overrides = {}) {
  return {
    dollar_smile: {
      position: 'midten',
      usd_bias: 'Bearish',
      usd_color: 'bear',
      desc: 'Goldilocks scenario',
      inputs: {
        vix: 18.5,
        hy_stress: false,
        hy_chg5d: -0.3,
        brent: 72,
        tip_trend_5d: 0.15,
        dxy_trend_5d: -0.42,
        yield_curve: 0.12,
        copper_5d: 1.2,
        em_5d: 0.8,
      },
    },
    vix_regime: {
      value: 18.5,
      label: 'Lavt',
      color: 'bull',
    },
    prices: {
      VIX: { price: 18.5, chg1d: -0.3, chg5d: -2.1 },
      DXY: { price: 104.2, chg1d: 0.1, chg5d: -0.5 },
      Brent: { price: 72.4, chg1d: 0.8, chg5d: 1.2 },
      Gold: { price: 2045, chg1d: 0.5, chg5d: 1.8 },
    },
    macro_indicators: {
      TNX: { price: 4.35, chg5d: -0.1 },
      IRX: { price: 5.2, chg5d: 0.05 },
      HYG: { price: 76.5, chg5d: -0.8 },
      TIP: { price: 107.2, chg5d: 0.15 },
      Copper: { price: 4.1, chg5d: 1.2 },
      EEM: { price: 40.5, chg5d: 0.8 },
    },
    ...overrides,
  };
}

describe('MacroPanel', () => {
  let container;

  beforeEach(() => {
    document.body.innerHTML = '';
    container = document.createElement('div');
    container.id = 'panel-macro';
    document.body.appendChild(container);
  });

  it('renders the panel skeleton with Dollar Smile card', () => {
    render(container);

    const ct = container.querySelector('.ct');
    expect(ct).not.toBeNull();
    expect(ct.textContent).toBe('Dollar-smil modell');
  });

  it('renders the VIX-regime card', () => {
    render(container);

    const headings = container.querySelectorAll('.ct');
    const texts = Array.from(headings).map((h) => h.textContent);
    expect(texts).toContain('VIX-regime');
  });

  it('renders the Safe-haven hierarki card', () => {
    render(container);

    const headings = container.querySelectorAll('.ct');
    const texts = Array.from(headings).map((h) => h.textContent);
    expect(texts).toContain('Safe-haven hierarki');
  });

  it('renders the Rente & Kreditt section heading', () => {
    render(container);

    const headings = container.querySelectorAll('.sh-t');
    expect(headings.length).toBeGreaterThanOrEqual(2);
    const texts = Array.from(headings).map((h) => h.textContent);
    expect(texts).toContain('Rente & Kreditt');
  });

  it('handles null data in update() gracefully', () => {
    render(container);
    update(null);

    // Should not throw; skeleton stays intact
    expect(container.querySelector('.ct')).not.toBeNull();
  });

  it('renders Dollar Smile segments after update()', () => {
    render(container);
    update(makeMacro());

    const smileEl = document.getElementById('smile');
    expect(smileEl).not.toBeNull();
    const segments = smileEl.querySelectorAll('.sseg');
    expect(segments.length).toBe(3);
  });

  it('highlights the active smile position', () => {
    render(container);
    update(makeMacro({ dollar_smile: { position: 'midten', usd_bias: 'Bearish', usd_color: 'bear', desc: 'Test', inputs: {} } }));

    const smileEl = document.getElementById('smile');
    const active = smileEl.querySelector('.am');
    expect(active).not.toBeNull();
  });

  it('renders smile input indicators (VIX, HY Stress, Brent, etc.)', () => {
    render(container);
    update(makeMacro());

    const sinpEl = document.getElementById('smileInp');
    expect(sinpEl).not.toBeNull();
    const items = sinpEl.querySelectorAll('.sii');
    expect(items.length).toBe(8);

    const labels = Array.from(items).map((el) => el.querySelector('.sil').textContent);
    expect(labels).toContain('VIX');
    expect(labels).toContain('HY Stress');
    expect(labels).toContain('Brent');
    expect(labels).toContain('TIPS 5d');
    expect(labels).toContain('DXY 5d');
  });

  it('renders VIX regime value and label', () => {
    render(container);
    update(makeMacro());

    const vixDet = document.getElementById('vixDet');
    expect(vixDet).not.toBeNull();
    expect(vixDet.querySelector('.snum').textContent).toBe('18.5');
    expect(vixDet.querySelector('.slabel').textContent).toBe('Lavt');
  });

  it('renders macro stat cards (VIX, DXY, Brent, Gull)', () => {
    render(container);
    update(makeMacro());

    const msEl = document.getElementById('macroStats');
    expect(msEl).not.toBeNull();
    const cards = msEl.querySelectorAll('.macro-stat-card');
    expect(cards.length).toBe(4);

    const headings = Array.from(cards).map((c) => c.querySelector('.ct').textContent);
    expect(headings).toContain('VIX');
    expect(headings).toContain('DXY');
    expect(headings).toContain('Brent');
    expect(headings).toContain('Gull');
  });

  it('renders Rate & Credit indicators after update()', () => {
    render(container);
    update(makeMacro());

    const renteEl = document.getElementById('macroRente');
    expect(renteEl).not.toBeNull();
    const cards = renteEl.querySelectorAll('.card');
    expect(cards.length).toBeGreaterThanOrEqual(5);
  });
});
