/**
 * MacroInputsSection sub-module — Macro stats (VIX, DXY, Brent, Gold) + Rate & Credit.
 *
 * Extracted from MacroPanel.js for the 500-line limit.
 * Renders into containers created by MacroPanel.render().
 */

import { formatPct } from '../../utils.js';
import { createSparkline } from '../../charts/miniSparkline.js';
import { createPriceChart } from '../../charts/priceLineChart.js';

/** @type {{ chart: any, series: any }[]} */
const chartInstances = [];

/**
 * Trend arrow helper.
 * @param {number} val
 * @returns {string}
 */
function trendArrow(val) {
  if (val == null || val === 0) return '<span style="color:var(--m)">--</span>';
  const up = val > 0;
  return `<span style="color:var(--${up ? 'bull' : 'bear'})">${up ? '\u25B2' : '\u25BC'} ${formatPct(val)}</span>`;
}

/**
 * Generate synthetic sparkline data.
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
 * Build 1d/5d/20d change bar.
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
  return `<div class="mono" style="display:flex;gap:12px;margin-top:8px;font-size:11px">${fmt('1d', chg1d)}${fmt('5d', chg5d)}${fmt('20d', chg20d)}</div>`;
}

/**
 * Destroy all chart instances before re-render.
 */
export function destroyCharts() {
  chartInstances.forEach((inst) => {
    try {
      if (inst.chart && inst.chart.remove) inst.chart.remove();
      if (inst._ro) inst._ro.disconnect();
    } catch { /* noop */ }
  });
  chartInstances.length = 0;
}

/**
 * Build the macro stats + rate & credit skeleton.
 * @param {HTMLElement} statsSection  Macro stats section wrapper
 * @param {HTMLElement} renteSection  Rate & credit section wrapper
 */
export function render(statsSection, renteSection) {
  statsSection.innerHTML = `
    <div class="sh"><h2 class="sh-t">Makro Nøkkeltall</h2><div class="sh-b">VIX, DXY, Brent, Gull</div></div>
    <div class="g2" id="macroStats" role="group" aria-label="Makro noekkeltall"></div>`;

  renteSection.innerHTML = `
    <div class="sh" style="margin-top:16px"><h2 class="sh-t">Rente &amp; Kreditt</h2><div class="sh-b">Realrenter, spreader, vekst</div></div>
    <div class="g4" id="macroRente" role="group" aria-label="Rente og kreditt indikatorer"></div>`;
}

/**
 * Update macro stats and rate & credit panels.
 * @param {Object} m  Full macro data payload
 * @param {Function} openDrilldown  Callback to open drilldown detail
 */
export function update(m, openDrilldown) {
  if (!m) return;

  const p = m.prices || {};
  const inp = (m.dollar_smile || {}).inputs || {};

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

  destroyCharts();

  const msEl = document.getElementById('macroStats');
  if (msEl) {
    msEl.innerHTML = ms
      .map(
        (x, i) => {
          const price = x.data.price;
          const chg1d = x.data.chg1d;
          const chg5d = x.data.chg5d;
          const chg20d = x.data.chg20d;
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

    // Render price charts
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
      const price = item.data.price;
      const col = item.colorFn(item.data);
      openDrilldown(
        item.name + ' \u2014 Detaljer',
        `<div style="margin-bottom:8px"><strong>Nåpris:</strong> ${price ? price.toFixed(price > 100 ? 2 : 5) : '-'}</div>
         <div style="margin-bottom:8px"><strong>1-dags endring:</strong> ${trendArrow(item.data.chg1d)}</div>
         <div style="margin-bottom:8px"><strong>5-dagers endring:</strong> ${trendArrow(item.data.chg5d)}</div>
         <div style="margin-bottom:8px"><strong>20-dagers endring:</strong> ${trendArrow(item.data.chg20d)}</div>
         <div style="margin-bottom:8px"><strong>Regime:</strong> <span class="${col}" style="font-weight:600">${col.toUpperCase()}</span></div>
         <div style="color:var(--m)">${item.desc}</div>`
      );
    });
  }

  // Rate & Credit
  const ycTxt =
    inp.yield_curve != null
      ? (inp.yield_curve > 0 ? '+' : '') + inp.yield_curve.toFixed(2) + '%'
      : '-';
  const ycCol =
    inp.yield_curve == null ? 'neutral' : inp.yield_curve < -0.3 ? 'bear' : inp.yield_curve < 0.3 ? 'warn' : 'bull';

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

    // Render sparklines
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
}
