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
  // Indicators
  { name: 'COT Momentum', file: 'cot_momentum.pine', category: 'Indicators', description: 'COT speculator net position momentum with divergence detection.' },
  { name: 'Dollar Smile Model', file: 'dollar_smile.pine', category: 'Indicators', description: 'Three-regime USD model: risk-off, goldilocks, growth.' },
  { name: 'VIX Regime Overlay', file: 'vix_regime.pine', category: 'Indicators', description: 'Color-coded VIX regime bands for position sizing.' },
  { name: 'SMC Market Structure', file: 'smc_structure.pine', category: 'Indicators', description: 'Break of structure, order blocks, and fair value gaps.' },
  { name: 'Level-to-Level Map', file: 'level_to_level.pine', category: 'Indicators', description: 'Multi-timeframe support/resistance with proximity alerts.' },

  // Strategies
  { name: 'COT Swing Strategy', file: 'cot_swing.pine', category: 'Strategies', description: 'Weekly COT-based swing entries with ATR-scaled stops.' },
  { name: 'SMC Scalp Strategy', file: 'smc_scalp.pine', category: 'Strategies', description: 'Intraday smart money concept entries on 15m/1H.' },
  { name: 'Macro Regime Strategy', file: 'macro_regime.pine', category: 'Strategies', description: 'Dollar smile regime filter with carry trade entries.' },
  { name: 'Binary Risk Filter', file: 'binary_risk.pine', category: 'Strategies', description: 'Event-driven position reduction around high-impact releases.' },

  // Combos
  { name: 'Full Confluence Engine', file: 'confluence_engine.pine', category: 'Combos', description: 'Combined 12-point scoring: COT + SMC + Macro + Levels.' },
  { name: 'Risk Dashboard', file: 'risk_dashboard.pine', category: 'Combos', description: 'Portfolio heat, correlation matrix, and VIX scaling overlay.' },
  { name: 'Alert Hub', file: 'alert_hub.pine', category: 'Combos', description: 'Unified alerts for all signals — webhook-ready for automation.' },
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
