import { describe, it, expect, beforeEach } from 'vitest';
import { renderCard, attachToggle } from '../components/SetupCard.js';

/** Minimal instrument/signal data to exercise the card. */
function makeLv(overrides = {}) {
  return {
    name: 'EURUSD',
    label: 'Euro / US Dollar',
    grade: 'A+',
    grade_color: 'bull',
    score: 6,
    score_pct: 75,
    class: 'A',
    dir_color: 'bull',
    current: 1.085,
    timeframe_bias: 'SWING',
    session: { active: true, label: 'London' },
    cot: { net: 50000, bias: 'LONG', color: 'bull', momentum: 'OKER', report: 'Legacy', date: '2026-03-18', chg: 5000, pct: 12.3 },
    open_interest: 400000,
    sma200: 1.072,
    sma200_pos: 'over',
    atr14: 0.0085,
    chg5d: 0.35,
    chg20d: 1.12,
    resistances: [{ name: 'R1', level: 1.09, dist_atr: 0.6, weight: 3 }],
    supports: [{ name: 'S1', level: 1.075, dist_atr: 1.2, weight: 2 }],
    setup_long: {
      entry_name: 'FVG',
      entry: 1.083,
      entry_dist_atr: 0.3,
      sl: 1.078,
      sl_type: 'PDL',
      risk_atr_d: 0.6,
      t1: 1.09,
      t1_weight: 3,
      t1_quality: 'strong',
      t2: 1.095,
      rr_t1: 1.4,
      rr_t2: 2.4,
      min_rr: 1.2,
      entry_weight: 4,
      note: 'Strong confluence',
    },
    setup_short: null,
    binary_risk: [],
    score_details: [
      { kryss: 'COT', verdi: true },
      { kryss: 'SMA', verdi: false },
    ],
    pos_size: '2%',
    dxy_conf: 'medvind',
    vix_spread_factor: 1.2,
    ...overrides,
  };
}

describe('SetupCard', () => {
  beforeEach(() => {
    document.body.innerHTML = '';
  });

  it('renders a card with the instrument name', () => {
    const html = renderCard(makeLv(), 0);
    const div = document.createElement('div');
    div.innerHTML = html;

    expect(div.querySelector('.tname').textContent).toBe('EURUSD');
  });

  it('renders the grade and score', () => {
    const html = renderCard(makeLv(), 0);
    const div = document.createElement('div');
    div.innerHTML = html;

    const grade = div.querySelector('.tgrade');
    expect(grade.textContent).toContain('A+');
    expect(grade.textContent).toContain('6/8');
  });

  it('renders label subtitle', () => {
    const html = renderCard(makeLv(), 0);
    const div = document.createElement('div');
    div.innerHTML = html;

    expect(div.querySelector('.tsub').textContent).toBe('Euro / US Dollar');
  });

  it('shows LONG bias when dir_color is bull', () => {
    const html = renderCard(makeLv(), 0);
    const div = document.createElement('div');
    div.innerHTML = html;

    const bias = div.querySelector('.tbias');
    expect(bias.textContent).toBe('LONG');
    expect(bias.classList.contains('bull')).toBe(true);
  });

  it('shows SHORT bias when dir_color is bear', () => {
    const html = renderCard(makeLv({ dir_color: 'bear' }), 0);
    const div = document.createElement('div');
    div.innerHTML = html;

    const bias = div.querySelector('.tbias');
    expect(bias.textContent).toBe('SHORT');
  });

  it('renders the LONG setup side', () => {
    const html = renderCard(makeLv(), 0);
    const div = document.createElement('div');
    div.innerHTML = html;

    const setupLabels = div.querySelectorAll('.setup-label');
    const texts = Array.from(setupLabels).map((el) => el.textContent);
    expect(texts.some((t) => t.includes('LONG'))).toBe(true);
  });

  it('shows "Ikke tilgjengelig" for null setup_short', () => {
    const html = renderCard(makeLv(), 0);
    const div = document.createElement('div');
    div.innerHTML = html;

    expect(div.innerHTML).toContain('Ikke tilgjengelig');
  });

  it('renders score dots from score_details', () => {
    const html = renderCard(makeLv(), 0);
    const div = document.createElement('div');
    div.innerHTML = html;

    const dots = div.querySelectorAll('.score-item');
    expect(dots.length).toBe(2);
  });

  it('renders binary risk warning when present', () => {
    const html = renderCard(makeLv({ binary_risk: [{ title: 'NFP i dag' }] }), 0);
    const div = document.createElement('div');
    div.innerHTML = html;

    expect(div.querySelector('.binrisk')).not.toBeNull();
    expect(div.querySelector('.binrisk').textContent).toContain('NFP i dag');
    expect(div.querySelector('.trisk')).not.toBeNull();
  });

  it('does not render binary risk when array is empty', () => {
    const html = renderCard(makeLv(), 0);
    const div = document.createElement('div');
    div.innerHTML = html;

    expect(div.querySelector('.binrisk')).toBeNull();
    expect(div.querySelector('.trisk')).toBeNull();
  });

  describe('attachToggle', () => {
    it('opens the detail panel on header click', () => {
      const container = document.createElement('div');
      container.innerHTML = renderCard(makeLv(), 0);
      document.body.appendChild(container);

      attachToggle(container);

      const head = container.querySelector('.tic-head');
      head.click();

      const det = document.getElementById('tdet0');
      expect(det.classList.contains('open')).toBe(true);
    });

    it('closes the panel on second click', () => {
      const container = document.createElement('div');
      container.innerHTML = renderCard(makeLv(), 0);
      document.body.appendChild(container);

      attachToggle(container);

      const head = container.querySelector('.tic-head');
      head.click(); // open
      head.click(); // close

      const det = document.getElementById('tdet0');
      expect(det.classList.contains('open')).toBe(false);
    });
  });
});
