import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';

// Mock Chart.js — use function (not arrow) so it works as a constructor
vi.mock('chart.js', () => {
  function MockChart() {
    this.destroy = vi.fn();
    this.update = vi.fn();
  }
  MockChart.register = vi.fn();
  return { Chart: MockChart, registerables: [] };
});

describe('vixTermChart', () => {
  let createVixTermChart, destroyVixTermChart;

  beforeEach(async () => {
    const mod = await import('../charts/vixTermChart.js');
    createVixTermChart = mod.createVixTermChart;
    destroyVixTermChart = mod.destroyVixTermChart;
  });

  afterEach(() => {
    destroyVixTermChart();
  });

  it('should return null if no canvas provided', () => {
    expect(createVixTermChart(null, { spot: 15 })).toBeNull();
  });

  it('should return null if no data provided', () => {
    const canvas = document.createElement('canvas');
    expect(createVixTermChart(canvas, null)).toBeNull();
  });

  it('should create chart with contango data', () => {
    const canvas = document.createElement('canvas');
    const result = createVixTermChart(canvas, {
      vix_9d: 14, spot: 15, vix_3m: 18, regime: 'contango', spread: 3.0,
    });
    expect(result).toBeTruthy();
  });

  it('should create chart with backwardation data', () => {
    const canvas = document.createElement('canvas');
    const result = createVixTermChart(canvas, {
      vix_9d: 28, spot: 25, vix_3m: 20, regime: 'backwardation', spread: -5.0,
    });
    expect(result).toBeTruthy();
  });

  it('should handle zero values gracefully', () => {
    const canvas = document.createElement('canvas');
    const result = createVixTermChart(canvas, {
      vix_9d: 0, spot: 0, vix_3m: 0, regime: 'unknown', spread: 0,
    });
    expect(result).toBeTruthy();
  });

  it('should destroy existing chart before creating new one', () => {
    const canvas = document.createElement('canvas');
    createVixTermChart(canvas, { vix_9d: 14, spot: 15, vix_3m: 18, spread: 3 });
    // Creating again should destroy first
    createVixTermChart(canvas, { vix_9d: 20, spot: 22, vix_3m: 25, spread: 3 });
    // No error means destroy worked
  });

  it('destroyVixTermChart should be safe to call multiple times', () => {
    destroyVixTermChart();
    destroyVixTermChart();
    // No error
  });

  it('should handle missing spread field', () => {
    const canvas = document.createElement('canvas');
    const result = createVixTermChart(canvas, { vix_9d: 14, spot: 15, vix_3m: 18 });
    expect(result).toBeTruthy();
  });
});
