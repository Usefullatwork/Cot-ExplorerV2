/**
 * MacroPanel component — Dollar Smile, VIX regime, macro stats, rates & credit.
 *
 * Ports the renderMakro function from v1 index.html.
 */

import { formatPct } from '../utils.js';

/**
 * Build the static DOM skeleton inside the macro panel.
 * @param {HTMLElement} container  #panel-macro
 */
export function render(container) {
  container.innerHTML = `
    <div class="g21">
      <div class="card">
        <div class="ct">Dollar-smil modell</div>
        <div class="smile" id="smile"></div>
        <div style="font-size:13px;color:var(--m)" id="smileDesc"></div>
        <div class="sinp" id="smileInp"></div>
      </div>
      <div>
        <div class="card" style="margin-bottom:12px">
          <div class="ct">VIX-regime</div>
          <div id="vixDet"></div>
          <div style="margin-top:12px;font-size:12px;color:var(--m);line-height:2">
            Under 20 - Full storrelse<br>
            20-30 - Halv storrelse<br>
            Over 30 - Kvart storrelse
          </div>
        </div>
        <div class="card">
          <div class="ct">Safe-haven hierarki</div>
          <div id="safeH" style="font-size:13px;line-height:1.8;color:var(--m)"></div>
        </div>
      </div>
    </div>
    <div class="g4" id="macroStats"></div>
    <div class="sh" style="margin-top:16px"><div class="sh-t">Rente &amp; Kreditt</div><div class="sh-b">Realrenter, spreader, vekst</div></div>
    <div class="g4" id="macroRente"></div>`;
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

  // ── Macro stats (VIX, DXY, Brent, Gold) ───────────────────
  const ms = [
    ['VIX', (p.VIX || {}).price, (p.VIX || {}).chg5d || 0, (p.VIX || {}).chg5d > 0 ? 'bear' : 'bull'],
    ['DXY', (p.DXY || {}).price, (p.DXY || {}).chg5d || 0, (p.DXY || {}).chg5d > 0 ? 'bull' : 'bear'],
    ['Brent', (p.Brent || {}).price, (p.Brent || {}).chg5d || 0, 'warn'],
    ['Gull', (p.Gold || {}).price, (p.Gold || {}).chg5d || 0, (p.Gold || {}).chg5d > 0 ? 'bull' : 'bear'],
  ];

  const msEl = document.getElementById('macroStats');
  if (msEl) {
    msEl.innerHTML = ms
      .map(
        (x) =>
          `<div class="card"><div class="ct">${x[0]}</div><div class="snum">${x[1] ? x[1].toFixed(x[1] > 100 ? 0 : 2) : '-'}</div><div class="slabel" style="margin-top:4px;color:var(--${x[3]})">${formatPct(x[2])} (5d)</div></div>`
      )
      .join('');
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
        (x) =>
          `<div class="card"><div class="ct">${x[0]}</div><div class="snum" style="font-size:20px">${x[1]}</div><div class="slabel" style="margin-top:4px;color:var(--${x[2]})">${x[2].toUpperCase()}</div></div>`
      )
      .join('');
  }
}
