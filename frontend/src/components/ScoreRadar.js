/**
 * ScoreRadar component — Chart.js radar chart for 12-point confluence scoring.
 *
 * New component (not in v1). Subscribes to state.selectedInstrument.
 */

import { createRadarChart } from '../charts/radarChart.js';

let chartInstance = null;

/**
 * Build the radar chart container.
 * @param {HTMLElement} container  A panel or sub-element to host the radar
 */
export function render(container) {
  container.innerHTML = `
    <div class="card" id="radarCard" style="display:none">
      <div class="ct">Konfluens-radar</div>
      <div style="height:300px;position:relative">
        <canvas id="radarCanvas"></canvas>
      </div>
      <div id="radarSummary" style="font-size:12px;color:var(--m);margin-top:8px;text-align:center"></div>
    </div>`;
}

/**
 * Update the radar chart for a selected instrument.
 * @param {Object|null} instrument  Signal data with score_details array
 */
export function update(instrument) {
  const card = document.getElementById('radarCard');
  if (!card) return;

  if (!instrument || !instrument.score_details || !instrument.score_details.length) {
    card.style.display = 'none';
    return;
  }

  card.style.display = 'block';

  const details = instrument.score_details;
  const labels = details.map((d) => d.kryss || d.label || 'Kriterium');
  const values = details.map((d) => (d.verdi ? 1 : 0));
  const passing = values.filter((v) => v).length;

  // Destroy previous chart
  if (chartInstance) {
    chartInstance.destroy();
    chartInstance = null;
  }

  const canvas = document.getElementById('radarCanvas');
  if (canvas) {
    chartInstance = createRadarChart(canvas, labels, values);
  }

  const summaryEl = document.getElementById('radarSummary');
  if (summaryEl) {
    summaryEl.textContent = `${passing}/${details.length} kriterier oppfylt (${instrument.score_pct || 0}%)`;
  }
}
