import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';

// Mock leaflet before importing the component
vi.mock('leaflet', () => {
  const mockMap = {
    remove: vi.fn(),
    invalidateSize: vi.fn(),
    setView: vi.fn().mockReturnThis(),
  };
  const mockLayerGroup = {
    addTo: vi.fn().mockReturnThis(),
    clearLayers: vi.fn(),
  };
  return {
    default: {
      map: vi.fn(() => mockMap),
      tileLayer: vi.fn(() => ({ addTo: vi.fn() })),
      layerGroup: vi.fn(() => ({ ...mockLayerGroup, addTo: vi.fn().mockReturnThis(), clearLayers: vi.fn() })),
      circleMarker: vi.fn(() => ({ bindPopup: vi.fn().mockReturnThis(), addTo: vi.fn() })),
      polyline: vi.fn(() => ({ bindPopup: vi.fn().mockReturnThis(), addTo: vi.fn() })),
      marker: vi.fn(() => ({ bindPopup: vi.fn().mockReturnThis(), addTo: vi.fn() })),
      control: { layers: vi.fn(() => ({ addTo: vi.fn() })) },
      icon: vi.fn(() => ({})),
      divIcon: vi.fn(() => ({})),
      latLng: vi.fn((a, b) => [a, b]),
    },
  };
});

// Mock leaflet CSS (jsdom cannot load CSS)
vi.mock('leaflet/dist/leaflet.css', () => ({}));

import L from 'leaflet';
import { render, update, destroy } from '../components/GeoMapPanel.js';

describe('GeoMapPanel', () => {
  let container;

  beforeEach(() => {
    vi.clearAllMocks();
    document.body.innerHTML = '';
    container = document.createElement('div');
    container.id = 'geo-map';
    document.body.appendChild(container);
  });

  afterEach(() => {
    // Reset module-level state between tests
    destroy();
  });

  it('creates a Leaflet map when render() is called', () => {
    render(container);

    expect(L.map).toHaveBeenCalledTimes(1);
    expect(L.map).toHaveBeenCalledWith(container, expect.objectContaining({
      center: [30, 20],
      zoom: 2,
    }));
  });

  it('adds a tile layer to the map', () => {
    render(container);

    expect(L.tileLayer).toHaveBeenCalledTimes(1);
    expect(L.tileLayer).toHaveBeenCalledWith(
      expect.stringContaining('cartocdn.com'),
      expect.objectContaining({ maxZoom: 19 }),
    );
  });

  it('creates six layer groups (mines, chokepoints, pipelines, lngTerminals, shippingLanes, seismic)', () => {
    render(container);

    // 6 layer groups
    expect(L.layerGroup).toHaveBeenCalledTimes(6);
  });

  it('adds a layer control overlay', () => {
    render(container);

    expect(L.control.layers).toHaveBeenCalledTimes(1);
    expect(L.control.layers).toHaveBeenCalledWith(
      null,
      expect.objectContaining({
        Gruver: expect.anything(),
        Chokepoints: expect.anything(),
        Rorledninger: expect.anything(),
        'LNG-terminaler': expect.anything(),
        Shippingruter: expect.anything(),
        Seismisk: expect.anything(),
      }),
      expect.objectContaining({ collapsed: false, position: 'topright' }),
    );
  });

  it('does not re-create the map if render() is called twice', () => {
    render(container);
    render(container);

    expect(L.map).toHaveBeenCalledTimes(1);
  });

  it('adds circleMarkers for mines on update()', () => {
    render(container);

    update({
      mines: [
        { name: 'Test Mine', type: 'open-pit', country: 'Chile', commodity: 'copper', production: 'large', lat: -33.4, lon: -70.6 },
        { name: 'Gold Mine', type: 'underground', country: 'Australia', commodity: 'gold', production: 'medium', lat: -25.2, lon: 131.0 },
      ],
    });

    expect(L.circleMarker).toHaveBeenCalledTimes(2);
    expect(L.circleMarker).toHaveBeenCalledWith(
      [-33.4, -70.6],
      expect.objectContaining({ fillColor: '#B87333' }), // copper color
    );
    expect(L.circleMarker).toHaveBeenCalledWith(
      [-25.2, 131.0],
      expect.objectContaining({ fillColor: '#FFD700' }), // gold color
    );
  });

  it('adds polylines for pipelines on update()', () => {
    render(container);

    update({
      pipelines: [
        { name: 'Nord Stream', type: 'gas', coords: [[55, 12], [60, 30]], color: '#58a6ff' },
      ],
    });

    expect(L.polyline).toHaveBeenCalledTimes(1);
    expect(L.polyline).toHaveBeenCalledWith(
      [[55, 12], [60, 30]],
      expect.objectContaining({ dashArray: '5, 5' }), // gas type gets dashed
    );
  });

  it('adds circleMarkers for LNG terminals on update()', () => {
    render(container);

    update({
      lngTerminals: [
        { name: 'Hammerfest LNG', type: 'export', country: 'Norway', lat: 70.6, lon: 23.6 },
      ],
    });

    // circleMarker called once for the LNG terminal
    expect(L.circleMarker).toHaveBeenCalledTimes(1);
    expect(L.circleMarker).toHaveBeenCalledWith(
      [70.6, 23.6],
      expect.objectContaining({ radius: 5, fillColor: '#58a6ff' }),
    );
  });

  it('adds polylines for shipping lanes on update()', () => {
    render(container);

    update({
      shippingLanes: [
        { name: 'Suez Route', coords: [[30, 32], [12, 43]], color: '#58a6ff' },
      ],
    });

    expect(L.polyline).toHaveBeenCalledTimes(1);
    expect(L.polyline).toHaveBeenCalledWith(
      [[30, 32], [12, 43]],
      expect.objectContaining({ dashArray: '10, 6', opacity: 0.5 }),
    );
  });

  it('adds markers for chokepoints on update()', () => {
    render(container);

    update({
      chokepoints: [
        { name: 'Strait of Hormuz', description: 'Critical oil transit', lat: 26.5, lon: 56.2 },
      ],
    });

    expect(L.marker).toHaveBeenCalledTimes(1);
    expect(L.marker).toHaveBeenCalledWith([26.5, 56.2]);
  });

  it('adds circleMarkers for seismic events on update()', () => {
    render(container);

    update({
      seismic: [
        { lat: 35.6, lon: 139.7, magnitude: 5.2, place: 'Tokyo, Japan' },
      ],
    });

    expect(L.circleMarker).toHaveBeenCalledTimes(1);
    expect(L.circleMarker).toHaveBeenCalledWith(
      [35.6, 139.7],
      expect.objectContaining({ radius: expect.any(Number) }),
    );
  });

  it('does nothing on update() if map has not been initialized', () => {
    // Don't call render(), so map is null
    update({ mines: [{ name: 'X', type: 'Y', country: 'Z', commodity: 'gold', production: 'large', lat: 0, lon: 0 }] });

    expect(L.circleMarker).not.toHaveBeenCalled();
  });

  it('destroy() calls map.remove() and resets state', () => {
    render(container);

    const mapInstance = L.map.mock.results[0].value;

    destroy();

    expect(mapInstance.remove).toHaveBeenCalledTimes(1);
  });

  it('destroy() is safe to call when map is not initialized', () => {
    // Should not throw
    expect(() => destroy()).not.toThrow();
  });

  it('can re-render after destroy()', () => {
    render(container);
    destroy();
    render(container);

    expect(L.map).toHaveBeenCalledTimes(2);
  });
});
