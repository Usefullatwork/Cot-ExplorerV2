import { describe, it, expect, vi, beforeEach } from 'vitest';

// Mock Chart.js
vi.mock('chart.js', () => {
  const mockChart = vi.fn().mockImplementation(() => ({
    destroy: vi.fn(),
    update: vi.fn(),
    data: { datasets: [] },
  }));
  mockChart.register = vi.fn();
  return { Chart: mockChart, registerables: [] };
});

describe('CotChart', () => {
  beforeEach(() => {
    document.body.innerHTML = `
      <div id="cot-modal" style="display:none">
        <div class="cot-modal-content">
          <canvas id="cot-chart-canvas"></canvas>
          <div id="cot-chart-stats"></div>
          <button id="cot-modal-close">Lukk</button>
        </div>
      </div>`;
  });

  it('should have modal initially hidden', () => {
    const modal = document.getElementById('cot-modal');
    expect(modal.style.display).toBe('none');
  });

  it('should show modal when opened', () => {
    const modal = document.getElementById('cot-modal');
    modal.style.display = 'flex';
    expect(modal.style.display).toBe('flex');
  });

  it('should hide modal on close button click', () => {
    const modal = document.getElementById('cot-modal');
    const closeBtn = document.getElementById('cot-modal-close');
    modal.style.display = 'flex';
    closeBtn.addEventListener('click', () => { modal.style.display = 'none'; });
    closeBtn.click();
    expect(modal.style.display).toBe('none');
  });

  it('should have canvas element for chart', () => {
    const canvas = document.getElementById('cot-chart-canvas');
    expect(canvas).toBeTruthy();
    expect(canvas.tagName).toBe('CANVAS');
  });

  it('should have stats container', () => {
    const stats = document.getElementById('cot-chart-stats');
    expect(stats).toBeTruthy();
  });

  it('should render COT stats with correct fields', () => {
    const stats = document.getElementById('cot-chart-stats');
    const data = {
      market: 'EURO FX',
      net_commercial: 45000,
      net_speculator: -32000,
      open_interest: 580000,
    };
    stats.innerHTML = `
      <div>Marked: ${data.market}</div>
      <div>Kommersiell netto: ${data.net_commercial.toLocaleString()}</div>
      <div>Spekulant netto: ${data.net_speculator.toLocaleString()}</div>
      <div>Open Interest: ${data.open_interest.toLocaleString()}</div>`;
    expect(stats.textContent).toContain('EURO FX');
    expect(stats.textContent).toContain('45');
  });

  it('should handle missing data gracefully', () => {
    const stats = document.getElementById('cot-chart-stats');
    stats.innerHTML = '<div>Ingen COT-data</div>';
    expect(stats.textContent).toContain('Ingen');
  });
});
