import { describe, it, expect, beforeEach } from 'vitest';
import { render, update, updateFng, stopPolling } from '../components/CryptoPanel.js';

function makeCoin(overrides = {}) {
  return {
    id: 'bitcoin',
    symbol: 'BTC',
    name: 'Bitcoin',
    price: 65000,
    market_cap: 1_300_000_000_000,
    volume_24h: 30_000_000_000,
    change_24h: 2.5,
    rank: 1,
    image: '',
    ...overrides,
  };
}

describe('CryptoPanel', () => {
  let container;

  beforeEach(() => {
    stopPolling();
    document.body.innerHTML = '';
    container = document.createElement('div');
    container.id = 'panel-krypto-intel';
    document.body.appendChild(container);
  });

  it('renders skeleton with heading', () => {
    render(container);
    const heading = container.querySelector('.sh-t');
    expect(heading.textContent).toBe('Krypto Intel');
  });

  it('renders loading state', () => {
    render(container);
    expect(container.textContent).toContain('Laster kryptomarked');
  });

  it('updates with market data', () => {
    render(container);
    update({
      coins: [makeCoin(), makeCoin({ id: 'ethereum', symbol: 'ETH', name: 'Ethereum', price: 3500 })],
      total_market_cap: 1_720_000_000_000,
      btc_dominance: 75.6,
    });

    const content = document.getElementById('kryptoContent');
    expect(content.textContent).toContain('BTC');
    expect(content.textContent).toContain('ETH');
    expect(content.textContent).toContain('75.6%');
  });

  it('renders coin cards with price and change', () => {
    render(container);
    update({ coins: [makeCoin()], total_market_cap: 1e12, btc_dominance: 50 });

    const cards = document.querySelectorAll('.card');
    // 2 summary cards (market cap, dominance) + 1 coin card
    expect(cards.length).toBeGreaterThanOrEqual(3);
  });

  it('handles null data gracefully', () => {
    render(container);
    update(null);
    // Should not crash, content unchanged
    expect(document.getElementById('kryptoContent').textContent).toContain('Laster');
  });

  it('updates Fear & Greed gauge', () => {
    render(container);
    updateFng({ value: 15, label: 'Extreme Fear' });

    const fng = document.getElementById('kryptoFng');
    expect(fng.textContent).toContain('15');
    expect(fng.textContent).toContain('Ekstrem frykt');
  });

  it('Fear & Greed gauge handles high value', () => {
    render(container);
    updateFng({ value: 85, label: 'Extreme Greed' });

    const fng = document.getElementById('kryptoFng');
    expect(fng.textContent).toContain('85');
    expect(fng.textContent).toContain('Ekstrem gradighet');
  });

  it('updates timestamp on data update', () => {
    render(container);
    update({ coins: [makeCoin()], total_market_cap: 1e12, btc_dominance: 50 });

    const ts = document.getElementById('kryptoUpdated');
    expect(ts.textContent).toContain('Oppdatert');
  });

  it('escapes HTML in coin names', () => {
    render(container);
    update({
      coins: [makeCoin({ name: '<script>xss</script>', symbol: 'XSS' })],
      total_market_cap: 1e12,
      btc_dominance: 50,
    });

    const content = document.getElementById('kryptoContent');
    expect(content.innerHTML).not.toContain('<script>');
    expect(content.textContent).toContain('XSS');
  });
});
