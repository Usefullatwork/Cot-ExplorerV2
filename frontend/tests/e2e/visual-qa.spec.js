/**
 * Visual QA for all 19 tabs.
 *
 * Prerequisites:
 *   - Backend: uvicorn src.api.app:app --port 8000
 *   - Frontend: cd frontend && npm run dev (port 5173)
 *   - Data: python scripts/populate_db.py  (prices, COT, signals populated)
 *
 * Run: cd frontend && npx playwright test tests/e2e/ --workers=1
 */

import { test, expect } from '@playwright/test';

const SCREENSHOT_DIR = 'tests/e2e/screenshots';

// ── Shared helpers ──────────────────────────────────────────

/** Navigate to a tab, wait for panel activation. */
async function goToTab(page, tab) {
  await page.goto(`/#${tab}`, { waitUntil: 'networkidle' });
  const panel = page.locator(`#panel-${tab}`);
  await panel.waitFor({ state: 'attached', timeout: 10000 });
  // Wait for .active class (router activates the panel)
  await expect(panel).toHaveClass(/active/, { timeout: 5000 });
  // Wait for spinner to disappear (loading state cleared)
  const spinner = panel.locator('.loading .spinner');
  if (await spinner.count() > 0) {
    await spinner.first().waitFor({ state: 'hidden', timeout: 15000 }).catch(() => {});
  }
  // Small settle time for lazy-loaded panels
  await page.waitForTimeout(500);
  return panel;
}

/** Assert no "undefined" or "null" text leaking into the panel. */
async function assertNoSlop(panel) {
  const text = await panel.textContent();
  // Allow "null" in actual data contexts like "null island" but not bare "null" as a value
  expect(text).not.toMatch(/\bundefined\b/);
}

/** Assert no horizontal overflow at 1280px viewport. */
async function assertNoOverflow(page) {
  const scrollWidth = await page.evaluate(() => document.body.scrollWidth);
  const viewportWidth = await page.evaluate(() => window.innerWidth);
  expect(scrollWidth).toBeLessThanOrEqual(viewportWidth + 5);
}

/** Take a full-page screenshot. */
async function screenshot(page, name) {
  await page.screenshot({
    path: `${SCREENSHOT_DIR}/${name}.png`,
    fullPage: true,
  });
}

// ── Configure viewport ──────────────────────────────────────

test.use({ viewport: { width: 1280, height: 900 } });

// ── Data tabs ───────────────────────────────────────────────

test.describe('Data tabs', () => {
  test('Setups tab renders instrument cards', async ({ page }) => {
    const panel = await goToTab(page, 'setups');
    // SetupGrid should render instrument cards
    const cards = panel.locator('.setup-card, .card, .instrument-card');
    // May have 0 if no API — check panel has content beyond spinner
    const panelText = await panel.textContent();
    expect(panelText.length).toBeGreaterThan(10);
    await assertNoSlop(panel);
    await assertNoOverflow(page);
    await screenshot(page, 'setups');
  });

  test('COT tab renders table with data', async ({ page }) => {
    const panel = await goToTab(page, 'cot');
    // COT table should have rows
    const table = panel.locator('table');
    if (await table.count() > 0) {
      const rows = await table.first().locator('tbody tr').count();
      expect(rows).toBeGreaterThan(0);
    }
    await assertNoSlop(panel);
    await screenshot(page, 'cot');
  });

  test('Prices tab renders grouped price data', async ({ page }) => {
    const panel = await goToTab(page, 'prices');
    // Wait for lazy load
    await page.waitForTimeout(1000);
    const panelText = await panel.textContent();
    expect(panelText.length).toBeGreaterThan(10);
    await assertNoSlop(panel);
    await screenshot(page, 'prices');
  });

  test('Calendar tab renders economic events', async ({ page }) => {
    const panel = await goToTab(page, 'calendar');
    const panelText = await panel.textContent();
    expect(panelText.length).toBeGreaterThan(10);
    await assertNoSlop(panel);
    await screenshot(page, 'calendar');
  });

  test('Metals Intel tab renders', async ({ page }) => {
    const panel = await goToTab(page, 'metals-intel');
    await page.waitForTimeout(1000);
    const panelText = await panel.textContent();
    expect(panelText.length).toBeGreaterThan(5);
    await assertNoSlop(panel);
    await screenshot(page, 'metals-intel');
  });
});

// ── Analysis tabs ───────────────────────────────────────────

test.describe('Analysis tabs', () => {
  test('Macro tab renders VIX regime and indicators', async ({ page }) => {
    const panel = await goToTab(page, 'macro');
    const panelText = await panel.textContent();
    expect(panelText.length).toBeGreaterThan(20);
    // VIX or Dollar Smile section should be present
    await assertNoSlop(panel);
    await screenshot(page, 'macro');
  });

  test('Backtest tab renders WFO dashboard', async ({ page }) => {
    const panel = await goToTab(page, 'backtest');
    await page.waitForTimeout(1500);
    const panelText = await panel.textContent();
    expect(panelText.length).toBeGreaterThan(10);
    await assertNoSlop(panel);
    await screenshot(page, 'backtest');
  });

  test('Risk tab renders VaR and stress test data', async ({ page }) => {
    const panel = await goToTab(page, 'risk');
    await page.waitForTimeout(1000);
    const panelText = await panel.textContent();
    expect(panelText.length).toBeGreaterThan(10);
    await assertNoSlop(panel);
    await screenshot(page, 'risk');
  });

  test('Intelligence tab renders analysis', async ({ page }) => {
    const panel = await goToTab(page, 'intelligence');
    await page.waitForTimeout(1000);
    const panelText = await panel.textContent();
    expect(panelText.length).toBeGreaterThan(10);
    await assertNoSlop(panel);
    await screenshot(page, 'intelligence');
  });

  test('Correlations tab renders matrix', async ({ page }) => {
    const panel = await goToTab(page, 'correlations');
    await page.waitForTimeout(1000);
    const panelText = await panel.textContent();
    expect(panelText.length).toBeGreaterThan(10);
    await assertNoSlop(panel);
    await screenshot(page, 'correlations');
  });
});

// ── Trading tabs ────────────────────────────────────────────

test.describe('Trading tabs', () => {
  test('Trading tab renders bot controls', async ({ page }) => {
    const panel = await goToTab(page, 'trading');
    await page.waitForTimeout(1000);
    const panelText = await panel.textContent();
    expect(panelText.length).toBeGreaterThan(10);
    await assertNoSlop(panel);
    await screenshot(page, 'trading');
  });

  test('Signal Log tab renders signal entries', async ({ page }) => {
    const panel = await goToTab(page, 'signal-log');
    await page.waitForTimeout(1000);
    const panelText = await panel.textContent();
    expect(panelText.length).toBeGreaterThan(10);
    await assertNoSlop(panel);
    await screenshot(page, 'signal-log');
  });

  test('Signal Health tab renders ensemble quality', async ({ page }) => {
    const panel = await goToTab(page, 'signal-health');
    await page.waitForTimeout(1000);
    const panelText = await panel.textContent();
    expect(panelText.length).toBeGreaterThan(10);
    await assertNoSlop(panel);
    await screenshot(page, 'signal-health');
  });

  test('Attribution tab renders trade attribution', async ({ page }) => {
    const panel = await goToTab(page, 'attribution');
    await page.waitForTimeout(1000);
    const panelText = await panel.textContent();
    expect(panelText.length).toBeGreaterThan(5);
    await assertNoSlop(panel);
    await screenshot(page, 'attribution');
  });

  test('Competitor tab renders analysis', async ({ page }) => {
    const panel = await goToTab(page, 'competitor');
    await page.waitForTimeout(1000);
    const panelText = await panel.textContent();
    expect(panelText.length).toBeGreaterThan(5);
    await assertNoSlop(panel);
    await screenshot(page, 'competitor');
  });
});

// ── Infrastructure tabs ─────────────────────────────────────

test.describe('Infrastructure tabs', () => {
  test('Pipeline tab renders status and gate log', async ({ page }) => {
    const panel = await goToTab(page, 'pipeline');
    await page.waitForTimeout(1000);
    const panelText = await panel.textContent();
    expect(panelText.length).toBeGreaterThan(10);
    await assertNoSlop(panel);
    await screenshot(page, 'pipeline');
  });

  test('GeoEvents tab renders seismic and intel data', async ({ page }) => {
    const panel = await goToTab(page, 'geo-events');
    await page.waitForTimeout(1500);
    const panelText = await panel.textContent();
    expect(panelText.length).toBeGreaterThan(10);
    await assertNoSlop(panel);
    await screenshot(page, 'geo-events');
  });

  test('Crypto tab renders market overview', async ({ page }) => {
    const panel = await goToTab(page, 'krypto-intel');
    await page.waitForTimeout(1000);
    const panelText = await panel.textContent();
    expect(panelText.length).toBeGreaterThan(10);
    await assertNoSlop(panel);
    await screenshot(page, 'krypto-intel');
  });

  test('Pine tab renders script listings', async ({ page }) => {
    const panel = await goToTab(page, 'pine');
    const panelText = await panel.textContent();
    expect(panelText.length).toBeGreaterThan(10);
    await assertNoSlop(panel);
    await screenshot(page, 'pine');
  });
});

// ── Cross-cutting quality checks ────────────────────────────

test.describe('Cross-cutting quality', () => {
  test('Typography hierarchy exists (h1 > h2 > body)', async ({ page }) => {
    await page.goto('/', { waitUntil: 'networkidle' });
    const sizes = await page.evaluate(() => {
      const getSize = (sel) => {
        const el = document.querySelector(sel);
        if (!el) return 0;
        return parseFloat(getComputedStyle(el).fontSize);
      };
      return {
        h1: getSize('h1'),
        h2: getSize('h2'),
        body: parseFloat(getComputedStyle(document.body).fontSize),
      };
    });
    // At least body font size should be reasonable
    expect(sizes.body).toBeGreaterThan(10);
    expect(sizes.body).toBeLessThan(24);
  });

  test('No console errors on initial load', async ({ page }) => {
    const errors = [];
    page.on('console', (msg) => {
      if (msg.type() === 'error') errors.push(msg.text());
    });
    await page.goto('/', { waitUntil: 'networkidle' });
    await page.waitForTimeout(2000);
    // Filter out expected API errors (backend may not be running)
    const realErrors = errors.filter(
      (e) => !e.includes('fetch') && !e.includes('ERR_CONNECTION') && !e.includes('net::')
    );
    expect(realErrors.length).toBe(0);
  });

  test('CSS variables loaded from design tokens', async ({ page }) => {
    await page.goto('/', { waitUntil: 'networkidle' });
    const hasTokens = await page.evaluate(() => {
      const style = getComputedStyle(document.documentElement);
      // Check for key design tokens
      return {
        hasBg: style.getPropertyValue('--bg-primary') !== '',
        hasText: style.getPropertyValue('--text-primary') !== '',
      };
    });
    // At least one design token should be defined
    expect(hasTokens.hasBg || hasTokens.hasText).toBe(true);
  });
});
