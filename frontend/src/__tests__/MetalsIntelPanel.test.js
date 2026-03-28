import { describe, it, expect, beforeEach, vi } from 'vitest';

// Mock API calls
vi.mock('../api.js', () => ({
  fetchGeoIntel: vi.fn(),
}));

// Mock state
vi.mock('../state.js', () => ({
  setState: vi.fn(),
  subscribe: vi.fn(),
}));

import { render, update } from '../components/MetalsIntelPanel.js';

/** Build a minimal COMEX data payload. */
function makeComex(overrides = {}) {
  return {
    gold: { registered: 2000000, eligible: 3000000, total: 5000000, daily_change: 50000, stress: 35, ...overrides.gold },
    silver: { registered: 100000, eligible: 200000, total: 300000, daily_change: -10000, stress: 60, ...overrides.silver },
    copper: { registered: 50000, eligible: 80000, total: 130000, daily_change: 0, stress: 45, ...overrides.copper },
  };
}

/** Build a minimal seismic data payload. */
function makeSeismic() {
  return [
    { magnitude: 6.2, place: 'Near Chile', region: 'Chile/Peru', time: Date.now() - 3600000 },
    { magnitude: 5.1, place: 'Papua New Guinea', region: 'Indonesia/Papua', time: Date.now() - 7200000 },
  ];
}

/** Build a minimal intel feed payload. */
function makeIntel() {
  return {
    articles: [
      { title: 'Gold hits record high', url: 'https://example.com/1', source: 'Reuters', time: new Date().toISOString(), category: 'gold' },
      { title: 'Silver supply crunch', url: 'https://example.com/2', source: 'Bloomberg', time: new Date().toISOString(), category: 'silver' },
      { title: 'Copper mine strike', url: 'https://example.com/3', source: 'FT', time: new Date().toISOString(), category: 'copper' },
      { title: 'Red Sea disruption', url: 'https://example.com/4', source: 'BBC', time: new Date().toISOString(), category: 'geopolitics' },
    ],
  };
}

describe('MetalsIntelPanel', () => {
  let container;

  beforeEach(() => {
    document.body.innerHTML = '';
    container = document.createElement('div');
    container.id = 'panel-metals-intel';
    document.body.appendChild(container);
  });

  it('renders COMEX cards with mock data', () => {
    render(container);
    update({ comex: makeComex(), seismic: makeSeismic(), intel: makeIntel() });

    const comexEl = document.getElementById('mi-comex');
    expect(comexEl).not.toBeNull();
    const cards = comexEl.querySelectorAll('.card');
    expect(cards.length).toBe(3);

    // Gold card should contain "Gull"
    expect(cards[0].textContent).toContain('Gull');
    // Silver card should contain "Solv"
    expect(cards[1].textContent).toContain('Solv');
    // Copper card should contain "Kobber"
    expect(cards[2].textContent).toContain('Kobber');
  });

  it('renders seismic list', () => {
    render(container);
    update({ comex: makeComex(), seismic: makeSeismic(), intel: makeIntel() });

    const seismicEl = document.getElementById('mi-seismic');
    expect(seismicEl).not.toBeNull();
    // Should contain the place names
    expect(seismicEl.textContent).toContain('Near Chile');
    expect(seismicEl.textContent).toContain('Papua New Guinea');
  });

  it('renders seismic events sorted by magnitude descending', () => {
    render(container);
    update({ seismic: makeSeismic() });

    const seismicEl = document.getElementById('mi-seismic');
    // First event should be the higher magnitude (6.2)
    expect(seismicEl.textContent.indexOf('6.2')).toBeLessThan(
      seismicEl.textContent.indexOf('5.1')
    );
  });

  it('renders intel feed articles', () => {
    render(container);
    update({ comex: makeComex(), seismic: makeSeismic(), intel: makeIntel() });

    const listEl = document.getElementById('mi-intel-list');
    expect(listEl).not.toBeNull();
    expect(listEl.textContent).toContain('Gold hits record high');
    expect(listEl.textContent).toContain('Silver supply crunch');
  });

  it('renders category filter buttons', () => {
    render(container);
    update({ intel: makeIntel() });

    const filtersEl = document.getElementById('mi-intel-filters');
    expect(filtersEl).not.toBeNull();
    const buttons = filtersEl.querySelectorAll('button');
    expect(buttons.length).toBe(5); // All, Gold, Silver, Copper, Geopolitics
    const labels = Array.from(buttons).map((b) => b.textContent);
    expect(labels).toContain('All');
    expect(labels).toContain('Gold');
    expect(labels).toContain('Silver');
    expect(labels).toContain('Copper');
    expect(labels).toContain('Geopolitics');
  });

  it('escapeHtml is used on dynamic content', () => {
    render(container);
    update({
      comex: makeComex(),
      seismic: [
        { magnitude: 5.5, place: '<script>alert("xss")</script>', region: 'Chile', time: Date.now() },
      ],
      intel: makeIntel(),
    });

    const seismicEl = document.getElementById('mi-seismic');
    // Raw <script> tag should NOT appear; it should be escaped
    expect(seismicEl.innerHTML).not.toContain('<script>');
    expect(seismicEl.innerHTML).toContain('&lt;script&gt;');
  });

  it('handles null data in update() gracefully', () => {
    render(container);
    update(null);

    // Should not throw; skeleton stays intact
    expect(document.getElementById('mi-comex')).not.toBeNull();
    expect(document.getElementById('mi-seismic')).not.toBeNull();
    expect(document.getElementById('mi-intel-list')).not.toBeNull();
  });

  it('handles empty seismic list', () => {
    render(container);
    update({ seismic: [] });

    const seismicEl = document.getElementById('mi-seismic');
    expect(seismicEl.textContent).toContain('Ingen seismiske hendelser');
  });
});
