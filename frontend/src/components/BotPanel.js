/**
 * BotPanel component — Trading bot dashboard with 7 sections:
 * status, positions, signals, daily P&L, kill switch, config, trade log.
 * Follows MacroPanel.js pattern: render() builds skeleton, update() fills data.
 */
import { formatPrice, timeAgo, escapeHtml } from '../utils.js';
import { createPnlChart, destroyPnlChart } from '../charts/pnlChart.js';
import {
  fetchBotStatus, fetchBotPositions, fetchBotSignals,
  fetchBotHistory, fetchBotConfig, updateBotConfig,
  invalidateBot, startBot, stopBot,
} from '../api.js';

/* ── Helpers ─────────────────────────────────────────────── */

function pnlColor(v) { return v > 0 ? 'bull' : v < 0 ? 'bear' : ''; }

function fmtPnl(v) {
  if (v == null) return '-';
  return `${v >= 0 ? '+' : ''}$${v.toFixed(2)}`;
}

function fmtPips(v) {
  if (v == null) return '-';
  return `${v >= 0 ? '+' : ''}${v.toFixed(1)}`;
}

function statusBadge(status) {
  const c = { running: 'bull', stopped: 'bear', starting: 'warn' };
  const l = { running: 'Aktiv', stopped: 'Stoppet', starting: 'Starter' };
  return `<span class="tgrade ${c[status] || 'warn'}">${escapeHtml(l[status] || status)}</span>`;
}

function modeBadge(mode) {
  const c = { paper: 'neutral', live: 'bear', demo: 'warn' };
  return `<span class="tbias ${c[mode] || 'neutral'}">${escapeHtml((mode || 'paper').toUpperCase())}</span>`;
}

function cfgField(label, id, html) {
  return `<div><label class="bot-label">${label}</label>${html}</div>`;
}

/* ── Render (skeleton) ───────────────────────────────────── */

/** @param {HTMLElement} container  #panel-trading */
export function render(container) {
  container.innerHTML = `
    <div class="card" id="botStatusBanner" role="region" aria-label="Bot-status" style="margin-bottom:12px">
      <div class="ct">Bot-status</div>
      <div id="botStatusBody" style="font-size:13px;color:var(--m);line-height:1.8" aria-live="polite">Laster status...</div>
    </div>
    <div class="sh"><h2 class="sh-t">Aktive Posisjoner</h2><div class="sh-b" id="posCount">0</div></div>
    <div class="cotw" style="margin-bottom:18px;overflow-x:auto">
      <table class="cott"><thead><tr>
        <th>Instrument</th><th>Retning</th><th>Inngang</th><th>Nåpris</th>
        <th class="tdr">P&L (pips)</th><th class="tdr">P&L ($)</th>
        <th class="tdr">Lots</th><th class="tdr">Candles</th><th>T1</th><th>Status</th>
      </tr></thead><tbody id="positionsBody"><tr><td colspan="10" style="color:var(--m);text-align:center">Ingen posisjoner</td></tr></tbody></table>
    </div>
    <div class="sh"><h2 class="sh-t">Signalkoe</h2><div class="sh-b" id="sigCount">0</div></div>
    <div class="cotw" style="margin-bottom:18px;overflow-x:auto">
      <table class="cott"><thead><tr>
        <th>Instrument</th><th>Retning</th><th>Grade</th><th class="tdr">Score</th>
        <th>Inngangszone</th><th>Status</th><th>Mottatt</th>
      </tr></thead><tbody id="signalsBody"><tr><td colspan="7" style="color:var(--m);text-align:center">Ingen signaler</td></tr></tbody></table>
    </div>
    <div class="sh"><h2 class="sh-t">Daglig P&L</h2><div class="sh-b">Oppsummering</div></div>
    <div class="g4" id="pnlStats" style="margin-bottom:12px" role="group" aria-label="Daglig P&L statistikk">
      <div class="card"><div class="ct">Dagens P&L</div><div class="snum" id="pnlToday">-</div></div>
      <div class="card"><div class="ct">Antall trades</div><div class="snum" id="pnlTrades">-</div></div>
      <div class="card"><div class="ct">Win Rate</div><div class="snum" id="pnlWinRate">-</div></div>
      <div class="card"><div class="ct">Beste / Dårligste</div><div id="pnlBestWorst" style="font-size:13px;color:var(--m);margin-top:8px">-</div></div>
    </div>
    <div class="card" style="margin-bottom:18px" role="region" aria-label="P&L-kurve">
      <div class="ct">Equity-kurve</div>
      <div style="height:220px;position:relative"><canvas id="pnlCanvas" aria-hidden="true"></canvas></div>
    </div>
    <div class="sh"><h2 class="sh-t">Kill Switch</h2></div>
    <div class="card" style="margin-bottom:18px" id="killSwitchCard" role="region" aria-label="Kill switch">
      <div style="display:flex;align-items:center;gap:16px;flex-wrap:wrap">
        <button id="killSwitchBtn" class="fc" style="background:var(--rbg);border-color:var(--bear);color:var(--bear);font-size:13px;font-weight:700;padding:10px 24px;border-radius:6px;cursor:pointer">KILL SWITCH</button>
        <div id="killSwitchStatus" style="font-size:12px;color:var(--m)" aria-live="polite">Status: Inaktiv</div>
      </div>
      <div id="killConfirmDialog" style="display:none;margin-top:12px;padding:12px;background:var(--s2);border:1px solid var(--bear);border-radius:6px">
        <div style="font-size:13px;color:var(--bear);margin-bottom:8px;font-weight:600">Bekreft: Steng alle posisjoner og stopp bot?</div>
        <div style="display:flex;gap:8px">
          <button id="killConfirmYes" class="fc" style="background:var(--rbg);border-color:var(--bear);color:var(--bear);padding:6px 16px">Ja, stopp alt</button>
          <button id="killConfirmNo" class="fc" style="padding:6px 16px">Avbryt</button>
        </div>
      </div>
    </div>
    <div class="sh"><h2 class="sh-t">Konfigurasjon</h2></div>
    <div class="card" style="margin-bottom:18px" id="configCard" role="region" aria-label="Bot-konfigurasjon">
      <div class="g2" id="configBody" style="gap:12px">
        ${cfgField('Bot aktiv', 'cfgActive', `<select id="cfgActive" class="bot-input"><option value="true">Pa</option><option value="false">Av</option></select>`)}
        ${cfgField('Megler-modus', 'cfgMode', `<select id="cfgMode" class="bot-input"><option value="paper">Paper</option><option value="demo">Demo</option><option value="live">Live</option></select>`)}
        ${cfgField('Maks posisjoner', 'cfgMaxPos', `<input id="cfgMaxPos" type="number" min="1" max="20" value="5" class="bot-input">`)}
        ${cfgField('Risiko %', 'cfgRisk', `<input id="cfgRisk" type="number" min="0.1" max="5" step="0.1" value="1.0" class="bot-input">`)}
        ${cfgField('Min. grade', 'cfgMinGrade', `<select id="cfgMinGrade" class="bot-input"><option value="A+">A+</option><option value="A">A</option><option value="B" selected>B</option><option value="C">C</option></select>`)}
        ${cfgField('Min. score', 'cfgMinScore', `<input id="cfgMinScore" type="number" min="1" max="8" step="1" value="5" class="bot-input">`)}
      </div>
      <div style="margin-top:12px;display:flex;gap:8px;align-items:center">
        <button id="cfgSaveBtn" class="fc" style="background:var(--bbg);border-color:var(--bull);color:var(--bull);padding:8px 20px;font-size:12px;font-weight:600">Lagre</button>
        <span id="cfgSaveMsg" style="font-size:11px;color:var(--m)" aria-live="polite"></span>
      </div>
    </div>
    <div class="sh" style="margin-top:16px"><h2 class="sh-t">Posisjonskalkulator</h2><div class="sh-b">Beregn lot-størrelse</div></div>
    <div class="card" style="margin-bottom:18px" id="posCalcCard" role="region" aria-label="Posisjonskalkulator">
      <div class="g2" style="gap:12px">
        ${cfgField('Balanse (USD)', 'calcBalance', `<input id="calcBalance" type="number" min="100" value="10000" class="bot-input">`)}
        ${cfgField('Risiko %', 'calcRisk', `<input id="calcRisk" type="number" min="0.1" max="10" step="0.1" value="1.0" class="bot-input">`)}
        ${cfgField('Instrument', 'calcInst', `<select id="calcInst" class="bot-input"><option value="EURUSD">EUR/USD</option><option value="GBPUSD">GBP/USD</option><option value="USDJPY">USD/JPY</option><option value="AUDUSD">AUD/USD</option><option value="Gold">Gull</option><option value="Brent">Brent</option><option value="SPX">S&P 500</option><option value="NAS100">Nasdaq</option></select>`)}
        ${cfgField('SL distanse (pips)', 'calcSL', `<input id="calcSL" type="number" min="1" value="30" class="bot-input">`)}
        ${cfgField('VIX', 'calcVix', `<input id="calcVix" type="number" min="0" step="0.1" value="15.0" class="bot-input">`)}
        ${cfgField('Grade', 'calcGrade', `<select id="calcGrade" class="bot-input"><option value="A+">A+</option><option value="A" selected>A</option><option value="B">B</option><option value="C">C</option></select>`)}
      </div>
      <div style="margin-top:12px;display:flex;gap:8px;align-items:center">
        <button id="calcSizeBtn" class="fc" style="background:var(--bbg);border-color:var(--bull);color:var(--bull);padding:8px 20px;font-size:12px;font-weight:600">Beregn</button>
      </div>
      <div id="calcResult" style="margin-top:12px;font-size:13px;color:var(--m);display:none" aria-live="polite"></div>
    </div>
    <div class="sh"><h2 class="sh-t">Handelslogg</h2><div class="sh-b">Siste hendelser</div></div>
    <div class="cotw" style="overflow-x:auto">
      <table class="cott"><thead><tr><th>Tid</th><th>Hendelse</th><th>Instrument</th><th>Detaljer</th></tr></thead>
      <tbody id="tradeLogBody"><tr><td colspan="4" style="color:var(--m);text-align:center">Ingen hendelser</td></tr></tbody></table>
    </div>`;

  wireKillSwitch();
  wireConfigSave();
  wireBotToggle();
  wirePositionCalc();
}

/* ── Event wiring ────────────────────────────────────────── */

function wireKillSwitch() {
  const btn = document.getElementById('killSwitchBtn');
  const dialog = document.getElementById('killConfirmDialog');
  const yes = document.getElementById('killConfirmYes');
  const no = document.getElementById('killConfirmNo');
  if (!btn || !dialog || !yes || !no) return;

  btn.addEventListener('click', () => { dialog.style.display = 'block'; });
  no.addEventListener('click', () => { dialog.style.display = 'none'; });
  yes.addEventListener('click', async () => {
    dialog.style.display = 'none';
    const el = document.getElementById('killSwitchStatus');
    try {
      await invalidateBot('Manual kill switch activated');
      if (el) el.innerHTML = '<span style="color:var(--bear);font-weight:600">AKTIVERT</span> — Alle posisjoner stengt';
    } catch (err) {
      if (el) el.textContent = 'Feil: ' + (err.message || 'Ukjent feil');
    }
  });
}

function wireConfigSave() {
  const btn = document.getElementById('cfgSaveBtn');
  if (!btn) return;
  btn.addEventListener('click', async () => {
    const msg = document.getElementById('cfgSaveMsg');
    const config = {
      active: document.getElementById('cfgActive')?.value === 'true',
      broker_mode: document.getElementById('cfgMode')?.value || 'paper',
      max_positions: parseInt(document.getElementById('cfgMaxPos')?.value || '5', 10),
      risk_pct: parseFloat(document.getElementById('cfgRisk')?.value || '1.0'),
      min_grade: document.getElementById('cfgMinGrade')?.value || 'B',
      min_score: parseInt(document.getElementById('cfgMinScore')?.value || '5', 10),
    };
    try {
      await updateBotConfig(config);
      if (msg) { msg.style.color = 'var(--bull)'; msg.textContent = 'Lagret!'; }
      setTimeout(() => { if (msg) msg.textContent = ''; }, 3000);
    } catch (err) {
      if (msg) { msg.style.color = 'var(--bear)'; msg.textContent = 'Feil: ' + (err.message || 'Ukjent'); }
    }
  });
}

function wireBotToggle() {
  document.getElementById('botStatusBanner')?.addEventListener('click', async (e) => {
    const btn = e.target.closest('#botStartBtn, #botStopBtn');
    if (!btn) return;
    try {
      if (btn.id === 'botStartBtn') await startBot(); else await stopBot();
      await refreshAll();
    } catch (err) { console.error('[BotPanel] Toggle error:', err); }
  });
}

/* ── Update (data) ───────────────────────────────────────── */

/** @param {Object} data  { status, positions, signals, config, history, pnl } */
export function update(data) {
  if (!data) return;
  if (data.status) updateStatus(data.status);
  if (data.positions) updatePositions(data.positions);
  if (data.signals) updateSignals(data.signals);
  if (data.pnl) updatePnl(data.pnl);
  if (data.config) updateConfig(data.config);
  if (data.history) updateLog(data.history);
}

function updateStatus(s) {
  const el = document.getElementById('botStatusBody');
  if (!el) return;
  const status = s.status || 'stopped';
  const since = s.connected_since ? timeAgo(s.connected_since) : '-';
  const toggleBtn = status === 'stopped'
    ? '<button id="botStartBtn" class="fc" style="background:var(--bbg);border-color:var(--bull);color:var(--bull);padding:4px 12px;font-size:11px">Start</button>'
    : '<button id="botStopBtn" class="fc" style="background:var(--rbg);border-color:var(--bear);color:var(--bear);padding:4px 12px;font-size:11px">Stopp</button>';
  el.innerHTML = `<div style="display:flex;gap:16px;align-items:center;flex-wrap:wrap">
    ${statusBadge(status)} ${modeBadge(s.broker_mode || 'paper')}
    <span style="font-size:11px;color:var(--m)">Tilkoblet: ${escapeHtml(since)}</span>
    <span style="font-size:11px;color:var(--m)">Posisjoner: <strong>${escapeHtml(s.positions_count ?? 0)}</strong></span>
    ${toggleBtn}</div>`;
}

function updatePositions(positions) {
  const body = document.getElementById('positionsBody');
  const count = document.getElementById('posCount');
  if (!body) return;
  const arr = Array.isArray(positions) ? positions : [];
  if (count) count.textContent = String(arr.length);
  if (!arr.length) { body.innerHTML = '<tr><td colspan="10"><div class="empty-state" style="padding:20px 12px"><div class="empty-state-icon">\uD83D\uDCC2</div><div class="empty-state-title">Ingen åpne posisjoner</div><div class="empty-state-text">Boten har ingen aktive trades. Nye posisjoner åpnes når signaler oppfyller filtrene.</div></div></td></tr>'; return; }
  body.innerHTML = arr.map((p) => {
    const dirCol = p.direction === 'LONG' ? 'bull' : 'bear';
    return `<tr>
      <td class="tdname">${escapeHtml(p.instrument || '-')}</td>
      <td><span class="tbias ${dirCol}" style="font-size:10px">${escapeHtml(p.direction || '-')}</span></td>
      <td class="tdr">${escapeHtml(formatPrice(p.entry))}</td><td class="tdr">${escapeHtml(formatPrice(p.current))}</td>
      <td class="td${pnlColor(p.pnl_pips)}" style="text-align:right">${escapeHtml(fmtPips(p.pnl_pips))}</td>
      <td class="td${pnlColor(p.pnl_usd)}" style="text-align:right">${escapeHtml(fmtPnl(p.pnl_usd))}</td>
      <td class="tdr">${escapeHtml(p.lots ?? '-')}</td><td class="tdr">${escapeHtml(p.candles ?? '-')}</td>
      <td>${p.t1_hit ? '<span style="color:var(--bull)">Ja</span>' : '<span style="color:var(--m)">Nei</span>'}</td>
      <td><span class="tsess ${p.status === 'active' ? 'active' : 'inactive'}">${escapeHtml(p.status || '-')}</span></td></tr>`;
  }).join('');
}

function updateSignals(signals) {
  const body = document.getElementById('signalsBody');
  const count = document.getElementById('sigCount');
  if (!body) return;
  const arr = Array.isArray(signals) ? signals : [];
  if (count) count.textContent = String(arr.length);
  if (!arr.length) { body.innerHTML = '<tr><td colspan="7"><div class="empty-state" style="padding:20px 12px"><div class="empty-state-icon">\uD83D\uDCE1</div><div class="empty-state-title">Ingen signaler i køen</div><div class="empty-state-text">Signaler genereres av analysemotoren. Kjør <code>python fetch_all.py</code> for å oppdatere.</div></div></td></tr>'; return; }
  body.innerHTML = arr.map((s) => {
    const dirCol = s.direction === 'LONG' ? 'bull' : 'bear';
    const gradeCol = s.grade === 'A+' ? 'bull' : s.grade === 'B' ? 'warn' : s.grade === 'C' ? 'bear' : 'bull';
    return `<tr>
      <td class="tdname">${escapeHtml(s.instrument || '-')}</td>
      <td><span class="tbias ${dirCol}" style="font-size:10px">${escapeHtml(s.direction || '-')}</span></td>
      <td><span class="tgrade ${gradeCol}">${escapeHtml(s.grade || '-')}</span></td>
      <td class="tdr">${escapeHtml(s.score ?? '-')}</td><td class="tdr">${escapeHtml(s.entry_zone || '-')}</td>
      <td><span class="tsess ${s.status === 'pending' ? 'active' : 'inactive'}">${escapeHtml(s.status || '-')}</span></td>
      <td style="font-size:11px;color:var(--m)">${s.received ? escapeHtml(timeAgo(s.received)) : '-'}</td></tr>`;
  }).join('');
}

function updatePnl(pnl) {
  const todayEl = document.getElementById('pnlToday');
  const tradesEl = document.getElementById('pnlTrades');
  const winEl = document.getElementById('pnlWinRate');
  const bwEl = document.getElementById('pnlBestWorst');
  if (todayEl) { const v = pnl.today ?? 0; todayEl.textContent = fmtPnl(v); todayEl.className = `snum ${pnlColor(v)}`; }
  if (tradesEl) tradesEl.textContent = String(pnl.trades ?? 0);
  if (winEl) { const wr = pnl.win_rate; winEl.textContent = wr != null ? wr.toFixed(1) + '%' : '-'; winEl.className = `snum ${wr != null && wr >= 50 ? 'bull' : wr != null ? 'bear' : ''}`; }
  if (bwEl) { bwEl.innerHTML = `<span style="color:var(--bull)">${pnl.best != null ? fmtPnl(pnl.best) : '-'}</span> / <span style="color:var(--bear)">${pnl.worst != null ? fmtPnl(pnl.worst) : '-'}</span>`; }
  const canvas = document.getElementById('pnlCanvas');
  if (canvas && pnl.equity_curve?.length) createPnlChart(canvas, pnl.equity_curve);
}

function updateConfig(cfg) {
  const set = (id, val) => { const el = document.getElementById(id); if (el && val != null) el.value = String(val); };
  set('cfgActive', cfg.active != null ? String(cfg.active) : 'false');
  set('cfgMode', cfg.broker_mode || 'paper');
  set('cfgMaxPos', cfg.max_positions);
  set('cfgRisk', cfg.risk_pct);
  set('cfgMinGrade', cfg.min_grade || 'B');
  set('cfgMinScore', cfg.min_score);
}

function updateLog(history) {
  const body = document.getElementById('tradeLogBody');
  if (!body) return;
  const arr = Array.isArray(history) ? history : [];
  if (!arr.length) { body.innerHTML = '<tr><td colspan="4"><div class="empty-state" style="padding:20px 12px"><div class="empty-state-icon">\uD83D\uDCDD</div><div class="empty-state-title">Ingen hendelser logget</div><div class="empty-state-text">Handelsloggen fylles når boten åpner, lukker eller justerer posisjoner.</div></div></td></tr>'; return; }
  body.innerHTML = arr.slice(0, 50).map((e) => {
    const c = e.event === 'error' ? 'bear' : e.event === 'fill' ? 'bull' : 'm';
    return `<tr>
      <td style="font-size:11px;color:var(--m);white-space:nowrap">${escapeHtml(e.time || '-')}</td>
      <td><span style="color:var(--${escapeHtml(c)});font-weight:500;text-transform:uppercase;font-size:11px">${escapeHtml(e.event || '-')}</span></td>
      <td class="tdname">${escapeHtml(e.instrument || '-')}</td>
      <td style="font-size:12px;color:var(--m)">${escapeHtml(e.details || '-')}</td></tr>`;
  }).join('');
}

/* ── Data refresh ────────────────────────────────────────── */

/** Fetch all bot data and update panel. Called from main.js polling. */
export async function refreshAll() {
  const r = await Promise.allSettled([
    fetchBotStatus(), fetchBotPositions(), fetchBotSignals(),
    fetchBotHistory(50), fetchBotConfig(),
  ]);
  const data = {};
  if (r[0].status === 'fulfilled') data.status = r[0].value;
  if (r[1].status === 'fulfilled') data.positions = r[1].value;
  if (r[2].status === 'fulfilled') data.signals = r[2].value;
  if (r[3].status === 'fulfilled') { data.history = r[3].value; if (r[3].value?.pnl_summary) data.pnl = r[3].value.pnl_summary; }
  if (r[4].status === 'fulfilled') data.config = r[4].value;
  if (data.status?.pnl) data.pnl = data.status.pnl;
  update(data);
}

/** Clean up chart instances when leaving the tab. */
function wirePositionCalc() {
  const btn = document.getElementById('calcSizeBtn');
  if (!btn) return;

  btn.addEventListener('click', async () => {
    const balance = parseFloat(document.getElementById('calcBalance')?.value) || 10000;
    const riskPct = parseFloat(document.getElementById('calcRisk')?.value) || 1.0;
    const inst = document.getElementById('calcInst')?.value || 'EURUSD';
    const slPips = parseFloat(document.getElementById('calcSL')?.value) || 30;
    const vix = parseFloat(document.getElementById('calcVix')?.value) || 15.0;
    const grade = document.getElementById('calcGrade')?.value || 'A';

    const resultEl = document.getElementById('calcResult');
    if (!resultEl) return;

    // Use a simple entry/SL pair (entry 1.0 + SL offset for pip calculation)
    const entry = 1.10000;
    const slDist = slPips * 0.00010; // forex pip size
    const sl = entry - slDist;

    try {
      const { default: post } = { default: async (path, body) => {
        const url = new URL(path, window.__API_BASE || window.location.origin);
        const res = await fetch(url.toString(), {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(body),
        });
        if (!res.ok) throw new Error(`API ${res.status}`);
        return res.json();
      }};

      const data = await post('/api/v1/trading/calculate-size', {
        account_balance: balance,
        risk_pct: riskPct,
        instrument: inst,
        entry,
        stop_loss: sl,
        vix,
        grade,
      });

      resultEl.style.display = 'block';
      resultEl.innerHTML = `
        <div class="g4" style="gap:8px;margin-top:8px">
          <div class="card"><div class="ct">Lot-størrelse</div><div class="snum bull mono">${data.lot_size.toFixed(2)}</div></div>
          <div class="card"><div class="ct">Maks tap</div><div class="snum bear mono">$${data.max_loss_usd.toFixed(0)}</div></div>
          <div class="card"><div class="ct">VIX Regime</div><div class="snum warn mono" style="font-size:14px">${escapeHtml(data.vix_regime)}</div></div>
          <div class="card"><div class="ct">Tier-multiplikator</div><div class="snum mono">${data.tier_multiplier.toFixed(1)}x</div></div>
        </div>`;
    } catch (e) {
      resultEl.style.display = 'block';
      resultEl.innerHTML = '<span style="color:var(--bear)">Feil: ' + escapeHtml(e.message) + '</span>';
    }
  });
}

export function cleanup() { destroyPnlChart(); }
