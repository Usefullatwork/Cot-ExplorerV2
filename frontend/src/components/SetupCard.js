/**
 * SetupCard component — expandable instrument card showing trading setup details.
 *
 * Ports the renderIdeer / renderSetupSide logic from v1 index.html.
 * Each card has a header row (always visible) and a detail panel (toggled on click).
 */

import { formatNumber, formatPct, colorClass, formatPrice } from '../utils.js';
import { renderSparkline } from '../charts/svgSparkline.js';

// ── Helpers ─────────────────────────────────────────────────

function weightBadge(w) {
  if (!w) return '';
  const label = w >= 5 ? 'Ukentlig' : w >= 4 ? 'PDH/PDL' : w >= 3 ? 'D1' : w >= 2 ? '4H/SMC' : '15m';
  const cls = w >= 4 ? 'bull' : w >= 3 ? 'warn' : 'neutral';
  return `<span class="tf-badge ${cls}">${label}</span>`;
}

function renderSetupSide(setup, type) {
  if (!setup) {
    return `<div class="setup-label na">${type}</div>
      <div style="color:var(--m);font-size:12px;padding:20px 0;text-align:center">Ikke tilgjengelig</div>`;
  }

  const col = type === 'LONG' ? 'bull' : 'bear';
  const rrOk = setup.rr_t1 >= setup.min_rr;
  const distOk = setup.entry_dist_atr <= 1.0;
  const entryW = setup.entry_weight || 1;
  const t1W = setup.t1_weight || 1;

  return `
    <div class="setup-label ${col}">${type} - ${setup.entry_name} ${weightBadge(entryW)}</div>
    <div class="setup-row"><span class="setup-key">Entry</span><span class="setup-val ${distOk ? col : 'warn'}">${formatPrice(setup.entry)}${distOk ? ' *' : ' (' + setup.entry_dist_atr + 'xATR)'}</span></div>
    <div class="setup-row"><span class="setup-key">Stop Loss</span><span class="setup-val bear">${formatPrice(setup.sl)}<span style="font-size:10px;color:var(--m);margin-left:6px">${setup.sl_type || ''}${setup.risk_atr_d ? ' · ' + setup.risk_atr_d + 'xATRd' : ''}</span></span></div>
    <div class="setup-row"><span class="setup-key">Target 1</span><span class="setup-val bull">${formatPrice(setup.t1)} ${weightBadge(t1W)}${setup.t1_quality === 'weak' ? '<span class="tf-badge neutral" title="Svak T1">?</span>' : ''}</span></div>
    <div class="setup-row"><span class="setup-key">Target 2</span><span class="setup-val bull">${formatPrice(setup.t2)}</span></div>
    <div class="setup-row"><span class="setup-key">R:R T1</span><span class="rr-badge ${rrOk ? 'ok' : 'bad'}">1:${setup.rr_t1}</span></div>
    <div class="setup-row"><span class="setup-key">R:R T2</span><span class="setup-val">1:${setup.rr_t2}</span></div>
    <div class="setup-row"><span class="setup-key">Min R:R</span><span class="setup-val">1:${setup.min_rr}</span></div>
    <div style="font-size:11px;color:var(--m);margin-top:8px">${setup.note || ''}</div>`;
}

function makeLevelRow(l, type) {
  const act = l.dist_atr <= 1.0;
  const cls = act ? (type === 'res' ? 'ar' : 'as') : '';
  const lvlF = l.level > 100 ? l.level.toFixed(1) : l.level.toFixed(5);
  return `<div class="lr ${cls}"><span class="ln">${l.name}${act ? ' *' : ''} ${weightBadge(l.weight || 1)}</span><span><span class="lv">${lvlF}</span> <span class="ld">${l.dist_atr.toFixed(1)}x</span></span></div>`;
}

// ── Public API ──────────────────────────────────────────────

/**
 * Render a single SetupCard.
 * @param {Object} lv        Instrument/signal data object
 * @param {number} idx       Index for unique DOM IDs
 * @returns {string}         HTML string
 */
export function renderCard(lv, idx) {
  const cot = lv.cot || {};
  const gc = lv.grade_color || 'neutral';
  const sess = lv.session || {};
  const brisk = lv.binary_risk || [];
  const clsLv = lv.class || 'A';
  const curr = lv.current || 0;
  const specNet = cot.net || 0;
  const pct = Math.min(100, Math.max(0, 50 + (specNet / Math.max(1, lv.open_interest || 1e6)) * 50));
  const res = lv.resistances || [];
  const sup = lv.supports || [];
  const smaPos = lv.sma200_pos === 'over';
  const smaFmt = lv.sma200 ? formatPrice(lv.sma200) : '-';
  const atrFmt = lv.atr14 ? (lv.atr14 > 10 ? lv.atr14.toFixed(1) : lv.atr14.toFixed(5)) : '-';
  const biasText = lv.dir_color === 'bull' ? 'LONG' : lv.dir_color === 'bear' ? 'SHORT' : 'NOYTRAL';
  const tf = lv.timeframe_bias || 'WATCHLIST';
  const tfCol = tf === 'MAKRO' ? 'bull' : tf === 'SWING' ? 'warn' : tf === 'SCALP' ? 'neutral' : 'bear';

  const resH = res.slice(0, 3).map((l) => makeLevelRow(l, 'res')).join('');
  const supH = sup.slice(0, 3).map((l) => makeLevelRow(l, 'sup')).join('');

  // Score dots
  const scoreDots = (lv.score_details || [])
    .map((sd) => `<div class="score-item"><div class="score-dot" style="background:${sd.verdi ? 'var(--bull)' : 'var(--b2)'}"></div>${sd.kryss}</div>`)
    .join('');

  // Binary risk warning
  const briskHtml = brisk.length
    ? `<div class="binrisk" role="alert" aria-label="Binar risiko advarsel">Binar risiko: ${brisk.map((r) => r.title).join(', ')}</div>`
    : '';

  const scoreColor = gc === 'bull' ? 'var(--bull)' : gc === 'warn' ? 'var(--warn)' : 'var(--bear)';

  return `
    <div class="tic" role="article" aria-label="${lv.name} ${lv.grade} setup">
      <div class="tic-head" data-idx="${idx}" role="button" tabindex="0" aria-expanded="false" aria-controls="tdet${idx}" aria-label="Vis detaljer for ${lv.name}: ${lv.grade} ${biasText} ${formatPrice(curr)}">
        <span class="tcls" aria-label="Klasse ${clsLv}">${clsLv}</span>
        <div><div class="tname">${lv.name}</div><div class="tsub">${lv.label || ''}</div></div>
        <span class="tgrade ${gc}" aria-label="Grade ${lv.grade}, score ${lv.score} av 8">${lv.grade} ${lv.score}/8</span>
        <span class="tgrade ${tfCol}" aria-label="Tidsramme ${tf}">${tf}</span>
        <span class="tbias ${lv.dir_color || 'neutral'}" aria-label="Retning ${biasText}">${biasText}</span>
        <span class="tprice" aria-label="Pris ${formatPrice(curr)}">${formatPrice(curr)}</span>
        <span class="tsess ${sess.active ? 'active' : 'inactive'}" aria-label="${sess.active ? 'Aktiv sesjon' : sess.label || 'Utenfor sesjon'}">${sess.active ? 'AKTIV SESJON' : sess.label || 'Utenfor sesjon'}</span>
        ${brisk.length ? '<span class="trisk" role="alert">BINAR RISIKO</span>' : ''}
      </div>
      <div id="tdet${idx}" class="tdet" role="region" aria-label="Detaljer for ${lv.name}">
        ${briskHtml}
        <div class="setup-grid">
          <div class="setup-side">${renderSetupSide(lv.setup_long, 'LONG')}</div>
          <div class="setup-side">${renderSetupSide(lv.setup_short, 'SHORT')}</div>
        </div>
        <div class="score-section">
          <div class="ct">Konfluens-score (${lv.score_pct || 0}%)</div>
          <div class="score-bar-wrap"><div class="score-bar"><div class="score-fill" style="width:${lv.score_pct || 0}%;background:${scoreColor}"></div></div></div>
          <div class="score-items">${scoreDots}</div>
        </div>
        <div class="levels-section">
          <div><div class="lgt">Motstand</div>${resH}</div>
          <div>
            <div class="pline"><span class="pcurr">${formatPrice(curr)}</span><span class="pm">Nåpris</span><span class="psma ${smaPos ? 'above' : 'below'}">SMA200 ${smaPos ? 'Over' : 'Under'}</span></div>
            <div style="margin-top:8px"><div class="lgt">Støtte</div>${supH}</div>
          </div>
          <div><div class="lgt">Nøkkeltall</div>
            <div class="lr"><span class="ln">SMA200</span><span class="lv">${smaFmt}</span></div>
            <div class="lr"><span class="ln">ATR14</span><span class="lv">${atrFmt}</span></div>
            <div class="lr"><span class="ln">5d</span><span class="lv ${colorClass(lv.chg5d || 0)}">${formatPct(lv.chg5d || 0)}</span></div>
            <div class="lr"><span class="ln">20d</span><span class="lv ${colorClass(lv.chg20d || 0)}">${formatPct(lv.chg20d || 0)}</span></div>
          </div>
        </div>
        <div class="tmeta">
          <div><div class="ml">COT Bias</div><div class="mv ${cot.color || 'neutral'}">${cot.bias || '-'}</div></div>
          <div><div class="ml">COT Trend</div><div class="mv ${cot.momentum === 'OKER' ? 'bull' : cot.momentum === 'SNUR' ? 'warn' : 'neutral'}">${cot.momentum || '-'}</div></div>
          <div><div class="ml">DXY</div><div class="mv ${lv.dxy_conf === 'medvind' ? 'bull' : 'bear'}">${lv.dxy_conf || '-'}</div></div>
          <div><div class="ml">Posisjon</div><div class="mv warn">${lv.pos_size || '-'}</div></div>
          <div><div class="ml">Spread-faktor</div><div class="mv">${lv.vix_spread_factor || '-'}x</div></div>
        </div>
        <div class="tcotbar">
          <div class="ct">COT Spekulanter (${cot.report || '-'} per ${cot.date || '-'})</div>
          <div style="display:flex;justify-content:space-between;font-size:12px;margin-bottom:6px">
            <span>Netto: <strong class="${cot.color || 'neutral'}" style="font-family:monospace">${specNet > 0 ? '+' : ''}${formatNumber(specNet)}</strong></span>
            <span>Uke: <strong class="${colorClass(cot.chg || 0)}" style="font-family:monospace">${(cot.chg || 0) > 0 ? '+' : ''}${formatNumber(cot.chg || 0)}</strong></span>
            <span>OI: <strong style="font-family:monospace">${(cot.pct || 0).toFixed(1)}%</strong></span>
          </div>
          <div class="cbt"><div class="cbf" style="width:${pct}%;background:${specNet > 0 ? 'var(--bull)' : 'var(--bear)'}"></div></div>
          ${cot.history && cot.history.length > 1 ? '<div style="margin-top:8px;text-align:center" aria-label="COT historikk sparkline">' + renderSparkline(cot.history, { width: 120, height: 24 }) + '</div>' : ''}
        </div>
      </div>
    </div>`;
}

/**
 * Attach toggle listeners for expand/collapse.
 * Call after inserting SetupCard HTML into the DOM.
 * @param {HTMLElement} container  The parent that holds all .tic elements
 */
export function attachToggle(container) {
  function toggle(head) {
    const idx = head.dataset.idx;
    const det = document.getElementById('tdet' + idx);
    if (!det) return;

    const wasOpen = det.classList.contains('open');
    // Close all open detail panels and reset ARIA
    container.querySelectorAll('.tdet.open').forEach((el) => el.classList.remove('open'));
    container.querySelectorAll('.tic-head').forEach((h) => h.setAttribute('aria-expanded', 'false'));

    if (!wasOpen) {
      det.classList.add('open');
      head.setAttribute('aria-expanded', 'true');
    }
  }

  // Click handler
  container.addEventListener('click', (e) => {
    const head = e.target.closest('.tic-head');
    if (!head) return;
    toggle(head);
  });

  // Keyboard: Enter/Space to toggle
  container.addEventListener('keydown', (e) => {
    if (e.key === 'Enter' || e.key === ' ') {
      const head = e.target.closest('.tic-head');
      if (!head) return;
      e.preventDefault();
      toggle(head);
    }
  });
}
