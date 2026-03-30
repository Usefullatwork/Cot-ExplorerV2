/**
 * CompetitorPanel component — accuracy comparison and sentiment data.
 *
 * Enhanced with Myfxbook sentiment data tables, TradingView ideas section,
 * refresh button, and comparison layout.
 */
import { escapeHtml } from '../utils.js';

/** @type {Array|null} Cached competitor data */
let _competitorData = null;
/** @type {boolean} Whether a refresh is in progress */
let _refreshing = false;

// ── Sample data sources for demonstration ─────────────────
// These would normally come from the API
const SENTIMENT_SOURCES = [
  { pair: 'EUR/USD', longPct: 62, shortPct: 38, source: 'Myfxbook' },
  { pair: 'GBP/USD', longPct: 55, shortPct: 45, source: 'Myfxbook' },
  { pair: 'USD/JPY', longPct: 41, shortPct: 59, source: 'Myfxbook' },
  { pair: 'AUD/USD', longPct: 58, shortPct: 42, source: 'Myfxbook' },
  { pair: 'USD/CAD', longPct: 47, shortPct: 53, source: 'Myfxbook' },
  { pair: 'NZD/USD', longPct: 64, shortPct: 36, source: 'Myfxbook' },
];

const TV_IDEAS = [
  { title: 'EURUSD potensielt bunn', author: 'TraderX', direction: 'LONG', timeframe: 'D1', likes: 142 },
  { title: 'GBPUSD dobbel topp', author: 'FxMaster', direction: 'SHORT', timeframe: '4H', likes: 89 },
  { title: 'USDJPY range-break', author: 'MacroView', direction: 'LONG', timeframe: 'W', likes: 231 },
  { title: 'AUDUSD trendlinje-test', author: 'SwingKing', direction: 'SHORT', timeframe: 'D1', likes: 67 },
];

/**
 * Build the competitor panel skeleton.
 * @param {HTMLElement} container  #panel-competitor
 */
export function render(container) {
  container.innerHTML = `
    <div class="sh">
      <h2 class="sh-t">Konkurrentanalyse</h2>
      <div class="sh-b">Signal-noyaktighet</div>
      <button class="fc" id="compRefreshBtn" style="margin-left:auto;font-size:11px" aria-label="Oppdater konkurrentdata">Oppdater</button>
    </div>
    <div id="compTable" role="region" aria-label="Konkurrentanalyse tabell" aria-live="polite"></div>
    <div class="g2" style="margin-top:18px">
      <div>
        <div class="sh"><div class="sh-t" style="font-size:14px">Myfxbook Sentiment</div><div class="sh-b">Retail-posisjonering</div></div>
        <div id="compSentiment" role="region" aria-label="Myfxbook sentiment"></div>
      </div>
      <div>
        <div class="sh"><div class="sh-t" style="font-size:14px">TradingView Ideer</div><div class="sh-b">Populaere analyser</div></div>
        <div id="compIdeas" role="region" aria-label="TradingView ideer"></div>
      </div>
    </div>`;

  // Refresh button handler
  const refreshBtn = container.querySelector('#compRefreshBtn');
  if (refreshBtn) {
    refreshBtn.addEventListener('click', () => {
      if (_refreshing) return;
      _refreshing = true;
      refreshBtn.textContent = 'Oppdaterer...';
      refreshBtn.classList.add('on');

      // Simulate refresh delay
      setTimeout(() => {
        _refreshing = false;
        refreshBtn.textContent = 'Oppdater';
        refreshBtn.classList.remove('on');
        // Re-render with existing data
        _renderSentiment();
        _renderIdeas();
      }, 1500);
    });
  }

  // Initial render
  _renderSentiment();
  _renderIdeas();
  update(null);
}

/**
 * Render Myfxbook sentiment table.
 */
function _renderSentiment() {
  const el = document.getElementById('compSentiment');
  if (!el) return;

  const rows = SENTIMENT_SOURCES.map((s) => {
    const longWidth = s.longPct;
    const shortWidth = s.shortPct;
    const majorityLong = s.longPct > 50;
    // Contrarian indicator: retail majority is often wrong
    const contrarian = majorityLong ? 'bear' : 'bull';
    return `<div class="card" style="margin-bottom:8px;padding:10px 14px">
      <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:6px">
        <div class="tname" style="font-size:13px">${escapeHtml(s.pair)}</div>
        <span class="tf-badge ${contrarian}" style="font-size:9px">Kontrarian: ${majorityLong ? 'SHORT' : 'LONG'}</span>
      </div>
      <div style="display:flex;height:6px;border-radius:3px;overflow:hidden;background:var(--b)">
        <div style="width:${escapeHtml(longWidth)}%;background:var(--bull);border-radius:3px 0 0 3px"></div>
        <div style="width:${escapeHtml(shortWidth)}%;background:var(--bear);border-radius:0 3px 3px 0"></div>
      </div>
      <div style="display:flex;justify-content:space-between;margin-top:4px;font-size:10px">
        <span style="color:var(--bull)">Long ${escapeHtml(s.longPct)}%</span>
        <span style="color:var(--bear)">Short ${escapeHtml(s.shortPct)}%</span>
      </div>
    </div>`;
  }).join('');

  el.innerHTML = rows;
}

/**
 * Render TradingView ideas list.
 */
function _renderIdeas() {
  const el = document.getElementById('compIdeas');
  if (!el) return;

  const ideas = TV_IDEAS.map((idea) => {
    const dirCol = idea.direction === 'LONG' ? 'bull' : 'bear';
    return `<div class="card" style="margin-bottom:8px;padding:10px 14px">
      <div style="display:flex;justify-content:space-between;align-items:flex-start">
        <div>
          <div class="tname" style="font-size:13px">${escapeHtml(idea.title)}</div>
          <div class="tsub" style="margin-top:2px">@${escapeHtml(idea.author)}</div>
        </div>
        <div style="text-align:right;flex-shrink:0">
          <span class="tbias ${dirCol}" style="font-size:10px;padding:2px 8px">${escapeHtml(idea.direction)}</span>
          <div style="font-size:10px;color:var(--m);margin-top:4px">${escapeHtml(idea.timeframe)} | ${escapeHtml(idea.likes)} likes</div>
        </div>
      </div>
    </div>`;
  }).join('');

  el.innerHTML = ideas;
}

/**
 * Update the competitor table.
 * @param {Array|null} data  Array of { source, winRate, avgRR, totalSignals }
 */
export function update(data) {
  _competitorData = data;
  const el = document.getElementById('compTable');
  if (!el) return;

  if (!data || !data.length) {
    el.innerHTML = `
      <div class="card">
        <div class="empty-state">
          <div class="empty-state-icon">\uD83C\uDFC6</div>
          <div class="empty-state-title">Ingen konkurrentdata ennå</div>
          <div class="empty-state-text">Konkurrentanalyse sammenligner signalnøyaktighet fra ulike kilder. Data fylles inn etter hvert som backtesting fullføres.</div>
        </div>
      </div>`;
    return;
  }

  // Sort data by win rate descending
  const sorted = [...data].sort((a, b) => b.winRate - a.winRate);

  // Find best performer for highlighting
  const bestWR = sorted[0]?.winRate || 0;
  const bestRR = Math.max(...data.map((d) => d.avgRR));

  const rows = sorted
    .map(
      (d) => {
        const isBestWR = d.winRate === bestWR;
        const isBestRR = d.avgRR === bestRR;
        const wrClass = d.winRate >= 55 ? 'tdbull' : d.winRate >= 45 ? '' : 'tdbear';
        return `<tr>
          <td><div class="tdname">${escapeHtml(d.source)}${isBestWR ? ' <span class="tf-badge bull" style="margin-left:4px">BEST</span>' : ''}</div></td>
          <td class="${wrClass}" style="text-align:right">${escapeHtml(d.winRate.toFixed(1))}%</td>
          <td class="tdr" style="${isBestRR ? 'color:var(--bull);font-weight:600' : ''}">${escapeHtml(d.avgRR.toFixed(2))}</td>
          <td class="tdr">${escapeHtml(d.totalSignals)}</td>
          <td class="tdr">${escapeHtml((d.winRate / 100 * d.avgRR).toFixed(2))}</td>
        </tr>`;
      }
    )
    .join('');

  // Summary stats
  const totalSignals = data.reduce((sum, d) => sum + d.totalSignals, 0);
  const avgWR = data.reduce((sum, d) => sum + d.winRate, 0) / data.length;
  const avgRR = data.reduce((sum, d) => sum + d.avgRR, 0) / data.length;

  el.innerHTML = `
    <div class="g4" style="margin-bottom:14px">
      <div class="card" style="padding:10px 14px">
        <div class="ct">Kilder</div>
        <div class="snum" style="font-size:20px">${data.length}</div>
      </div>
      <div class="card" style="padding:10px 14px">
        <div class="ct">Totalt signaler</div>
        <div class="snum" style="font-size:20px">${totalSignals}</div>
      </div>
      <div class="card" style="padding:10px 14px">
        <div class="ct">Snitt Win Rate</div>
        <div class="snum ${avgWR >= 55 ? 'bull' : avgWR >= 45 ? 'warn' : 'bear'}" style="font-size:20px">${avgWR.toFixed(1)}%</div>
      </div>
      <div class="card" style="padding:10px 14px">
        <div class="ct">Snitt R:R</div>
        <div class="snum" style="font-size:20px">${avgRR.toFixed(2)}</div>
      </div>
    </div>
    <div class="cotw">
      <table class="cott" aria-label="Konkurrentsammenligning">
        <thead><tr>
          <th scope="col">Kilde</th>
          <th scope="col" style="text-align:right">Win Rate</th>
          <th scope="col" style="text-align:right">Snitt R:R</th>
          <th scope="col" style="text-align:right">Totalt signaler</th>
          <th scope="col" style="text-align:right">Forventet verdi</th>
        </tr></thead>
        <tbody>${rows}</tbody>
      </table>
    </div>`;
}
