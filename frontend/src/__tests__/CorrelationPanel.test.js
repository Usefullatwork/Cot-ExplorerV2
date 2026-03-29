import { describe, it, expect, beforeEach, vi } from 'vitest';

// Mock API calls
vi.mock('../api.js', () => ({
  fetchCorrelations: vi.fn(),
}));

// Mock state
vi.mock('../state.js', () => ({
  setState: vi.fn(),
}));

import { render, update } from '../components/CorrelationPanel.js';

/** Build a minimal 3-instrument correlation payload. */
function makeCorrelationData(n = 3) {
  const instruments = ['EURUSD', 'XAUUSD', 'USOIL'].slice(0, n);
  const matrix = instruments.map((_, i) =>
    instruments.map((_, j) => {
      if (i === j) return 1.0;
      if (i === 0 && j === 1) return 0.75;
      if (i === 1 && j === 0) return 0.75;
      if (i === 0 && j === 2) return -0.45;
      if (i === 2 && j === 0) return -0.45;
      if (i === 1 && j === 2) return -0.30;
      if (i === 2 && j === 1) return -0.30;
      return 0;
    })
  );
  return { instruments, matrix };
}

describe('CorrelationPanel', () => {
  let container;

  beforeEach(() => {
    document.body.innerHTML = '';
    container = document.createElement('div');
    container.id = 'panel-correlations';
    document.body.appendChild(container);
  });

  it('renders matrix grid with mock correlation data', () => {
    render(container);
    update(makeCorrelationData());

    const wrap = document.getElementById('corr-matrix-wrap');
    expect(wrap).not.toBeNull();
    const grid = wrap.querySelector('.corr-grid');
    expect(grid).not.toBeNull();

    // 3 instruments: header row (1+3) + 3 data rows * (1+3) = 4+12 = 16 cells
    const cells = grid.querySelectorAll('div');
    expect(cells.length).toBeGreaterThanOrEqual(16);
  });

  it('cell colors: positive values have green background in style attribute', () => {
    render(container);
    update(makeCorrelationData());

    const wrap = document.getElementById('corr-matrix-wrap');
    const grid = wrap.querySelector('.corr-grid');
    const allCells = grid.querySelectorAll('div');

    // Find a cell with the positive correlation value 0.75
    // jsdom may not parse inline rgba in style.background, so check getAttribute
    let foundGreen = false;
    allCells.forEach((cell) => {
      if (cell.textContent.trim() === '0.75') {
        const styleAttr = cell.getAttribute('style') || '';
        // Green background uses rgba(63,185,80,...)
        expect(styleAttr).toContain('rgba(63,185,80');
        foundGreen = true;
      }
    });
    expect(foundGreen).toBe(true);
  });

  it('cell colors: negative values have red background in style attribute', () => {
    render(container);
    update(makeCorrelationData());

    const wrap = document.getElementById('corr-matrix-wrap');
    const grid = wrap.querySelector('.corr-grid');
    const allCells = grid.querySelectorAll('div');

    // Find a cell with the negative correlation value -0.45
    let foundRed = false;
    allCells.forEach((cell) => {
      if (cell.textContent.trim() === '-0.45') {
        const styleAttr = cell.getAttribute('style') || '';
        // Red background uses rgba(248,81,73,...)
        expect(styleAttr).toContain('rgba(248,81,73');
        foundRed = true;
      }
    });
    expect(foundRed).toBe(true);
  });

  it('diagonal cells show 1.00', () => {
    render(container);
    update(makeCorrelationData());

    const wrap = document.getElementById('corr-matrix-wrap');
    const grid = wrap.querySelector('.corr-grid');
    const allCells = grid.querySelectorAll('div');

    // Count cells displaying "1.00"
    let diagCount = 0;
    allCells.forEach((cell) => {
      if (cell.textContent.trim() === '1.00') {
        diagCount++;
      }
    });
    // Should have 3 diagonal cells with value 1.00
    expect(diagCount).toBe(3);
  });

  it('handles null data in update() gracefully', () => {
    render(container);
    update(null);

    // Should not throw; skeleton with loading message stays
    const wrap = document.getElementById('corr-matrix-wrap');
    expect(wrap).not.toBeNull();
  });
});
