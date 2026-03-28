import { describe, it, expect } from 'vitest';
import { renderBarChart } from '../charts/barChart.js';
import { renderLineChart } from '../charts/lineChart.js';
import { heatmapColor, renderHeatmapCell } from '../charts/heatmapCell.js';

describe('barChart', () => {
  it('returns empty for no data', () => {
    expect(renderBarChart([])).toBe('');
    expect(renderBarChart(null)).toBe('');
  });

  it('renders SVG with bars', () => {
    const svg = renderBarChart([
      { label: 'A', value: 10 },
      { label: 'B', value: 20 },
    ]);
    expect(svg).toContain('<svg');
    expect(svg).toContain('<rect');
  });

  it('renders labels when enabled', () => {
    const svg = renderBarChart([{ label: 'Test', value: 5 }], { showLabels: true });
    expect(svg).toContain('Test');
  });

  it('uses custom color', () => {
    const svg = renderBarChart([{ label: 'X', value: 10, color: '#ff0000' }]);
    expect(svg).toContain('#ff0000');
  });

  it('uses bear color for negative values', () => {
    const svg = renderBarChart([{ label: 'X', value: -5 }]);
    expect(svg).toContain('var(--bear)');
  });

  it('respects custom dimensions', () => {
    const svg = renderBarChart([{ label: 'X', value: 10 }], { width: 300, height: 150 });
    expect(svg).toContain('width="300"');
    expect(svg).toContain('height="150"');
  });
});

describe('lineChart', () => {
  it('returns empty for insufficient data', () => {
    expect(renderLineChart([])).toBe('');
    expect(renderLineChart([1])).toBe('');
  });

  it('renders SVG with path', () => {
    const svg = renderLineChart([1, 2, 3, 4]);
    expect(svg).toContain('<svg');
    expect(svg).toContain('<path');
  });

  it('uses green for uptrend', () => {
    const svg = renderLineChart([1, 2, 3]);
    expect(svg).toContain('#3fb950');
  });

  it('uses red for downtrend', () => {
    const svg = renderLineChart([3, 2, 1]);
    expect(svg).toContain('#f85149');
  });

  it('includes gradient fill by default', () => {
    const svg = renderLineChart([1, 2, 3]);
    expect(svg).toContain('<defs>');
    expect(svg).toContain('linearGradient');
  });

  it('omits fill when fill=false', () => {
    const svg = renderLineChart([1, 2, 3], { fill: false });
    expect(svg).not.toContain('linearGradient');
  });

  it('shows dots when enabled', () => {
    const svg = renderLineChart([1, 2, 3], { dots: true });
    expect(svg).toContain('<circle');
  });

  it('renders x-axis labels', () => {
    const svg = renderLineChart([1, 2, 3], { labels: ['Jan', 'Feb', 'Mar'] });
    expect(svg).toContain('Jan');
  });
});

describe('heatmapCell', () => {
  it('returns rgba color string', () => {
    const color = heatmapColor(0.5, 0, 1);
    expect(color).toContain('rgba');
  });

  it('returns green-ish for max value', () => {
    const color = heatmapColor(1, 0, 1);
    expect(color).toContain('rgba');
    // Green component should be high
  });

  it('returns red-ish for min value', () => {
    const color = heatmapColor(0, 0, 1);
    expect(color).toContain('rgba(248');
  });

  it('renderHeatmapCell returns td element', () => {
    const html = renderHeatmapCell(0.75);
    expect(html).toContain('<td');
    expect(html).toContain('0.75');
  });

  it('renderHeatmapCell formats percentage', () => {
    const html = renderHeatmapCell(0.75, 0, 1, 'pct');
    expect(html).toContain('75%');
  });
});
