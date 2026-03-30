/**
 * CryptoPanel component — Krypto Intel tab.
 *
 * Displays Fear & Greed gauge, total market cap, BTC dominance,
 * and a price grid for 8 major cryptocurrencies.
 */

import { escapeHtml, formatNumber, colorClass } from '../utils.js';
import { fetchCryptoMarket, fetchCryptoFearGreed } from '../api.js';

let pollTimer = null;

/**
 * Render the initial skeleton.
 * @param {HTMLElement} container
 */
export function render(container) {
  container.innerHTML = `
    <div class="sh">
      <h2 class="sh-t">Krypto Intel</h2>
      <div class="sh-b" id="kryptoUpdated" aria-live="polite">-</div>
    </div>
    <div id="kryptoFng" style="margin-bottom:16px">
      <div class="loading" role="status"><div class="spinner" aria-hidden="true"></div>Laster Frykt & Gradighet...</div>
    </div>
    <div id="kryptoContent">
      <div class="loading" role="status"><div class="spinner" aria-hidden="true"></div>Laster kryptomarked...</div>
    </div>`;
}

/** Norwegian label for Fear & Greed value */
function fngLabel(value) {
  if (value <= 20) return 'Ekstrem frykt';
  if (value <= 40) return 'Frykt';
  if (value <= 60) return 'Nøytral';
  if (value <= 80) return 'Gradighet';
  return 'Ekstrem gradighet';
}

/** Color for Fear & Greed gauge */
function fngColor(value) {
  if (value <= 25) return 'var(--bear)';
  if (value <= 45) return '#f0883e';
  if (value <= 55) return 'var(--m)';
  if (value <= 75) return '#7ee787';
  return 'var(--bull)';
}

/** Format large numbers as B/M/K */
function fmtCap(n) {
  if (n == null) return '-';
  if (n >= 1e12) return (n / 1e12).toFixed(2) + 'T';
  if (n >= 1e9) return (n / 1e9).toFixed(1) + 'B';
  if (n >= 1e6) return (n / 1e6).toFixed(1) + 'M';
  return formatNumber(n);
}

/** Format price with appropriate precision */
function fmtPrice(p) {
  if (p == null) return '-';
  if (p >= 1000) return formatNumber(Math.round(p));
  if (p >= 1) return p.toFixed(2);
  return p.toFixed(4);
}

/**
 * Update the Fear & Greed gauge.
 * @param {{ value: number, label: string }} data
 */
export function updateFng(data) {
  const el = document.getElementById('kryptoFng');
  if (!el || !data) return;

  const v = data.value ?? 50;
  const pct = Math.min(100, Math.max(0, v));
  const col = fngColor(v);
  const label = fngLabel(v);

  el.innerHTML = `
    <div class="card" style="padding:16px">
      <div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:8px">
        <span style="font-size:13px;font-weight:600">Frykt & Gradighet</span>
        <span class="mono" style="font-size:24px;font-weight:700;color:${col}">${v}</span>
      </div>
      <div style="height:8px;border-radius:4px;background:var(--bg3);overflow:hidden">
        <div style="width:${pct}%;height:100%;background:${col};border-radius:4px;transition:width 0.3s"></div>
      </div>
      <div style="font-size:11px;color:var(--m);margin-top:4px;text-align:right">${escapeHtml(label)}</div>
    </div>`;
}

/**
 * Update the market overview grid.
 * @param {{ coins: Array, total_market_cap: number, btc_dominance: number }} data
 */
export function update(data) {
  const el = document.getElementById('kryptoContent');
  if (!el) return;
  if (!data || !data.coins || !data.coins.length) {
    el.innerHTML = `<div class="empty-state"><div class="empty-state-icon">\u20BF</div><div class="empty-state-title">Ingen kryptodata tilgjengelig</div><div class="empty-state-text">Markedsdata hentes fra CoinGecko. Sjekk nettverkstilkobling eller prøv å laste siden på nytt.</div></div>`;
    return;
  }

  const coins = data.coins || [];
  const cap = data.total_market_cap || 0;
  const dom = data.btc_dominance || 0;

  const capHtml = `
    <div style="display:flex;gap:16px;margin-bottom:16px">
      <div class="card" style="flex:1;padding:12px">
        <div class="ct">Total markedsverdi</div>
        <div class="snum">${escapeHtml(fmtCap(cap))}</div>
      </div>
      <div class="card" style="flex:1;padding:12px">
        <div class="ct">BTC Dominans</div>
        <div class="snum">${dom.toFixed(1)}%</div>
      </div>
    </div>`;

  const grid = coins.map((c) => {
    const chg = c.change_24h;
    return `<div class="card" style="padding:12px">
      <div style="display:flex;align-items:center;gap:8px;margin-bottom:8px">
        <span style="font-weight:600;font-size:13px">${escapeHtml(c.symbol)}</span>
        <span style="font-size:11px;color:var(--m)">${escapeHtml(c.name)}</span>
        ${c.rank ? `<span style="font-size:10px;color:var(--m);margin-left:auto">#${c.rank}</span>` : ''}
      </div>
      <div style="display:flex;justify-content:space-between;align-items:baseline">
        <span class="data-value" style="font-size:14px;font-weight:600">\$${escapeHtml(fmtPrice(c.price))}</span>
        <span class="${colorClass(chg)} data-value" style="font-size:12px">${chg != null ? (chg > 0 ? '+' : '') + chg.toFixed(1) + '%' : '-'}</span>
      </div>
      <div style="font-size:10px;color:var(--m);margin-top:4px">Vol: \$${escapeHtml(fmtCap(c.volume_24h))}</div>
    </div>`;
  }).join('');

  el.innerHTML = capHtml + `<div class="g4">${grid}</div>`;

  const ts = document.getElementById('kryptoUpdated');
  if (ts) ts.textContent = 'Oppdatert: ' + new Date().toLocaleTimeString('nb-NO');
}

/**
 * Fetch all crypto data and render.
 */
export async function refreshAll() {
  try {
    const [market, fng] = await Promise.all([
      fetchCryptoMarket(),
      fetchCryptoFearGreed(),
    ]);
    update(market);
    updateFng(fng);
  } catch (e) {
    console.error('[CryptoPanel]', e);
  }

  stopPolling();
  pollTimer = setInterval(async () => {
    try {
      const [market, fng] = await Promise.all([
        fetchCryptoMarket(),
        fetchCryptoFearGreed(),
      ]);
      update(market);
      updateFng(fng);
    } catch { /* ignore */ }
  }, 120_000);
}

/** Stop auto-refresh polling. */
export function stopPolling() {
  if (pollTimer) {
    clearInterval(pollTimer);
    pollTimer = null;
  }
}
