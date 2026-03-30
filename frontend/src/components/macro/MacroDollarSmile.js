/**
 * MacroDollarSmile sub-module — Dollar Smile model, inputs, safe-haven hierarchy, ADR table.
 *
 * Extracted from MacroPanel.js for the 500-line limit.
 * Renders into containers created by MacroPanel.render().
 */

import { formatPct, escapeHtml, formatPrice } from '../../utils.js';
import { fetchADR } from '../../api.js';

/**
 * Build the Dollar Smile + safe-haven + ADR skeleton.
 * Called once by MacroPanel.render().
 * @param {HTMLElement} smileContainer  Left column of the g21 grid
 * @param {HTMLElement} safeContainer   Safe-haven card wrapper
 * @param {HTMLElement} adrSection      ADR section wrapper
 */
export function render(smileContainer, safeContainer, adrSection) {
  smileContainer.innerHTML = `
    <div class="ct">Dollar-smil modell</div>
    <div class="smile" id="smile" role="img" aria-label="Dollar-smil posisjon"></div>
    <div style="font-size:13px;color:var(--m)" id="smileDesc" aria-live="polite"></div>
    <div class="sinp" id="smileInp" role="group" aria-label="Makro-indikatorer"></div>`;

  safeContainer.innerHTML = `
    <div class="ct">Safe-haven hierarki</div>
    <div id="safeH" style="font-size:13px;line-height:1.8;color:var(--m)" aria-live="polite"></div>`;

  adrSection.innerHTML = `
    <div class="sh" style="margin-top:16px"><h2 class="sh-t">Sesjonsrekkevidde (ADR)</h2><div class="sh-b">20-dagers gjennomsnittlig daglig rekkevidde</div></div>
    <div id="adrTable" role="region" aria-label="ADR tabell"></div>`;
}

/**
 * Update Dollar Smile, safe-haven, and ADR with fresh macro data.
 * @param {Object} m  Full macro data payload
 */
export function update(m) {
  if (!m) return;

  const sm = m.dollar_smile || {};
  const inp = sm.inputs || {};

  // Dollar Smile segments
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

  // Smile description
  const descEl = document.getElementById('smileDesc');
  if (descEl) {
    const bc = sm.usd_color === 'bull' ? 'var(--bull)' : 'var(--bear)';
    descEl.innerHTML = `<strong style="color:${bc}">USD ${sm.usd_bias || ''}</strong> - ${sm.desc || ''}`;
  }

  // Smile inputs
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

  // Safe-haven hierarchy
  const riskOff = inp.vix > 20 || inp.hy_stress || (inp.yield_curve != null && inp.yield_curve < -0.3);
  const safeEl = document.getElementById('safeH');
  if (safeEl) {
    safeEl.innerHTML = riskOff
      ? '<strong style="color:var(--bear)">Risk-off aktiv</strong><br>Kjop: USD, XAU, CHF, JPY<br>Selg: NOK, AUD, NZD, CAD'
      : '<strong style="color:var(--bull)">Normalt marked</strong><br>Carry: AUD, NZD, CAD, NOK';
  }

  // ADR Table (async fetch)
  fetchADR()
    .then((data) => {
      const adrEl = document.getElementById('adrTable');
      if (!adrEl || !data || !data.items || !data.items.length) return;
      const rows = data.items
        .map((r) => `<tr><td>${escapeHtml(r.instrument)}</td><td class="data-value" style="text-align:right">${formatPrice(r.current_price)}</td><td class="data-value" style="text-align:right">${r.adr > 10 ? r.adr.toFixed(1) : r.adr.toFixed(5)}</td><td class="data-value" style="text-align:right;color:var(--${r.adr_pct > 2 ? 'bear' : r.adr_pct > 1 ? 'warn' : 'bull'})">${r.adr_pct.toFixed(2)}%</td><td style="text-align:right;color:var(--m)">${r.days_used}d</td></tr>`)
        .join('');
      adrEl.innerHTML = `<div class="cotw"><table class="cott" aria-label="ADR tabell"><thead><tr><th scope="col">Instrument</th><th scope="col" style="text-align:right">Pris</th><th scope="col" style="text-align:right">ADR</th><th scope="col" style="text-align:right">ADR%</th><th scope="col" style="text-align:right">Dager</th></tr></thead><tbody>${rows}</tbody></table></div>`;
    })
    .catch(() => {});
}
