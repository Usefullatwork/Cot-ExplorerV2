/** GeoMapPanel — Leaflet.js world map with mines, pipelines, chokepoints, infrastructure. */
import L from 'leaflet';
import 'leaflet/dist/leaflet.css';
import { escapeHtml } from '../utils.js';
import { MINE_COLORS, INFRA_COLORS, PRODUCTION_RADIUS } from '../constants/geoData.js';

let map = null;
let layerGroups = {};

export function render(container) {
  if (map) return; // already initialized

  map = L.map(container, {
    center: [30, 20],
    zoom: 2,
    zoomControl: true,
    attributionControl: true,
  });

  L.tileLayer('https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png', {
    attribution:
      '&copy; <a href="https://www.openstreetmap.org/copyright">OSM</a> ' +
      '&copy; <a href="https://carto.com/">CARTO</a>',
    subdomains: 'abcd',
    maxZoom: 19,
  }).addTo(map);

  // Create layer groups
  layerGroups = {
    mines: L.layerGroup().addTo(map),
    chokepoints: L.layerGroup().addTo(map),
    pipelines: L.layerGroup().addTo(map),
    lngTerminals: L.layerGroup().addTo(map),
    shippingLanes: L.layerGroup().addTo(map),
    seismic: L.layerGroup().addTo(map),
  };

  // Add layer control with Norwegian labels
  L.control
    .layers(
      null,
      {
        Gruver: layerGroups.mines,
        Chokepoints: layerGroups.chokepoints,
        Rorledninger: layerGroups.pipelines,
        'LNG-terminaler': layerGroups.lngTerminals,
        Shippingruter: layerGroups.shippingLanes,
        Seismisk: layerGroups.seismic,
      },
      { collapsed: false, position: 'topright' },
    )
    .addTo(map);

  // Force resize after render
  setTimeout(() => map && map.invalidateSize(), 100);
}

export function update({
  mines,
  pipelines,
  lngTerminals,
  shippingLanes,
  chokepoints,
  seismic,
} = {}) {
  if (!map) return;

  if (mines) {
    layerGroups.mines.clearLayers();
    mines.forEach((m) => {
      const color = MINE_COLORS[m.commodity] || MINE_COLORS.copper;
      const radius = PRODUCTION_RADIUS[m.production] || 4;
      L.circleMarker([m.lat, m.lon], {
        radius,
        fillColor: color,
        fillOpacity: 0.8,
        color: '#fff',
        weight: 1,
      })
        .bindPopup(
          `<b>${escapeHtml(m.name)}</b><br>${escapeHtml(m.type)}<br>${escapeHtml(m.country)}`,
        )
        .addTo(layerGroups.mines);
    });
  }

  if (pipelines) {
    layerGroups.pipelines.clearLayers();
    pipelines.forEach((p) => {
      L.polyline(p.coords, {
        color: p.color || INFRA_COLORS.oil,
        weight: 2,
        opacity: 0.7,
        dashArray: p.type === 'gas' ? '5, 5' : null,
      })
        .bindPopup(
          `<b>${escapeHtml(p.name)}</b><br>Type: ${escapeHtml(p.type)}`,
        )
        .addTo(layerGroups.pipelines);
    });
  }

  if (lngTerminals) {
    layerGroups.lngTerminals.clearLayers();
    lngTerminals.forEach((t) => {
      L.circleMarker([t.lat, t.lon], {
        radius: 5,
        fillColor: INFRA_COLORS.lng,
        fillOpacity: 0.9,
        color: '#fff',
        weight: 1,
      })
        .bindPopup(
          `<b>${escapeHtml(t.name)}</b><br>${escapeHtml(t.type)} — ${escapeHtml(t.country)}`,
        )
        .addTo(layerGroups.lngTerminals);
    });
  }

  if (shippingLanes) {
    layerGroups.shippingLanes.clearLayers();
    shippingLanes.forEach((s) => {
      L.polyline(s.coords, {
        color: s.color || '#58a6ff',
        weight: 2,
        opacity: 0.5,
        dashArray: '10, 6',
      })
        .bindPopup(`<b>${escapeHtml(s.name)}</b>`)
        .addTo(layerGroups.shippingLanes);
    });
  }

  if (chokepoints && Array.isArray(chokepoints)) {
    layerGroups.chokepoints.clearLayers();
    chokepoints.forEach((c) => {
      L.marker([c.lat, c.lon])
        .bindPopup(
          `<b>${escapeHtml(c.name)}</b><br>${escapeHtml(c.description || '')}`,
        )
        .addTo(layerGroups.chokepoints);
    });
  }

  if (seismic && Array.isArray(seismic)) {
    layerGroups.seismic.clearLayers();
    seismic.forEach((s) => {
      const mag = s.magnitude || 0;
      const fillColor =
        mag >= 6 ? 'var(--bear)' : mag >= 4 ? '#e8730e' : '#8b6914';
      L.circleMarker([s.lat, s.lon], {
        radius: Math.max(3, mag * 2),
        fillColor,
        fillOpacity: 0.6,
        color: '#fff',
        weight: 1,
      })
        .bindPopup(
          `<b>M${mag.toFixed(1)}</b><br>${escapeHtml(s.place || '')}`,
        )
        .addTo(layerGroups.seismic);
    });
  }
}

export function destroy() {
  if (map) {
    map.remove();
    map = null;
    layerGroups = {};
  }
}
