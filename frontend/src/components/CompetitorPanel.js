/**
 * CompetitorPanel component — accuracy comparison table.
 *
 * New component. Placeholder for competitor signal accuracy data.
 * Displays a table with Source, Win Rate, Avg R:R, Total Signals columns.
 */

/**
 * Build the competitor panel skeleton.
 * @param {HTMLElement} container  #panel-competitor
 */
export function render(container) {
  container.innerHTML = `
    <div class="sh"><div class="sh-t">Konkurrentanalyse</div><div class="sh-b">Signal-noyaktighet</div></div>
    <div id="compTable"></div>`;

  // Initial empty state
  update(null);
}

/**
 * Update the competitor table.
 * @param {Array|null} data  Array of { source, winRate, avgRR, totalSignals }
 */
export function update(data) {
  const el = document.getElementById('compTable');
  if (!el) return;

  if (!data || !data.length) {
    el.innerHTML = `
      <div class="card">
        <div style="text-align:center;padding:40px 20px">
          <div style="font-size:15px;font-weight:600;margin-bottom:8px">Ingen data enna</div>
          <div style="font-size:12px;color:var(--m);line-height:1.6;max-width:400px;margin:0 auto">
            Konkurrentanalyse sammenligner signalnoyaktighet fra ulike kilder.
            Data fylles inn etter hvert som backtesting fullfortes.
          </div>
        </div>
      </div>`;
    return;
  }

  const rows = data
    .map(
      (d) => `<tr>
        <td><div class="tdname">${d.source}</div></td>
        <td class="${d.winRate >= 55 ? 'tdbull' : d.winRate >= 45 ? '' : 'tdbear'}" style="text-align:right">${d.winRate.toFixed(1)}%</td>
        <td class="tdr">${d.avgRR.toFixed(2)}</td>
        <td class="tdr">${d.totalSignals}</td>
      </tr>`
    )
    .join('');

  el.innerHTML = `
    <div class="cotw">
      <table class="cott">
        <thead><tr>
          <th>Kilde</th>
          <th style="text-align:right">Win Rate</th>
          <th style="text-align:right">Snitt R:R</th>
          <th style="text-align:right">Totalt signaler</th>
        </tr></thead>
        <tbody>${rows}</tbody>
      </table>
    </div>`;
}
