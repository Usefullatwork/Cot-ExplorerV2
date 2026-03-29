/**
 * MacroPanel component — Dollar Smile, VIX regime, sentiment, macro stats,
 * rates & credit, and conflicts.
 *
 * Ports the renderMakro function from v1 index.html.
 * Enhanced with full-size lightweight-charts, drill-down, trend arrows,
 * 1d/5d/20d change bars, sentiment card, and conflicts section.
 */

import { formatPct, escapeHtml, formatPrice } from '../utils.js';
import { createSparkline } from '../charts/miniSparkline.js';
import { createPriceChart } from '../charts/priceLineChart.js';
import { createVixTermChart, destroyVixTermChart } from '../charts/vixTermChart.js';
import { fetchVixTerm, fetchADR, fetchRegimeHistory } from '../api.js';
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
const chartInstances = [];

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
 * Generate synthetic sparkline/chart data from a current value and change percentage.
 * @param {number} current
 * @param {number} chgPct  Percentage change over the period
 * @param {number} [numPoints=20]  Number of data points to generate
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
 * Build a 1d/5d/20d change bar HTML string.
 * @param {number|null} chg1d
 * @param {number|null} chg5d
 * @param {number|null} chg20d
 * @returns {string}
 */
function changeBar(chg1d, chg5d, chg20d) {
  const fmt = (label, val) => {
    if (val == null) return `<span style="color:var(--m)">${label}: --</span>`;
    const color = val > 0 ? 'var(--bull)' : val < 0 ? 'var(--bear)' : 'var(--m)';
    const arrow = val > 0 ? '\u25B2' : val < 0 ? '\u25BC' : '';
    return `<span style="color:${color}">${label}: ${arrow} ${formatPct(val)}</span>`;
  };
  return `<div style="display:flex;gap:12px;margin-top:8px;font-size:11px;font-family:'DM Mono',monospace">${fmt('1d', chg1d)}${fmt('5d', chg5d)}${fmt('20d', chg20d)}</div>`;
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
          <div style="height:200px;position:relative;margin-top:10px" role="img" aria-label="VIX trend diagram">
            <canvas id="vixMiniChart" aria-hidden="true"></canvas>
          </div>
          <div style="margin-top:12px;font-size:12px;color:var(--m);line-height:2" role="note">
            Under 20 - Full storrelse<br>
            20-30 - Halv storrelse<br>
            Over 30 - Kvart storrelse
          </div>
        </div>
        <div class="card" style="margin-bottom:12px" role="region" aria-label="Sentiment">
          <div class="ct">Sentiment</div>
          <div id="sentimentBody" aria-live="polite" style="font-size:13px;color:var(--m);line-height:1.8"></div>
        </div>
        <div class="card" role="region" aria-label="Safe-haven hierarki">
          <div class="ct">Safe-haven hierarki</div>
          <div id="safeH" style="font-size:13px;line-height:1.8;color:var(--m)" aria-live="polite"></div>
        </div>
      </div>
    </div>
    <div class="sh"><h2 class="sh-t">Makro Noekkeltall</h2><div class="sh-b">VIX, DXY, Brent, Gull</div></div>
    <div class="g2" id="macroStats" role="group" aria-label="Makro noekkeltall"></div>
    <div class="sh" style="margin-top:16px"><h2 class="sh-t">Rente &amp; Kreditt</h2><div class="sh-b">Realrenter, spreader, vekst</div></div>
    <div class="g4" id="macroRente" role="group" aria-label="Rente og kreditt indikatorer"></div>
    <div class="sh" style="margin-top:16px"><h2 class="sh-t">VIX Termstruktur</h2><div class="sh-b">Spot, 9D, 3M — contango/backwardation</div></div>
    <div id="vixTermGrid" class="g4" role="group" aria-label="VIX termstruktur"></div>
    <div class="card" style="margin-top:12px;padding:12px">
      <div style="height:200px;position:relative">
        <canvas id="vixTermChart" aria-label="VIX termstruktur diagram"></canvas>
      </div>
    </div>
    <div class="sh" style="margin-top:16px"><h2 class="sh-t">Regime-tidslinje</h2><div class="sh-b">Siste 30 dager</div></div>
    <div id="regimeTimeline" role="img" aria-label="Regime tidslinje" style="padding:8px 0"></div>
    <div class="sh" style="margin-top:16px"><h2 class="sh-t">Sesjonsrekkevidde (ADR)</h2><div class="sh-b">20-dagers gjennomsnittlig daglig rekkevidde</div></div>
    <div id="adrTable" role="region" aria-label="ADR tabell"></div>
    <div id="macroConflicts" style="display:none;margin-top:16px" role="alert" aria-label="Konflikter"></div>
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

  // ── Sentiment card ─────────────────────────────────────────
  const sentEl = document.getElementById('sentimentBody');
  if (sentEl) {
    const sent = m.sentiment || {};
    const fg = sent.fear_greed || {};
    const news = sent.news || {};

    // Fear & Greed score with color coding
    let fgColor = 'var(--m)';
    const fgScore = fg.score != null ? fg.score : null;
    if (fgScore != null) {
      if (fgScore <= 25) fgColor = 'var(--bear)';
      else if (fgScore <= 45) fgColor = 'var(--warn)';
      else if (fgScore >= 75) fgColor = 'var(--bull)';
      else fgColor = 'var(--m)';
    }

    // News sentiment label
    const newsLabel = news.label || 'neutral';
    const newsColor = newsLabel === 'risk_on' ? 'var(--bull)' : newsLabel === 'risk_off' ? 'var(--bear)' : 'var(--warn)';
    const newsDisplay = newsLabel.replace('_', ' ').toUpperCase();

    // Top headlines
    const headlines = (news.top_headlines || []).slice(0, 3);
    const headlineHtml = headlines.length
      ? headlines.map((h) => `<div style="margin-left:8px;font-size:11px;color:var(--m);line-height:1.5">- ${typeof h === 'string' ? h : h.title || h}</div>`).join('')
      : '<div style="font-size:11px;color:var(--m)">Ingen overskrifter</div>';

    sentEl.innerHTML = `
      <div style="display:flex;gap:24px;align-items:center;margin-bottom:10px">
        <div>
          <div style="font-size:11px;color:var(--m);margin-bottom:4px">Fear & Greed</div>
          <div style="font-family:'DM Mono',monospace;font-size:28px;font-weight:600;color:${fgColor}">${fgScore != null ? fgScore.toFixed(0) : '--'}</div>
          <div style="font-size:10px;color:${fgColor};text-transform:uppercase;font-weight:600">${fg.rating || '--'}</div>
        </div>
        <div>
          <div style="font-size:11px;color:var(--m);margin-bottom:4px">Nyhetssentiment</div>
          <div style="font-family:'DM Mono',monospace;font-size:16px;font-weight:600;color:${newsColor}">${newsDisplay}</div>
          <div style="font-size:10px;color:var(--m)">Score: ${news.score != null ? news.score.toFixed(2) : '--'}</div>
        </div>
      </div>
      <div style="font-size:11px;color:var(--m);font-weight:600;margin-bottom:4px">Topp overskrifter:</div>
      ${headlineHtml}`;
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

  // ── Macro stats (VIX, DXY, Brent, Gold) — big charts with 1d/5d/20d ──
  const ms = [
    {
      name: 'VIX', data: p.VIX || {},
      colorFn: (d) => (d.chg5d || 0) > 0 ? 'bear' : 'bull',
      desc: 'Volatilitetsindeks. Over 20 = forsiktig, over 30 = defensiv.',
    },
    {
      name: 'DXY', data: p.DXY || {},
      colorFn: (d) => (d.chg5d || 0) > 0 ? 'bull' : 'bear',
      desc: 'Dollar-indeks. Styres av Dollar Smile-modellen.',
    },
    {
      name: 'Brent', data: p.Brent || {},
      colorFn: () => 'warn',
      desc: 'Brent-olje. Over $85 = inflasjonspress.',
    },
    {
      name: 'Gull', data: p.Gold || {},
      colorFn: (d) => (d.chg5d || 0) > 0 ? 'bull' : 'bear',
      desc: 'Gull-pris. Safe haven ved risk-off.',
    },
  ];

  // Clean up old chart instances
  destroyVixTermChart();
  chartInstances.forEach((inst) => {
    try {
      if (inst.chart && inst.chart.remove) inst.chart.remove();
      if (inst._ro) inst._ro.disconnect();
    } catch { /* noop */ }
  });
  chartInstances.length = 0;

  const msEl = document.getElementById('macroStats');
  if (msEl) {
    msEl.innerHTML = ms
      .map(
        (x, i) => {
          const price = x.data.price;
          const chg1d = x.data.chg1d;
          const chg5d = x.data.chg5d;
          const chg20d = x.data.chg20d;
          const col = x.colorFn(x.data);
          return `<div class="card macro-stat-card" data-macro-idx="${i}" style="cursor:pointer">
            <div class="ct">${x.name}</div>
            <div class="snum">${price ? price.toFixed(price > 100 ? 0 : 2) : '-'}</div>
            <div style="margin-top:4px">${trendArrow(chg5d || 0)}</div>
            ${changeBar(chg1d, chg5d, chg20d)}
            <div class="macro-price-chart" id="macroPriceChart${i}" style="width:100%;height:180px;margin-top:12px;border-radius:6px;overflow:hidden"></div>
          </div>`;
        }
      )
      .join('');

    // Render full price charts for each stat card
    ms.forEach((x, i) => {
      const chartEl = document.getElementById('macroPriceChart' + i);
      if (chartEl && x.data.price) {
        const chgForData = x.data.chg20d || x.data.chg5d || 0;
        const data = syntheticSparkData(x.data.price, chgForData, 20);
        const inst = createPriceChart(chartEl, data);
        chartInstances.push(inst);
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
        const price = item.data.price;
        const col = item.colorFn(item.data);
        title.textContent = item.name + ' \u2014 Detaljer';
        body.innerHTML = `
          <div style="margin-bottom:8px"><strong>Napris:</strong> ${price ? price.toFixed(price > 100 ? 2 : 5) : '-'}</div>
          <div style="margin-bottom:8px"><strong>1-dags endring:</strong> ${trendArrow(item.data.chg1d)}</div>
          <div style="margin-bottom:8px"><strong>5-dagers endring:</strong> ${trendArrow(item.data.chg5d)}</div>
          <div style="margin-bottom:8px"><strong>20-dagers endring:</strong> ${trendArrow(item.data.chg20d)}</div>
          <div style="margin-bottom:8px"><strong>Regime:</strong> <span class="${col}" style="font-weight:600">${col.toUpperCase()}</span></div>
          <div style="color:var(--m)">${item.desc}</div>`;
        dd.style.display = 'block';
      }
    });
  }

  // ── Rate & Credit panel ───────────────────────────────────
  const mi = m.macro_indicators || {};
  const rc = [
    { name: '10Y rente', val: mi.TNX ? mi.TNX.price.toFixed(2) + '%' : '-', col: inp.yield_curve != null && inp.yield_curve < 0 ? 'bear' : 'bull', chg5d: mi.TNX ? mi.TNX.chg5d : null, price: mi.TNX ? mi.TNX.price : null },
    { name: '3M rente', val: mi.IRX ? mi.IRX.price.toFixed(2) + '%' : '-', col: 'neutral', chg5d: mi.IRX ? mi.IRX.chg5d : null, price: mi.IRX ? mi.IRX.price : null },
    { name: 'Rentekurve', val: ycTxt, col: ycCol, chg5d: null, price: null },
    { name: 'HY (HYG) 5d', val: mi.HYG ? formatPct(mi.HYG.chg5d) : '-', col: mi.HYG && mi.HYG.chg5d < -1.5 ? 'bear' : mi.HYG && mi.HYG.chg5d < 0 ? 'warn' : 'bull', chg5d: mi.HYG ? mi.HYG.chg5d : null, price: mi.HYG ? mi.HYG.price : null },
    { name: 'TIPS 5d', val: mi.TIP ? formatPct(mi.TIP.chg5d) : '-', col: mi.TIP && mi.TIP.chg5d > 0 ? 'bull' : 'bear', chg5d: mi.TIP ? mi.TIP.chg5d : null, price: mi.TIP ? mi.TIP.price : null },
    { name: 'Kobber 5d', val: mi.Copper ? formatPct(mi.Copper.chg5d) : '-', col: mi.Copper && mi.Copper.chg5d > 0 ? 'bull' : 'bear', chg5d: mi.Copper ? mi.Copper.chg5d : null, price: mi.Copper ? mi.Copper.price : null },
    { name: 'EM (EEM) 5d', val: mi.EEM ? formatPct(mi.EEM.chg5d) : '-', col: mi.EEM && mi.EEM.chg5d > 0 ? 'bull' : 'bear', chg5d: mi.EEM ? mi.EEM.chg5d : null, price: mi.EEM ? mi.EEM.price : null },
  ];

  const renteEl = document.getElementById('macroRente');
  if (renteEl) {
    renteEl.innerHTML = rc
      .map(
        (x, i) => {
          // Extract numeric change from value string if possible for trend arrow
          const numMatch = x.val.match(/^([+-]?\d+\.?\d*)%?$/);
          const numVal = numMatch ? parseFloat(numMatch[1]) : null;
          const arrow = numVal !== null && x.name.includes('5d') ? trendArrow(numVal) : '';
          return `<div class="card">
            <div class="ct">${x.name}</div>
            <div class="snum" style="font-size:20px">${x.val}</div>
            ${arrow ? '<div style="margin-top:4px">' + arrow + '</div>' : ''}
            <div class="slabel" style="margin-top:4px;color:var(--${x.col})">${x.col.toUpperCase()}</div>
            <div class="rate-spark" id="rateSpark${i}" style="width:100%;height:40px;margin-top:8px"></div>
          </div>`;
        }
      )
      .join('');

    // Render mini sparklines for rate & credit cards
    rc.forEach((x, i) => {
      const sparkEl = document.getElementById('rateSpark' + i);
      if (sparkEl && x.price && x.chg5d != null) {
        const data = syntheticSparkData(x.price, x.chg5d, 10);
        const color = x.col === 'bull' ? '#3fb950' : x.col === 'bear' ? '#f85149' : x.col === 'warn' ? '#d29922' : '#7d8590';
        const inst = createSparkline(sparkEl, data, color);
        chartInstances.push(inst);
      }
    });
  }

  // ── VIX Term Structure (async fetch) ─────────────────────
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
        .map((x) => `<div class="card"><div class="ct">${escapeHtml(x.name)}</div><div class="snum" style="font-size:20px;font-family:'DM Mono',monospace">${x.val}</div><div class="slabel" style="margin-top:4px;color:var(--${x.col})">${x.col.toUpperCase()}</div></div>`)
        .join('');

      // Render VIX term structure chart
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

  // ── Regime Timeline (async fetch) ───────────────────────
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

  // ── ADR Table (async fetch) ────────────────────────────
  fetchADR()
    .then((data) => {
      const adrEl = document.getElementById('adrTable');
      if (!adrEl || !data || !data.items || !data.items.length) return;
      const rows = data.items
        .map((r) => `<tr><td>${escapeHtml(r.instrument)}</td><td style="font-family:'DM Mono',monospace;text-align:right">${formatPrice(r.current_price)}</td><td style="font-family:'DM Mono',monospace;text-align:right">${r.adr > 10 ? r.adr.toFixed(1) : r.adr.toFixed(5)}</td><td style="font-family:'DM Mono',monospace;text-align:right;color:var(--${r.adr_pct > 2 ? 'bear' : r.adr_pct > 1 ? 'warn' : 'bull'})">${r.adr_pct.toFixed(2)}%</td><td style="text-align:right;color:var(--m)">${r.days_used}d</td></tr>`)
        .join('');
      adrEl.innerHTML = `<div class="cotw"><table class="cott" aria-label="ADR tabell"><thead><tr><th scope="col">Instrument</th><th scope="col" style="text-align:right">Pris</th><th scope="col" style="text-align:right">ADR</th><th scope="col" style="text-align:right">ADR%</th><th scope="col" style="text-align:right">Dager</th></tr></thead><tbody>${rows}</tbody></table></div>`;
    })
    .catch(() => {});

  // ── Conflicts section ──────────────────────────────────────
  const conflictsEl = document.getElementById('macroConflicts');
  if (conflictsEl) {
    const conflicts = m.conflicts || [];
    if (conflicts.length > 0) {
      conflictsEl.style.display = 'block';
      conflictsEl.innerHTML = `
        <div class="card" style="border-color:var(--warn);background:var(--wbg)">
          <div class="ct" style="color:var(--warn)">\u26A0 Konflikter (${conflicts.length})</div>
          <div style="font-size:12px;color:var(--t);line-height:1.8">
            ${conflicts.map((c) => `<div style="margin-bottom:4px;padding-left:12px;border-left:2px solid var(--warn)">${c}</div>`).join('')}
          </div>
        </div>`;
    } else {
      conflictsEl.style.display = 'none';
    }
  }
}
