/**
 * PinePanel component — browse Pine Script v5 indicators, strategies, and combos.
 *
 * New component. Displays cards grouped by category with copy-to-clipboard.
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

/**
 * Build the Pine Scripts panel.
 * @param {HTMLElement} container  #panel-pine
 */
export function render(container) {
  const sections = CATEGORIES.map((cat) => {
    const scripts = PINE_SCRIPTS.filter((s) => s.category === cat);
    const cards = scripts
      .map(
        (s) => `
        <div class="card" style="margin-bottom:10px">
          <div style="display:flex;justify-content:space-between;align-items:flex-start">
            <div>
              <div class="tname">${s.name}</div>
              <div class="tsub" style="margin-top:4px">${s.description}</div>
              <div style="margin-top:6px"><span class="tf-badge ${cat === 'Indicators' ? 'bull' : cat === 'Strategies' ? 'warn' : 'neutral'}">${cat}</span></div>
            </div>
            <button class="fc pine-copy" data-file="${s.file}" style="flex-shrink:0;margin-left:12px">Kopier</button>
          </div>
        </div>`
      )
      .join('');

    return `<div class="ct" style="margin-top:18px">${cat} (${scripts.length})</div>${cards}`;
  }).join('');

  container.innerHTML = `
    <div class="sh"><div class="sh-t">Pine Scripts</div><div class="sh-b">TradingView v5</div></div>
    ${sections}`;

  // Copy button handler (delegated)
  container.addEventListener('click', async (e) => {
    const btn = e.target.closest('.pine-copy');
    if (!btn) return;

    const file = btn.dataset.file;
    try {
      const res = await fetch(`/pine/${file}`);
      if (!res.ok) throw new Error('File not found');
      const text = await res.text();
      await navigator.clipboard.writeText(text);
      btn.textContent = 'Kopiert!';
      setTimeout(() => { btn.textContent = 'Kopier'; }, 2000);
    } catch {
      // Fallback: show the filename
      btn.textContent = file;
      setTimeout(() => { btn.textContent = 'Kopier'; }, 2000);
    }
  });
}

/**
 * No dynamic data needed — Pine panel is static.
 */
export function update() {
  // No-op; pine scripts are statically listed.
}
