/** Canonical instrument display order */
export const INSTRUMENT_ORDER = [
  'EURUSD', 'USDJPY', 'GBPUSD', 'AUDUSD',
  'Gold', 'Silver', 'Brent', 'WTI',
  'SPX', 'NAS100', 'DXY', 'VIX',
];

/** Category labels (Norwegian UI) */
export const CATEGORY_LABELS = {
  valuta: 'Valuta',
  ravarer: 'Ravarer',
  aksjer: 'Aksjer',
};

/** Grade → color-class mapping */
export const GRADE_COLORS = {
  'A+': 'bull',
  'A':  'warn',
  'B':  'bear',
  'C':  'bear',
};

/**
 * Hex values for chart.js (which cannot read CSS custom properties).
 * Matches the :root tokens in variables.css.
 */
export const CSS_COLORS = {
  bg:   '#0d1117',
  s:    '#161b22',
  s2:   '#1c2128',
  b:    '#21262d',
  b2:   '#30363d',
  t:    '#e6edf3',
  m:    '#7d8590',
  bull: '#3fb950',
  bbg:  'rgba(63,185,80,0.12)',
  bear: '#f85149',
  rbg:  'rgba(248,81,73,0.12)',
  warn: '#d29922',
  wbg:  'rgba(210,153,34,0.12)',
  blue: '#58a6ff',
  blbg: 'rgba(88,166,255,0.12)',
};
