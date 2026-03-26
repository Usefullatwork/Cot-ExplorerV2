/**
 * MacroPanel component — Dollar Smile, VIX regime, macro stats, rates & credit.
 *
 * Ports the renderMakro function from v1 index.html.
 * Enhanced with interactive Chart.js charts, drill-down, trend arrows, and sparklines.
 */

import { formatPct } from '../utils.js';
import { createSparkline } from '../charts/miniSparkline.js';
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
/** @type {{ chart: any, series: any }[]} */
const sparklineInstances = [];

/**
 * Trend arrow helper.
 * @param {number} val  Change value
 * @returns {string}  HTML with colored arrow
 */
function trendArrow(val) {
  if (val == null || val === 0) return '<span style="color:var(--m)">--</span>';
  const up = val > 0;
  return `<span style="color:var(--${up ? 'bull' : 'bear'})">${up ? '\u25B2' : '\u25BC'} ${formatPct(val)}</span>`;
}

/**
 * Generate fake sparkline data from a current value and 5d change.
 * @param {number} current
 * @param {number} chg5d  Percentage change over 5 days
 * @returns {{ time: string, value: number }[]}
 */
function syntheticSparkData(current, chg5d) {
  if (!current) return [];
  const start = current / (1 + (chg5d || 0) / 100);
  const points = [];
  for (let i = 0; i < 5; i++) {
    const t = new Date();
    t.setDate(t.getDate() - (4 - i));
    const frac = (i + 1) / 5;
    const val = start + (current - start) * frac + (Math.random() - 0.5) * Math.abs(current - start) * 0.3;
    points.push({ time: t.toISOString().slice(0, 10), value: val });
  }
  return points;
}

/**
 * Build the static DOM skeleton inside the macro panel.
 * @param {HTMLElement} container  #panel-macro
 */
export function render(container) {
  container.innerHTML = `
    <div class="g21">
      <div class="card" role="region" aria-label="Dollar-smil modell">
        <div class="ct">Dollar-smil modell</div>
        <div class="smile" id="smile" role="img" aria-label="Dollar-smil posisjon"></div>
        <div style="font-size:13px;color:var(--m)" id="smileDesc" aria-live="polite"></div>
        <div class="sinp" id="smileInp" role="group" aria-label="Makro-indikatorer"></div>
      </div>
      <div>
        <div class="card" style="margin-bottom:12px" role="region" aria-label="VIX regime">
          <div class="ct">VIX-regime</div>
          <div id="vixDet" aria-live="polite"></div>
          <div style="height:100px;position:relative;margin-top:10px" role="img" aria-label="VIX trend diagram">
            <canvas id="vixMiniChart" aria-hidden="true"></canvas>
          </div>
          <div style="margin-top:12px;font-size:12px;color:var(--m);line-height:2" role="note">
            Under 20 - Full storrelse<br>
            20-30 - Halv storrelse<br>
            Over 30 - Kvart storrelse
          </div>
        </div>
        <div class="card" role="region" aria-label="Safe-haven hierarki">
          <div class="ct">Safe-haven hierarki</div>
          <div id="safeH" style="font-size:13px;line-height:1.8;color:var(--m)" aria-live="polite"></div>
        </div>
      </div>
    </div>
    <div class="g4" id="macroStats" role="group" aria-label="Makro noekkeltall"></div>
    <div class="sh" style="margin-top:16px"><h2 class="sh-t">Rente &amp; Kreditt</h2><div class="sh-b">Realrenter, spreader, vekst</div></div>
    <div class="g4" id="macroRente" role="group" aria-label="Rente og kreditt indikatorer"></div>
    <div id="macroDrilldown" style="display:none;margin-top:16px" role="region" aria-label="Detaljer">
      <div class="card">
        <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:12px">
          <div class="ct" style="margin-bottom:0" id="drilldownTitle">Detaljer</div>
          <button class="fc" id="drilldownClose" style="font-size:11px" aria-label="Lukk detaljer">Lukk</button>
        </div>
        <div id="drilldownBody" style="font-size:13px;color:var(--m);line-height:1.7"></div>
      </div>
    </div>`;

  // Drill-down close handler
  const closeBtn = container.querySelector('#drilldownClose');
  if (closeBtn) {
    closeBtn.addEventListener('click', () => {
      const dd = document.getElementById('macroDrilldown');
      if (dd) dd.style.display = 'none';
    });
  }
}

/**
 * Update the macro panel with fresh data.
 * @param {Object} m  Full macro data payload
 */
export function update(m) {
  if (!m) return;

  const sm = m.dollar_smile || {};
  const vx = m.vix_regime || {};
  const p = m.prices || {};
  const inp = sm.inputs || {};

  // ── Dollar Smile segments ──────────────────────────────────
  const segs = [
    ['venstre', 'al', 'Venstre', 'Krise/Risk-off', 'VIX>20'],
    ['midten', 'am', 'Midten', 'Goldilocks', 'Fed kutter'],
    ['hoyre', 'ar', 'Hoyre', 'Vekst/Inflasjon', 'Olje>$85'],
  ];

  const smileEl = document.getElementById('smile');
  if (smileEl) {
    smileEl.innerHTML = segs
      .map(
        (s) =>
          `<div class="sseg${sm.position === s[0] ? ' ' + s[1] : ''}"><div class="sp">${s[2]}</div><div class="sl2">${s[3]}</div><div class="sd">${s[4]}</div></div>`
      )
      .join('');
  }

  // ── Smile description ─────────────────────────────────────
  const descEl = document.getElementById('smileDesc');
  if (descEl) {
    const bc = sm.usd_color === 'bull' ? 'var(--bull)' : 'var(--bear)';
    descEl.innerHTML = `<strong style="color:${bc}">USD ${sm.usd_bias || ''}</strong> - ${sm.desc || ''}`;
  }

  // ── Smile inputs ──────────────────────────────────────────
  const hyTxt = inp.hy_stress
    ? 'JA (' + formatPct(inp.hy_chg5d || 0) + ')'
    : 'NEI (' + formatPct(inp.hy_chg5d || 0) + ')';
  const ycTxt =
    inp.yield_curve != null
      ? (inp.yield_curve > 0 ? '+' : '') + inp.yield_curve.toFixed(2) + '%'
      : '-';
  const ycCol =
    inp.yield_curve == null ? 'neutral' : inp.yield_curve < -0.3 ? 'bear' : inp.yield_curve < 0.3 ? 'warn' : 'bull';

  const items = [
    ['VIX', (inp.vix || 0).toFixed(1), inp.vix > 25 ? 'bear' : inp.vix > 20 ? 'warn' : 'bull'],
    ['HY Stress', hyTxt, inp.hy_stress ? 'bear' : 'bull'],
    ['Brent', '$' + (inp.brent || 0).toFixed(0), inp.brent > 85 ? 'warn' : 'bull'],
    ['TIPS 5d', formatPct(inp.tip_trend_5d || 0), inp.tip_trend_5d > 0 ? 'bull' : 'bear'],
    ['DXY 5d', formatPct(inp.dxy_trend_5d || 0), inp.dxy_trend_5d > 0 ? 'bull' : 'bear'],
    ['10Y-3M', ycTxt, ycCol],
    ['Kobber 5d', formatPct(inp.copper_5d || 0), inp.copper_5d > 0 ? 'bull' : 'bear'],
    ['EM 5d', formatPct(inp.em_5d || 0), inp.em_5d > 0 ? 'bull' : 'bear'],
  ];

  const sinpEl = document.getElementById('smileInp');
  if (sinpEl) {
    sinpEl.innerHTML = items
      .map((x) => `<div class="sii"><div class="sil">${x[0]}</div><div class="siv ${x[2]}">${x[1]}</div></div>`)
      .join('');
  }

  // ── VIX regime detail ─────────────────────────────────────
  const vixDetEl = document.getElementById('vixDet');
  if (vixDetEl) {
    vixDetEl.innerHTML = `<div class="snum ${vx.color || ''}">${(vx.value || 0).toFixed(1)}</div><div class="slabel" style="margin-top:4px;color:var(--${vx.color || 'm'})">${vx.label || ''}</div>`;
  }

  // ── Safe-haven hierarchy ──────────────────────────────────
  const riskOff = inp.vix > 20 || inp.hy_stress || (inp.yield_curve != null && inp.yield_curve < -0.3);
  const safeEl = document.getElementById('safeH');
  if (safeEl) {
    safeEl.innerHTML = riskOff
      ? '<strong style="color:var(--bear)">Risk-off aktiv</strong><br>Kjop: USD, XAU, CHF, JPY<br>Selg: NOK, AUD, NZD, CAD'
      : '<strong style="color:var(--bull)">Normalt marked</strong><br>Carry: AUD, NZD, CAD, NOK';
  }

  // ── VIX mini chart ───────────────────────────────────────
  const vixCanvas = document.getElementById('vixMiniChart');
  if (vixCanvas && p.VIX) {
    if (vixChart) { vixChart.destroy(); vixChart = null; }
    const vixVal = p.VIX.price || 0;
    const vixData = syntheticSparkData(vixVal, p.VIX.chg5d || 0);
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

  // ── Macro stats (VIX, DXY, Brent, Gold) — with trend arrows & sparklines ──
  const ms = [
    ['VIX', (p.VIX || {}).price, (p.VIX || {}).chg5d || 0, (p.VIX || {}).chg5d > 0 ? 'bear' : 'bull', 'Volatilitetsindeks. Over 20 = forsiktig, over 30 = defensiv.'],
    ['DXY', (p.DXY || {}).price, (p.DXY || {}).chg5d || 0, (p.DXY || {}).chg5d > 0 ? 'bull' : 'bear', 'Dollar-indeks. Styres av Dollar Smile-modellen.'],
    ['Brent', (p.Brent || {}).price, (p.Brent || {}).chg5d || 0, 'warn', 'Brent-olje. Over $85 = inflasjonspress.'],
    ['Gull', (p.Gold || {}).price, (p.Gold || {}).chg5d || 0, (p.Gold || {}).chg5d > 0 ? 'bull' : 'bear', 'Gull-pris. Safe haven ved risk-off.'],
  ];

  // Clean up old sparklines
  sparklineInstances.forEach((s) => { try { s.chart.remove(); } catch { /* noop */ } });
  sparklineInstances.length = 0;

  const msEl = document.getElementById('macroStats');
  if (msEl) {
    msEl.innerHTML = ms
      .map(
        (x, i) =>
          `<div class="card macro-stat-card" data-macro-idx="${i}" style="cursor:pointer">
            <div class="ct">${x[0]}</div>
            <div class="snum">${x[1] ? x[1].toFixed(x[1] > 100 ? 0 : 2) : '-'}</div>
            <div style="margin-top:4px">${trendArrow(x[2])}</div>
            <div class="macro-spark" id="macroSpark${i}" style="width:100%;height:30px;margin-top:8px"></div>
          </div>`
      )
      .join('');

    // Render sparklines for each stat card
    ms.forEach((x, i) => {
      const sparkEl = document.getElementById('macroSpark' + i);
      if (sparkEl && x[1]) {
        const data = syntheticSparkData(x[1], x[2]);
        const color = x[3] === 'bull' ? '#3fb950' : x[3] === 'bear' ? '#f85149' : '#d29922';
        const inst = createSparkline(sparkEl, data, color);
        sparklineInstances.push(inst);
      }
    });

    // Drill-down on click
    msEl.addEventListener('click', (e) => {
      const card = e.target.closest('.macro-stat-card');
      if (!card) return;
      const idx = parseInt(card.dataset.macroIdx, 10);
      const item = ms[idx];
      if (!item) return;
      const dd = document.getElementById('macroDrilldown');
      const title = document.getElementById('drilldownTitle');
      const body = document.getElementById('drilldownBody');
      if (dd && title && body) {
        title.textContent = item[0] + ' — Detaljer';
        body.innerHTML = `
          <div style="margin-bottom:8px"><strong>Napris:</strong> ${item[1] ? item[1].toFixed(item[1] > 100 ? 2 : 5) : '-'}</div>
          <div style="margin-bottom:8px"><strong>5-dagers endring:</strong> ${trendArrow(item[2])}</div>
          <div style="margin-bottom:8px"><strong>Regime:</strong> <span class="${item[3]}" style="font-weight:600">${item[3].toUpperCase()}</span></div>
          <div style="color:var(--m)">${item[4]}</div>`;
        dd.style.display = 'block';
      }
    });
  }

  // ── Rate & Credit panel ───────────────────────────────────
  const mi = m.macro_indicators || {};
  const rc = [
    ['10Y rente', mi.TNX ? mi.TNX.price.toFixed(2) + '%' : '-', inp.yield_curve != null && inp.yield_curve < 0 ? 'bear' : 'bull'],
    ['3M rente', mi.IRX ? mi.IRX.price.toFixed(2) + '%' : '-', 'neutral'],
    ['Rentekurve', ycTxt, ycCol],
    ['HY (HYG) 5d', mi.HYG ? formatPct(mi.HYG.chg5d) : '-', mi.HYG && mi.HYG.chg5d < -1.5 ? 'bear' : mi.HYG && mi.HYG.chg5d < 0 ? 'warn' : 'bull'],
    ['TIPS 5d', mi.TIP ? formatPct(mi.TIP.chg5d) : '-', mi.TIP && mi.TIP.chg5d > 0 ? 'bull' : 'bear'],
    ['Kobber 5d', mi.Copper ? formatPct(mi.Copper.chg5d) : '-', mi.Copper && mi.Copper.chg5d > 0 ? 'bull' : 'bear'],
    ['EM (EEM) 5d', mi.EEM ? formatPct(mi.EEM.chg5d) : '-', mi.EEM && mi.EEM.chg5d > 0 ? 'bull' : 'bear'],
  ];

  const renteEl = document.getElementById('macroRente');
  if (renteEl) {
    renteEl.innerHTML = rc
      .map(
        (x) => {
          // Extract numeric change from value string if possible for trend arrow
          const numMatch = x[1].match(/^([+-]?\d+\.?\d*)%?$/);
          const numVal = numMatch ? parseFloat(numMatch[1]) : null;
          const arrow = numVal !== null && x[0].includes('5d') ? trendArrow(numVal) : '';
          return `<div class="card"><div class="ct">${x[0]}</div><div class="snum" style="font-size:20px">${x[1]}</div>${arrow ? '<div style="margin-top:4px">' + arrow + '</div>' : ''}<div class="slabel" style="margin-top:4px;color:var(--${x[2]})">${x[2].toUpperCase()}</div></div>`;
        }
      )
      .join('');
  }
}
