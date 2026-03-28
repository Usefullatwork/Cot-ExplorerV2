import { describe, it, expect, beforeEach, vi } from 'vitest';

// Mock API calls
vi.mock('../api.js', () => ({
  fetchGeoSignals: vi.fn(),
  fetchGeoEvents: vi.fn(),
  fetchRegime: vi.fn(),
}));

// Mock state
vi.mock('../state.js', () => ({
  setState: vi.fn(),
  subscribe: vi.fn(),
}));

import { render, update } from '../components/GeoEventsPanel.js';

/** Build a mock regime payload. */
function makeRegime(name = 'RISK_OFF') {
  return {
    name,
    description: 'VIX > 25. Min score raised to 12, position size halved.',
    adjustments: 'Min score: 12, Lots: 0.5x',
  };
}

/** Build mock geo-signals. */
function makeSignals() {
  return [
    {
      event_type: 'conflict',
      confidence: 85,
      strength: 'strong',
      reasoning: 'Escalation in Red Sea shipping lanes',
      instruments: [
        { symbol: 'XAUUSD', direction: 'bull' },
        { symbol: 'USOIL', direction: 'bull' },
        { symbol: 'EURUSD', direction: 'bear' },
      ],
      expires_at: new Date(Date.now() + 86400000).toISOString(),
      sources: [{ title: 'Reuters', url: 'https://reuters.com/1' }],
    },
    {
      event_type: 'sanctions',
      confidence: 60,
      strength: 'moderate',
      reasoning: 'New sanctions on Russian oil exports',
      instruments: [
        { symbol: 'Brent', direction: 'bull' },
        { symbol: 'USDJPY', direction: 'bear' },
      ],
      expires_at: new Date(Date.now() + 43200000).toISOString(),
      sources: [],
    },
  ];
}

/** Build mock geo-events. */
function makeEvents() {
  return [
    { timestamp: new Date(Date.now() - 3600000).toISOString(), event_type: 'conflict', title: 'Red Sea attack', source: 'BBC', confidence: 90, url: 'https://bbc.com/1' },
    { timestamp: new Date(Date.now() - 86400000).toISOString(), event_type: 'sanctions', title: 'EU sanctions package', source: 'FT', confidence: 75, url: 'https://ft.com/2' },
    { timestamp: new Date(Date.now() - 172800000).toISOString(), event_type: 'supply', title: 'Chile mine shutdown', source: 'Reuters', confidence: 65 },
  ];
}

describe('GeoEventsPanel', () => {
  let container;

  beforeEach(() => {
    document.body.innerHTML = '';
    container = document.createElement('div');
    container.id = 'panel-geo-events';
    document.body.appendChild(container);
  });

  it('renders regime banner with mock regime data', () => {
    render(container);
    update({ regime: makeRegime(), geoSignals: makeSignals(), geoEvents: makeEvents() });

    const banner = document.getElementById('geo-regime-banner');
    expect(banner).not.toBeNull();
    expect(banner.textContent).toContain('RISK-OFF');
    expect(banner.textContent).toContain('REGIME');
    expect(banner.textContent).toContain('VIX > 25');
  });

  it('renders signal cards sorted by confidence', () => {
    render(container);
    update({ regime: makeRegime(), geoSignals: makeSignals(), geoEvents: makeEvents() });

    const signalsEl = document.getElementById('geo-signals');
    expect(signalsEl).not.toBeNull();
    const cards = signalsEl.querySelectorAll('.card');
    expect(cards.length).toBe(2);

    // First card should be the higher confidence signal (85%)
    expect(cards[0].textContent).toContain('85');
    expect(cards[0].textContent).toContain('Red Sea shipping');
    // Second card should be lower (60%)
    expect(cards[1].textContent).toContain('60');
  });

  it('renders event timeline with filter buttons', () => {
    render(container);
    update({ regime: makeRegime(), geoSignals: makeSignals(), geoEvents: makeEvents() });

    const filtersEl = document.getElementById('geo-timeline-filters');
    expect(filtersEl).not.toBeNull();
    const buttons = filtersEl.querySelectorAll('button');
    expect(buttons.length).toBeGreaterThanOrEqual(3); // Alle + conflict + sanctions + supply
    const labels = Array.from(buttons).map((b) => b.textContent);
    expect(labels).toContain('Alle');
    expect(labels).toContain('conflict');

    const listEl = document.getElementById('geo-timeline-list');
    expect(listEl).not.toBeNull();
    expect(listEl.textContent).toContain('Red Sea attack');
    expect(listEl.textContent).toContain('EU sanctions package');
  });

  it('renders impact map grid', () => {
    render(container);
    update({ regime: makeRegime(), geoSignals: makeSignals(), geoEvents: makeEvents() });

    const mapEl = document.getElementById('geo-impact-map');
    expect(mapEl).not.toBeNull();
    // Should contain instrument labels
    expect(mapEl.textContent).toContain('XAUUSD');
    expect(mapEl.textContent).toContain('USOIL');
    // Should contain direction arrows
    expect(mapEl.innerHTML).toContain('\u2191'); // up arrow
    expect(mapEl.innerHTML).toContain('\u2193'); // down arrow
  });

  it('confidence bar colors: high=green, mid=yellow, low=red', () => {
    render(container);
    update({ regime: makeRegime(), geoSignals: makeSignals(), geoEvents: makeEvents() });

    const signalsEl = document.getElementById('geo-signals');
    const cards = signalsEl.querySelectorAll('.card');
    // 85% confidence -> green (var(--bull))
    const firstCardStyle = cards[0].innerHTML;
    expect(firstCardStyle).toContain('var(--bull)');
    // 60% confidence -> yellow (var(--warn))
    const secondCardStyle = cards[1].innerHTML;
    expect(secondCardStyle).toContain('var(--warn)');
  });

  it('escapeHtml is used on all dynamic content', () => {
    render(container);
    update({
      regime: { name: 'CRISIS', description: '<script>alert("xss")</script>' },
      geoSignals: [{
        event_type: 'conflict',
        confidence: 50,
        strength: 'weak',
        reasoning: '<img src=x onerror=alert(1)>',
        instruments: [{ symbol: '<b>XSS</b>', direction: 'bull' }],
        sources: [{ title: '<a>hack</a>', url: 'javascript:void(0)' }],
      }],
      geoEvents: [{
        timestamp: new Date().toISOString(),
        event_type: 'conflict',
        title: '<script>document.cookie</script>',
        source: '<b>evil</b>',
        confidence: 50,
      }],
    });

    // No raw <script> tags should appear in the DOM
    const fullHtml = container.innerHTML;
    expect(fullHtml).not.toContain('<script>');
    expect(fullHtml).not.toContain('<img src=x');
    expect(fullHtml).toContain('&lt;script&gt;');
  });

  it('handles null data in update() gracefully', () => {
    render(container);
    // Should not throw
    update(undefined);

    // Skeleton elements should remain
    expect(document.getElementById('geo-regime-banner')).not.toBeNull();
    expect(document.getElementById('geo-signals')).not.toBeNull();
    expect(document.getElementById('geo-timeline-list')).not.toBeNull();
    expect(document.getElementById('geo-impact-map')).not.toBeNull();
  });

  it('handles empty signals and events', () => {
    render(container);
    update({ regime: makeRegime(), geoSignals: [], geoEvents: [] });

    const signalsEl = document.getElementById('geo-signals');
    expect(signalsEl.textContent).toContain('Ingen aktive geo-signaler');

    const listEl = document.getElementById('geo-timeline-list');
    expect(listEl.textContent).toContain('Ingen hendelser');

    const mapEl = document.getElementById('geo-impact-map');
    expect(mapEl.textContent).toContain('Ingen aktive signaler');
  });
});
