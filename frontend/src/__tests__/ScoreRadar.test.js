import { describe, it, expect, beforeEach, vi } from 'vitest';

// Mock Chart.js radar chart
vi.mock('../charts/radarChart.js', () => ({
  createRadarChart: vi.fn(() => ({
    destroy: vi.fn(),
    update: vi.fn(),
  })),
}));

import { render, update } from '../components/ScoreRadar.js';

/** Minimal instrument data with score_details. */
function makeInstrument(overrides = {}) {
  return {
    name: 'EURUSD',
    score: 8,
    score_pct: 75,
    score_details: [
      { kryss: 'COT', verdi: true, beskrivelse: 'COT bias matches direction' },
      { kryss: 'SMA200', verdi: true, beskrivelse: 'Price above 200 SMA' },
      { kryss: 'ATR', verdi: true, beskrivelse: 'ATR within range' },
      { kryss: 'Levels', verdi: true, beskrivelse: 'Near key level' },
      { kryss: 'Session', verdi: true, beskrivelse: 'Active session' },
      { kryss: 'VIX', verdi: true, beskrivelse: 'Low VIX regime' },
      { kryss: 'DXY', verdi: false, beskrivelse: 'DXY not aligned' },
      { kryss: 'Macro', verdi: false, beskrivelse: 'Macro headwind' },
    ],
    ...overrides,
  };
}

describe('ScoreRadar', () => {
  let container;

  beforeEach(() => {
    document.body.innerHTML = '';
    container = document.createElement('div');
    container.id = 'radar-host';
    document.body.appendChild(container);
  });

  it('renders the radar card skeleton (initially hidden)', () => {
    render(container);

    const card = document.getElementById('radarCard');
    expect(card).not.toBeNull();
    expect(card.style.display).toBe('none');
  });

  it('renders the detail modal (initially hidden)', () => {
    render(container);

    const modal = document.getElementById('radarModal');
    expect(modal).not.toBeNull();
    expect(modal.getAttribute('aria-hidden')).toBe('true');
  });

  it('shows the radar card when update() receives valid instrument data', () => {
    render(container);
    update(makeInstrument());

    const card = document.getElementById('radarCard');
    expect(card.style.display).toBe('block');
  });

  it('hides the radar card when update() receives null', () => {
    render(container);
    update(makeInstrument());
    update(null);

    const card = document.getElementById('radarCard');
    expect(card.style.display).toBe('none');
  });

  it('hides the radar card when instrument has no score_details', () => {
    render(container);
    update({ name: 'GBPUSD', score_details: [] });

    const card = document.getElementById('radarCard');
    expect(card.style.display).toBe('none');
  });

  it('renders score summary with pass count', () => {
    render(container);
    update(makeInstrument());

    const summary = document.getElementById('radarSummary');
    expect(summary).not.toBeNull();
    // 6 out of 8 pass in our mock data
    expect(summary.textContent).toContain('6/8');
    expect(summary.textContent).toContain('75%');
  });

  it('renders breakdown dots for each score criterion', () => {
    render(container);
    update(makeInstrument());

    const breakdown = document.getElementById('radarBreakdown');
    const items = breakdown.querySelectorAll('.score-item');
    expect(items.length).toBe(8);

    // Check that labels are present
    const labels = Array.from(items).map((el) => el.textContent.trim());
    expect(labels.some((l) => l.includes('COT'))).toBe(true);
    expect(labels.some((l) => l.includes('DXY'))).toBe(true);
  });

  it('opens the detail modal when the "Vis detaljer" button is clicked', () => {
    render(container);
    update(makeInstrument());

    const detailBtn = document.getElementById('radarDetailBtn');
    detailBtn.click();

    const modal = document.getElementById('radarModal');
    expect(modal.style.display).toBe('flex');
    expect(modal.getAttribute('aria-hidden')).toBe('false');

    // Modal should show instrument name
    const title = document.getElementById('radarModalTitle');
    expect(title.textContent).toContain('EURUSD');
    expect(title.textContent).toContain('6/8');
  });

  it('closes the detail modal when the close button is clicked', () => {
    render(container);
    update(makeInstrument());

    // Open modal
    document.getElementById('radarDetailBtn').click();
    expect(document.getElementById('radarModal').style.display).toBe('flex');

    // Close modal
    document.getElementById('radarModalClose').click();
    expect(document.getElementById('radarModal').style.display).toBe('none');
    expect(document.getElementById('radarModal').getAttribute('aria-hidden')).toBe('true');
  });

  it('renders color legend after update()', () => {
    render(container);
    update(makeInstrument());

    const legend = document.getElementById('radarLegend');
    expect(legend).not.toBeNull();
    expect(legend.textContent).toContain('Oppfylt');
    expect(legend.textContent).toContain('Ikke oppfylt');
  });
});
