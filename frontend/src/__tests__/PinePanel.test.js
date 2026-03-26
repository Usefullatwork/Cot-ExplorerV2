import { describe, it, expect, beforeEach, vi } from 'vitest';
import { render, update } from '../components/PinePanel.js';

describe('PinePanel', () => {
  let container;

  beforeEach(() => {
    document.body.innerHTML = '';
    container = document.createElement('div');
    container.id = 'panel-pine';
    document.body.appendChild(container);

    // Mock clipboard API
    Object.assign(navigator, {
      clipboard: {
        writeText: vi.fn().mockResolvedValue(undefined),
      },
    });

    // Mock fetch for pine file loading
    global.fetch = vi.fn().mockResolvedValue({
      ok: true,
      text: () => Promise.resolve('// Pine Script v5\nindicator("Test")'),
    });
  });

  it('renders the panel skeleton with heading "Pine Scripts"', () => {
    render(container);

    const heading = container.querySelector('.sh-t');
    expect(heading).not.toBeNull();
    expect(heading.textContent).toBe('Pine Scripts');
  });

  it('renders the TradingView v5 subtitle', () => {
    render(container);

    const sub = container.querySelector('.sh-b');
    expect(sub).not.toBeNull();
    expect(sub.textContent).toBe('TradingView v5');
  });

  it('renders script cards grouped by category', () => {
    render(container);

    const cards = container.querySelectorAll('.pine-card');
    expect(cards.length).toBeGreaterThanOrEqual(10);
  });

  it('renders category headings (Indicators, Strategies, Combos)', () => {
    render(container);

    const headings = container.querySelectorAll('.ct');
    const texts = Array.from(headings).map((h) => h.textContent);
    expect(texts.some((t) => t.includes('Indicators'))).toBe(true);
    expect(texts.some((t) => t.includes('Strategies'))).toBe(true);
    expect(texts.some((t) => t.includes('Combos'))).toBe(true);
  });

  it('renders the dropdown with script options', () => {
    render(container);

    const select = document.getElementById('pineScriptSelect');
    expect(select).not.toBeNull();

    const optgroups = select.querySelectorAll('optgroup');
    expect(optgroups.length).toBe(3);
  });

  it('renders statistics card with correct counts', () => {
    render(container);

    const statsText = container.textContent;
    expect(statsText).toContain('Indikatorer:');
    expect(statsText).toContain('Strategier:');
    expect(statsText).toContain('Komboer:');
    expect(statsText).toContain('Totalt:');
    expect(statsText).toContain('12');
  });

  it('renders a copy button on each script card', () => {
    render(container);

    const copyBtns = container.querySelectorAll('.pine-copy');
    expect(copyBtns.length).toBeGreaterThanOrEqual(10);
  });

  it('calls clipboard.writeText when copy button is clicked', async () => {
    render(container);

    const copyBtn = container.querySelector('.pine-copy');
    expect(copyBtn).not.toBeNull();
    copyBtn.click();

    // Wait for async fetch + clipboard
    await vi.waitFor(() => {
      expect(navigator.clipboard.writeText).toHaveBeenCalled();
    });
  });

  it('shows preview area when a card is clicked', async () => {
    render(container);

    const card = container.querySelector('.pine-card');
    expect(card).not.toBeNull();
    card.click();

    // Wait for async fetch
    await vi.waitFor(() => {
      const preview = document.getElementById('pinePreview');
      expect(preview.style.display).toBe('block');
    });
  });

  it('update() is a no-op and does not throw', () => {
    render(container);
    expect(() => update()).not.toThrow();
  });
});
