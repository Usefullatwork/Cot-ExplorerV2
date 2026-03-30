/**
 * MacroVixSection sub-module — VIX regime, sentiment, VIX term structure, regime timeline.
 *
 * Extracted from MacroPanel.js for the 500-line limit.
 * Renders into containers created by MacroPanel.render().
 */

import { formatPct, escapeHtml } from '../../utils.js';
import { createVixTermChart, destroyVixTermChart } from '../../charts/vixTermChart.js';
import { fetchVixTerm, fetchRegimeHistory } from '../../api.js';
import {
  Chart,
  LineController,
  LineElement,
  PointElement,
  CategoryScale,
  LinearScale,
  Tooltip,
  Filler,
} from 'chart.js';

Chart.register(LineController, LineElement, PointElement, CategoryScale, LinearScale, Tooltip, Filler);

/** @type {Chart|null} */
let vixChart = null;

/**
 * Generate synthetic sparkline data from a current value and change percentage.
 * @param {number} current
 * @param {number} chgPct
 * @param {number} [numPoints=20]
 * @returns {{ time: string, value: number }[]}
 */
function syntheticSparkData(current, chgPct, numPoints = 20) {
  if (!current) return [];
  const start = current / (1 + (chgPct || 0) / 100);
  const points = [];
  for (let i = 0; i < numPoints; i++) {
    const t = new Date();
    t.setDate(t.getDate() - (numPoints - 1 - i));
    const frac = (i + 1) / numPoints;
    const val = start + (current - start) * frac + (Math.random() - 0.5) * Math.abs(current - start) * 0.3;
    points.push({ time: t.toISOString().slice(0, 10), value: val });
  }
  return points;
}

/**
 * Build the VIX regime, sentiment, term structure, and regime timeline skeleton.
 * @param {HTMLElement} vixContainer    Right column of g21 grid (VIX + sentiment + safe-haven)
 * @param {HTMLElement} termSection     VIX term structure section wrapper
 * @param {HTMLElement} timelineSection Regime timeline section wrapper
 */
export function render(vixContainer, termSection, timelineSection) {
  // VIX regime card + sentiment card (safe-haven is handled by MacroDollarSmile)
  vixContainer.innerHTML = `
    <div class="card" style="margin-bottom:12px" role="region" aria-label="VIX regime">
      <div class="ct">VIX-regime</div>
      <div id="vixDet" aria-live="polite"></div>
      <div style="height:200px;position:relative;margin-top:10px" role="img" aria-label="VIX trend diagram">
        <canvas id="vixMiniChart" aria-hidden="true"></canvas>
      </div>
      <div style="margin-top:12px;font-size:12px;color:var(--m);line-height:2" role="note">
        Under 20 - Full størrelse<br>
        20-30 - Halv størrelse<br>
        Over 30 - Kvart størrelse
      </div>
    </div>
    <div class="card" style="margin-bottom:12px" role="region" aria-label="Sentiment">
      <div class="ct">Sentiment</div>
      <div id="sentimentBody" aria-live="polite" style="font-size:13px;color:var(--m);line-height:1.8"></div>
    </div>`;

  // VIX term structure
  termSection.innerHTML = `
    <div class="sh" style="margin-top:16px"><h2 class="sh-t">VIX Termstruktur</h2><div class="sh-b">Spot, 9D, 3M — contango/backwardation</div></div>
    <div id="vixTermGrid" class="g4" role="group" aria-label="VIX termstruktur"></div>
    <div class="card" style="margin-top:12px;padding:12px">
      <div style="height:200px;position:relative">
        <canvas id="vixTermChart" aria-label="VIX termstruktur diagram"></canvas>
      </div>
    </div>`;

  // Regime timeline
  timelineSection.innerHTML = `
    <div class="sh" style="margin-top:16px"><h2 class="sh-t">Regime-tidslinje</h2><div class="sh-b">Siste 30 dager</div></div>
    <div id="regimeTimeline" role="img" aria-label="Regime tidslinje" style="padding:8px 0"></div>`;
}

/**
 * Destroy VIX chart instances for cleanup before re-render.
 */
export function destroyCharts() {
  destroyVixTermChart();
  if (vixChart) {
    vixChart.destroy();
    vixChart = null;
  }
}

/**
 * Update VIX regime, sentiment, term structure, and regime timeline.
 * @param {Object} m  Full macro data payload
 */
export function update(m) {
  if (!m) return;

  const vx = m.vix_regime || {};
  const p = m.prices || {};

  // VIX regime detail
  const vixDetEl = document.getElementById('vixDet');
  if (vixDetEl) {
    vixDetEl.innerHTML = `<div class="snum ${vx.color || ''}">${(vx.value || 0).toFixed(1)}</div><div class="slabel" style="margin-top:4px;color:var(--${vx.color || 'm'})">${vx.label || ''}</div>`;
  }

  // Sentiment card
  const sentEl = document.getElementById('sentimentBody');
  if (sentEl) {
    const sent = m.sentiment || {};
    const fg = sent.fear_greed || {};
    const news = sent.news || {};

    let fgColor = 'var(--m)';
    const fgScore = fg.score != null ? fg.score : null;
    if (fgScore != null) {
      if (fgScore <= 25) fgColor = 'var(--bear)';
      else if (fgScore <= 45) fgColor = 'var(--warn)';
      else if (fgScore >= 75) fgColor = 'var(--bull)';
      else fgColor = 'var(--m)';
    }

    const newsLabel = news.label || 'neutral';
    const newsColor = newsLabel === 'risk_on' ? 'var(--bull)' : newsLabel === 'risk_off' ? 'var(--bear)' : 'var(--warn)';
    const newsDisplay = newsLabel.replace('_', ' ').toUpperCase();

    const headlines = (news.top_headlines || []).slice(0, 3);
    const headlineHtml = headlines.length
      ? headlines.map((h) => `<div style="margin-left:8px;font-size:11px;color:var(--m);line-height:1.5">- ${typeof h === 'string' ? h : h.title || h}</div>`).join('')
      : '<div style="font-size:11px;color:var(--m)">Ingen overskrifter</div>';

    sentEl.innerHTML = `
      <div style="display:flex;gap:24px;align-items:center;margin-bottom:10px">
        <div>
          <div style="font-size:11px;color:var(--m);margin-bottom:4px">Fear & Greed</div>
          <div class="mono" style="font-size:28px;font-weight:600;color:${fgColor}">${fgScore != null ? fgScore.toFixed(0) : '--'}</div>
          <div style="font-size:10px;color:${fgColor};text-transform:uppercase;font-weight:600">${fg.rating || '--'}</div>
        </div>
        <div>
          <div style="font-size:11px;color:var(--m);margin-bottom:4px">Nyhetssentiment</div>
          <div class="mono" style="font-size:16px;font-weight:600;color:${newsColor}">${newsDisplay}</div>
          <div style="font-size:10px;color:var(--m)">Score: ${news.score != null ? news.score.toFixed(2) : '--'}</div>
        </div>
      </div>
      <div style="font-size:11px;color:var(--m);font-weight:600;margin-bottom:4px">Topp overskrifter:</div>
      ${headlineHtml}`;
  }

  // VIX mini chart
  const vixCanvas = document.getElementById('vixMiniChart');
  if (vixCanvas && p.VIX) {
    if (vixChart) { vixChart.destroy(); vixChart = null; }
    const vixVal = p.VIX.price || 0;
    const vixData = syntheticSparkData(vixVal, p.VIX.chg20d || p.VIX.chg5d || 0, 20);
    const vixLabels = vixData.map((d) => d.time.slice(5));
    const vixValues = vixData.map((d) => d.value);
    const vixColor = vixVal > 25 ? 'rgba(248,81,73,0.8)' : vixVal > 20 ? 'rgba(210,153,34,0.8)' : 'rgba(63,185,80,0.8)';
    vixChart = new Chart(vixCanvas.getContext('2d'), {
      type: 'line',
      data: {
        labels: vixLabels,
        datasets: [{
          data: vixValues,
          borderColor: vixColor,
          backgroundColor: vixColor.replace('0.8', '0.1'),
          borderWidth: 2,
          pointRadius: 3,
          pointBackgroundColor: vixColor,
          fill: true,
          tension: 0.3,
        }],
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
          legend: { display: false },
          tooltip: {
            backgroundColor: '#1c2128',
            borderColor: '#30363d',
            borderWidth: 1,
            titleColor: '#e6edf3',
            bodyColor: '#7d8590',
            padding: 8,
            cornerRadius: 6,
            displayColors: false,
            callbacks: {
              label(ctx) { return 'VIX: ' + ctx.raw.toFixed(1); },
            },
          },
        },
        scales: {
          x: { ticks: { color: '#7d8590', font: { size: 9 } }, grid: { color: '#21262d' } },
          y: { ticks: { color: '#7d8590', font: { size: 9 } }, grid: { color: '#21262d' } },
        },
      },
    });
  }

  // VIX Term Structure (async fetch)
  fetchVixTerm()
    .then((vt) => {
      const termEl = document.getElementById('vixTermGrid');
      if (!termEl || !vt) return;
      const regimeColor = vt.regime === 'backwardation' ? 'bear' : vt.regime === 'contango' ? 'bull' : 'warn';
      const regimeLabel = vt.regime === 'backwardation' ? 'Backwardation' : vt.regime === 'contango' ? 'Contango' : 'Flat';
      termEl.innerHTML = [
        { name: 'VIX Spot', val: vt.spot.toFixed(1), col: vt.spot > 25 ? 'bear' : vt.spot > 20 ? 'warn' : 'bull' },
        { name: 'VIX 9D', val: vt.vix_9d.toFixed(1), col: vt.vix_9d > 25 ? 'bear' : vt.vix_9d > 20 ? 'warn' : 'bull' },
        { name: 'VIX 3M', val: vt.vix_3m.toFixed(1), col: vt.vix_3m > 25 ? 'bear' : vt.vix_3m > 20 ? 'warn' : 'bull' },
        { name: 'Regime', val: escapeHtml(regimeLabel), col: regimeColor },
      ]
        .map((x) => `<div class="card"><div class="ct">${escapeHtml(x.name)}</div><div class="snum mono" style="font-size:20px">${x.val}</div><div class="slabel" style="margin-top:4px;color:var(--${x.col})">${x.col.toUpperCase()}</div></div>`)
        .join('');

      const termCanvas = document.getElementById('vixTermChart');
      if (termCanvas) {
        createVixTermChart(termCanvas, {
          vix_9d: vt.vix_9d,
          spot: vt.spot,
          vix_3m: vt.vix_3m,
          regime: vt.regime,
          spread: vt.spread || (vt.vix_3m - vt.spot),
        });
      }
    })
    .catch(() => {});

  // Regime Timeline (async fetch)
  fetchRegimeHistory()
    .then((data) => {
      const tlEl = document.getElementById('regimeTimeline');
      if (!tlEl || !data || !data.days || !data.days.length) return;
      const colorMap = { green: 'var(--bull)', yellow: 'var(--warn)', orange: '#e87c2f', red: 'var(--bear)' };
      const labelMap = { normal: 'Normal', risk_off: 'Risk-off', crisis: 'Krise', war_footing: 'Krig', energy_shock: 'Energi', sanctions: 'Sanksjoner' };
      const dayWidth = Math.max(4, Math.floor(600 / data.days.length));
      const bars = data.days
        .map((d) => `<div title="${escapeHtml(d.date)}: ${escapeHtml(labelMap[d.regime] || d.regime)}" style="width:${dayWidth}px;height:24px;background:${colorMap[d.color] || 'var(--bull)'};border-radius:2px;cursor:help"></div>`)
        .join('');
      const legend = Object.entries(labelMap)
        .map(([k, v]) => {
          const col = colorMap[({ normal: 'green', risk_off: 'yellow', crisis: 'red', war_footing: 'red', energy_shock: 'orange', sanctions: 'orange' })[k] || 'green'];
          return `<span style="display:inline-flex;align-items:center;gap:3px;font-size:10px;color:var(--m)"><span style="width:8px;height:8px;border-radius:2px;background:${col};display:inline-block"></span>${v}</span>`;
        })
        .join(' ');
      tlEl.innerHTML = `<div style="display:flex;gap:1px;align-items:end">${bars}</div><div style="display:flex;gap:8px;margin-top:6px;flex-wrap:wrap">${legend}</div>`;
    })
    .catch(() => {});
}
