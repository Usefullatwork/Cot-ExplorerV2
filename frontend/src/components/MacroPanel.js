/**
 * MacroPanel component — orchestrator for Dollar Smile, VIX regime, sentiment,
 * macro stats, rates & credit, VIX term structure, regime timeline, and ADR.
 *
 * Delegates rendering and updates to three sub-modules:
 * - MacroDollarSmile (Dollar Smile model, inputs, safe-haven, ADR)
 * - MacroVixSection (VIX regime, sentiment, VIX term, regime timeline)
 * - MacroInputsSection (Macro stats, rate & credit)
 */

import * as DollarSmile from './macro/MacroDollarSmile.js';
import * as VixSection from './macro/MacroVixSection.js';
import * as InputsSection from './macro/MacroInputsSection.js';

/**
 * Build the static DOM skeleton inside the macro panel.
 * Creates layout containers and delegates to sub-modules.
 * @param {HTMLElement} container  #panel-macro
 */
export function render(container) {
  // Top grid: Dollar Smile (left) + VIX/Sentiment/Safe-haven (right)
  const g21 = document.createElement('div');
  g21.className = 'g21';

  const smileCard = document.createElement('div');
  smileCard.className = 'card';
  smileCard.setAttribute('role', 'region');
  smileCard.setAttribute('aria-label', 'Dollar-smil modell');

  const rightCol = document.createElement('div');

  // Safe-haven card (lives in the right column, after sentiment)
  const safeCard = document.createElement('div');
  safeCard.className = 'card';
  safeCard.setAttribute('role', 'region');
  safeCard.setAttribute('aria-label', 'Safe-haven hierarki');

  g21.appendChild(smileCard);
  g21.appendChild(rightCol);

  container.innerHTML = '';
  container.appendChild(g21);

  // Sub-module sections
  const statsSection = document.createElement('div');
  const renteSection = document.createElement('div');
  const termSection = document.createElement('div');
  const timelineSection = document.createElement('div');
  const adrSection = document.createElement('div');

  container.appendChild(statsSection);
  container.appendChild(renteSection);
  container.appendChild(termSection);
  container.appendChild(timelineSection);
  container.appendChild(adrSection);

  // Conflicts + drilldown
  container.insertAdjacentHTML('beforeend', `
    <div id="macroConflicts" style="display:none;margin-top:16px" role="alert" aria-label="Konflikter"></div>
    <div id="macroDrilldown" style="display:none;margin-top:16px" role="region" aria-label="Detaljer">
      <div class="card">
        <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:12px">
          <div class="ct" style="margin-bottom:0" id="drilldownTitle">Detaljer</div>
          <button class="fc" id="drilldownClose" style="font-size:11px" aria-label="Lukk detaljer">Lukk</button>
        </div>
        <div id="drilldownBody" style="font-size:13px;color:var(--m);line-height:1.7"></div>
      </div>
    </div>`);

  // Drilldown close handler
  const closeBtn = container.querySelector('#drilldownClose');
  if (closeBtn) {
    closeBtn.addEventListener('click', () => {
      const dd = document.getElementById('macroDrilldown');
      if (dd) dd.style.display = 'none';
    });
  }

  // Delegate rendering to sub-modules
  DollarSmile.render(smileCard, safeCard, adrSection);
  VixSection.render(rightCol, termSection, timelineSection);
  InputsSection.render(statsSection, renteSection);

  // Append safe-haven card after VixSection populates rightCol
  rightCol.appendChild(safeCard);
}

/**
 * Open the drilldown detail panel.
 * @param {string} title
 * @param {string} bodyHtml
 */
function openDrilldown(title, bodyHtml) {
  const dd = document.getElementById('macroDrilldown');
  const titleEl = document.getElementById('drilldownTitle');
  const bodyEl = document.getElementById('drilldownBody');
  if (dd && titleEl && bodyEl) {
    titleEl.textContent = title;
    bodyEl.innerHTML = bodyHtml;
    dd.style.display = 'block';
  }
}

/**
 * Update the macro panel with fresh data.
 * Distributes data to each sub-module.
 * @param {Object} m  Full macro data payload
 */
export function update(m) {
  if (!m) {
    const msEl = document.getElementById('macroStats');
    if (msEl) msEl.innerHTML = `<div class="empty-state" style="grid-column:1/-1"><div class="empty-state-icon">\uD83D\uDCC9</div><div class="empty-state-title">Ingen makrodata tilgjengelig</div><div class="empty-state-text">Kjør <code>python fetch_fundamentals.py</code> for å hente VIX, DXY, Brent og gullpriser fra FRED og Yahoo Finance.</div></div>`;
    return;
  }

  // Clean up previous chart instances
  VixSection.destroyCharts();
  InputsSection.destroyCharts();

  // Delegate updates to sub-modules
  DollarSmile.update(m);
  VixSection.update(m);
  InputsSection.update(m, openDrilldown);

  // Conflicts section (cross-cutting, stays in orchestrator)
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
