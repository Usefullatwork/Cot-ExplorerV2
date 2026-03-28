import { describe, it, expect } from 'vitest';
import { renderSparkline, renderScoreDots } from '../charts/svgSparkline.js';

describe('renderSparkline', () => {
  it('returns empty string for insufficient data', () => {
    expect(renderSparkline([])).toBe('');
    expect(renderSparkline([1])).toBe('');
    expect(renderSparkline(null)).toBe('');
  });

  it('returns an SVG string for valid data', () => {
    const svg = renderSparkline([1, 2, 3, 4, 5]);
    expect(svg).toContain('<svg');
    expect(svg).toContain('</svg>');
    expect(svg).toContain('<polyline');
  });

  it('uses green color for uptrend by default', () => {
    const svg = renderSparkline([1, 2, 3]);
    expect(svg).toContain('#3fb950');
  });

  it('uses red color for downtrend by default', () => {
    const svg = renderSparkline([3, 2, 1]);
    expect(svg).toContain('#f85149');
  });

  it('respects custom color', () => {
    const svg = renderSparkline([1, 2, 3], { color: '#ff00ff' });
    expect(svg).toContain('#ff00ff');
  });

  it('respects custom width and height', () => {
    const svg = renderSparkline([1, 2, 3], { width: 100, height: 40 });
    expect(svg).toContain('width="100"');
    expect(svg).toContain('height="40"');
  });

  it('generates correct number of points in polyline', () => {
    const svg = renderSparkline([10, 20, 30, 40]);
    // polyline points attribute has exactly 4 point pairs
    const match = svg.match(/<polyline[^>]+points="([^"]+)"/);
    expect(match).not.toBeNull();
    const points = match[1].trim().split(' ');
    expect(points.length).toBe(4);
  });

  it('includes area fill by default', () => {
    const svg = renderSparkline([1, 2, 3]);
    expect(svg).toContain('<polygon');
  });

  it('omits area fill when fill=false', () => {
    const svg = renderSparkline([1, 2, 3], { fill: false });
    expect(svg).not.toContain('<polygon');
  });

  it('handles flat data', () => {
    const svg = renderSparkline([5, 5, 5, 5]);
    expect(svg).toContain('<svg');
  });

  it('handles negative values', () => {
    const svg = renderSparkline([-3, -2, -1, 0, 1]);
    expect(svg).toContain('<svg');
  });
});

describe('renderScoreDots', () => {
  it('returns empty string for empty input', () => {
    expect(renderScoreDots([])).toBe('');
    expect(renderScoreDots(null)).toBe('');
  });

  it('renders correct number of dots', () => {
    const details = [
      { kryss: 'COT', verdi: true },
      { kryss: 'SMC', verdi: false },
      { kryss: 'Trend', verdi: true },
    ];
    const html = renderScoreDots(details);
    const dots = html.match(/<span/g);
    expect(dots.length).toBe(3);
  });

  it('uses bull color for passing dots', () => {
    const html = renderScoreDots([{ kryss: 'Test', verdi: true }]);
    expect(html).toContain('var(--bull)');
  });

  it('uses b2 color for failing dots', () => {
    const html = renderScoreDots([{ kryss: 'Test', verdi: false }]);
    expect(html).toContain('var(--b2)');
  });

  it('includes tooltip title', () => {
    const html = renderScoreDots([{ kryss: 'COT Bias', verdi: true }]);
    expect(html).toContain('title="COT Bias"');
  });
});
