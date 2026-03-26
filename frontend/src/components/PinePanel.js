/**
 * PinePanel component — browse Pine Script v5 indicators, strategies, and combos.
 *
 * New component. Displays cards grouped by category with copy-to-clipboard.
 * Enhanced with TradingView widget placeholder, script selection dropdown,
 * copy-to-clipboard button, and script preview.
 */

// ── Pine script catalog ─────────────────────────────────────
// Hardcoded file list matching the pine/ directory structure.
// Each entry: { name, file, category, description }

const PINE_SCRIPTS = [
  // Indicators (7)
  { name: 'COT Overlay', file: 'indicators/cot_overlay.pine', category: 'Indicators', description: 'Spekulant- og kommersiell netto-posisjon med persentilrangering.' },
  { name: 'Confluence Score', file: 'indicators/confluence_score.pine', category: 'Indicators', description: '12-punkts konfluensvurdering for handelssetups.' },
  { name: 'SMC Zones', file: 'indicators/smc_zones.pine', category: 'Indicators', description: 'Supply/Demand-soner med BOS-linjer og strukturklassifisering.' },
  { name: 'L2L Levels', file: 'indicators/l2l_levels.pine', category: 'Indicators', description: 'Level-to-Level setup overlay med entry, SL, T1, T2 og R:R-beregning.' },
  { name: 'VIX Regime', file: 'indicators/vix_regime.pine', category: 'Indicators', description: 'Bakgrunnsfarge og posisjonsstorrelse basert pa VIX-niva.' },
  { name: 'Macro Dashboard', file: 'indicators/macro_dashboard.pine', category: 'Indicators', description: 'Tabell med makroindikatorer og Dollar Smile.' },
  { name: 'Dollar Smile', file: 'indicators/dollar_smile.pine', category: 'Indicators', description: 'USD-styrkeindikator med regimeklassifisering.' },

  // Strategies (2)
  { name: 'COT Reversal', file: 'strategies/cot_reversal.pine', category: 'Strategies', description: 'Backtestbar strategi med COT-ekstremreversal og SMA200-filter.' },
  { name: 'SMC Confluence', file: 'strategies/smc_confluence.pine', category: 'Strategies', description: 'Backtestbar strategi med confluence score og SMC demand/supply-soner.' },

  // Combos (3)
  { name: 'COT Explorer Overlay', file: 'combos/cot_explorer_overlay.pine', category: 'Combos', description: 'Slot 1: SMC Zones + L2L Levels + VIX bakgrunn + PDH/PDL/PWH/PWL.' },
  { name: 'COT Explorer Score', file: 'combos/cot_explorer_score.pine', category: 'Combos', description: 'Slot 2: Confluence Score histogram + COT netto-posisjon.' },
  { name: 'COT Explorer Macro', file: 'combos/cot_explorer_macro.pine', category: 'Combos', description: 'Slot 3: Macro Dashboard tabell + Dollar Smile label.' },
];

const CATEGORIES = ['Indicators', 'Strategies', 'Combos'];

/** @type {string|null} Currently selected script file for preview */
let _selectedScript = null;

/**
 * Build the Pine Scripts panel.
 * @param {HTMLElement} container  #panel-pine
 */
export function render(container) {
  // Build dropdown options
  const dropdownOptions = CATEGORIES.map((cat) => {
    const scripts = PINE_SCRIPTS.filter((s) => s.category === cat);
    return `<optgroup label="${cat}">${scripts.map((s) => `<option value="${s.file}">${s.name}</option>`).join('')}</optgroup>`;
  }).join('');

  const sections = CATEGORIES.map((cat) => {
    const scripts = PINE_SCRIPTS.filter((s) => s.category === cat);
    const cards = scripts
      .map(
        (s) => `
        <article class="card pine-card" data-file="${s.file}" style="margin-bottom:10px;cursor:pointer;transition:border-color 0.15s" aria-label="${s.name} Pine script">
          <div style="display:flex;justify-content:space-between;align-items:flex-start">
            <div>
              <div class="tname">${s.name}</div>
              <div class="tsub" style="margin-top:4px">${s.description}</div>
              <div style="margin-top:6px"><span class="tf-badge ${cat === 'Indicators' ? 'bull' : cat === 'Strategies' ? 'warn' : 'neutral'}" role="note">${cat}</span></div>
            </div>
            <button class="fc pine-copy" data-file="${s.file}" style="flex-shrink:0;margin-left:12px" aria-label="Kopier ${s.name} til utklippstavle">Kopier</button>
          </div>
        </article>`
      )
      .join('');

    return `<div class="ct" style="margin-top:18px">${cat} (${scripts.length})</div>${cards}`;
  }).join('');

  container.innerHTML = `
    <div class="sh"><h2 class="sh-t">Pine Scripts</h2><div class="sh-b">TradingView v5</div></div>
    <div class="g21" style="margin-bottom:18px">
      <div class="card" role="region" aria-label="TradingView widget">
        <div class="ct">TradingView Widget</div>
        <div id="tvWidgetPlaceholder" style="height:300px;display:flex;align-items:center;justify-content:center;border:1px dashed var(--b2);border-radius:8px;color:var(--m);font-size:13px;line-height:1.6;text-align:center">
          <div>
            <div style="font-size:24px;margin-bottom:8px" aria-hidden="true">&#128202;</div>
            <div>TradingView Widget</div>
            <div style="font-size:11px;margin-top:4px">Koble til TradingView for live chart-visning.<br>Velg et script fra listen for forhåndsvisning.</div>
          </div>
        </div>
      </div>
      <div>
        <div class="card" style="margin-bottom:12px">
          <div class="ct">Hurtigvalg</div>
          <label for="pineScriptSelect" class="sr-only">Velg Pine Script</label>
          <select id="pineScriptSelect" aria-label="Velg Pine Script" style="width:100%;background:var(--s2);border:1px solid var(--b);color:var(--t);font-family:'DM Sans',sans-serif;font-size:13px;padding:8px 10px;border-radius:6px;outline:none;margin-bottom:10px">
            <option value="">Velg script...</option>
            ${dropdownOptions}
          </select>
          <button class="fc" id="pineCopySelected" style="width:100%;text-align:center;padding:8px;font-size:12px;font-weight:600" aria-label="Kopier valgt script til utklippstavle">Kopier valgt script</button>
        </div>
        <div class="card" role="region" aria-label="Pine script statistikk">
          <div class="ct">Statistikk</div>
          <div style="font-size:12px;color:var(--m);line-height:1.8">
            <div>Indikatorer: <strong style="color:var(--bull)">${PINE_SCRIPTS.filter((s) => s.category === 'Indicators').length}</strong></div>
            <div>Strategier: <strong style="color:var(--warn)">${PINE_SCRIPTS.filter((s) => s.category === 'Strategies').length}</strong></div>
            <div>Komboer: <strong style="color:var(--m)">${PINE_SCRIPTS.filter((s) => s.category === 'Combos').length}</strong></div>
            <div style="margin-top:6px">Totalt: <strong>${PINE_SCRIPTS.length}</strong> scripts</div>
          </div>
        </div>
      </div>
    </div>
    <div id="pinePreview" style="display:none;margin-bottom:18px" role="region" aria-label="Script forhåndsvisning">
      <div class="card">
        <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:8px">
          <div class="ct" style="margin-bottom:0" id="pinePreviewTitle">Forhåndsvisning</div>
          <button class="fc" id="pinePreviewCopy" style="font-size:10px" aria-label="Kopier forhåndsvist kode">Kopier kode</button>
        </div>
        <pre id="pinePreviewCode" style="background:var(--bg);border:1px solid var(--b);border-radius:6px;padding:12px;font-family:'DM Mono',monospace;font-size:11px;color:var(--t);overflow-x:auto;max-height:300px;overflow-y:auto;white-space:pre;margin:0"></pre>
      </div>
    </div>
    ${sections}`;

  // Copy button handler (delegated)
  container.addEventListener('click', async (e) => {
    const btn = e.target.closest('.pine-copy');
    if (!btn) return;

    const file = btn.dataset.file;
    await _copyPineFile(file, btn);
  });

  // Card click -> select & preview
  container.addEventListener('click', (e) => {
    if (e.target.closest('.pine-copy')) return; // handled above
    const card = e.target.closest('.pine-card');
    if (!card) return;
    const file = card.dataset.file;
    if (file) {
      _selectAndPreview(file);
      // Update dropdown to match
      const sel = document.getElementById('pineScriptSelect');
      if (sel) sel.value = file;
    }
  });

  // Dropdown selection -> preview
  const dropdown = container.querySelector('#pineScriptSelect');
  if (dropdown) {
    dropdown.addEventListener('change', (e) => {
      if (e.target.value) _selectAndPreview(e.target.value);
    });
  }

  // Copy selected script from dropdown
  const copySelected = container.querySelector('#pineCopySelected');
  if (copySelected) {
    copySelected.addEventListener('click', async () => {
      const sel = document.getElementById('pineScriptSelect');
      if (sel && sel.value) {
        await _copyPineFile(sel.value, copySelected);
      } else {
        copySelected.textContent = 'Velg et script forst';
        setTimeout(() => { copySelected.textContent = 'Kopier valgt script'; }, 2000);
      }
    });
  }

  // Preview copy button
  const previewCopy = container.querySelector('#pinePreviewCopy');
  if (previewCopy) {
    previewCopy.addEventListener('click', async () => {
      const codeEl = document.getElementById('pinePreviewCode');
      if (codeEl && codeEl.textContent) {
        try {
          await navigator.clipboard.writeText(codeEl.textContent);
          previewCopy.textContent = 'Kopiert!';
        } catch {
          previewCopy.textContent = 'Feil';
        }
        setTimeout(() => { previewCopy.textContent = 'Kopier kode'; }, 2000);
      }
    });
  }
}

/**
 * Copy a Pine script file to clipboard.
 * @param {string} file  The filename
 * @param {HTMLElement} btn  The button to update text on
 */
async function _copyPineFile(file, btn) {
  const origText = btn.textContent;
  try {
    const res = await fetch(`/pine/${file}`);
    if (!res.ok) throw new Error('File not found');
    const text = await res.text();
    await navigator.clipboard.writeText(text);
    btn.textContent = 'Kopiert!';
    setTimeout(() => { btn.textContent = origText; }, 2000);
  } catch {
    btn.textContent = file;
    setTimeout(() => { btn.textContent = origText; }, 2000);
  }
}

/**
 * Select a script and show its preview.
 * @param {string} file  The filename
 */
async function _selectAndPreview(file) {
  _selectedScript = file;
  const script = PINE_SCRIPTS.find((s) => s.file === file);
  const previewWrap = document.getElementById('pinePreview');
  const titleEl = document.getElementById('pinePreviewTitle');
  const codeEl = document.getElementById('pinePreviewCode');
  if (!previewWrap || !codeEl) return;

  previewWrap.style.display = 'block';
  if (titleEl) titleEl.textContent = script ? script.name : file;

  codeEl.textContent = 'Laster...';
  try {
    const res = await fetch(`/pine/${file}`);
    if (!res.ok) throw new Error('Not found');
    codeEl.textContent = await res.text();
  } catch {
    codeEl.textContent = `// Kunne ikke laste ${file}\n// Filen er tilgjengelig i pine/-mappen.`;
  }

  // Highlight selected card
  document.querySelectorAll('.pine-card').forEach((c) => {
    c.style.borderColor = c.dataset.file === file ? 'var(--blue)' : '';
  });
}

/**
 * No dynamic data needed — Pine panel is static.
 */
export function update() {
  // No-op; pine scripts are statically listed.
}
