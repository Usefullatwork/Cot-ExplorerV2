import { describe, it, expect, beforeEach, vi } from 'vitest';
import { state, subscribe, setState } from '../state.js';

describe('state management', () => {
  // Reset state before each test to avoid cross-contamination
  beforeEach(() => {
    state.instruments = null;
    state.signals = null;
    state.macro = null;
    state.cot = null;
    state.cotSummary = null;
    state.health = null;
    state.metrics = null;
    state.activeTab = 'setups';
    state.selectedInstrument = null;
  });

  describe('state object', () => {
    it('has all expected initial keys', () => {
      expect(state).toHaveProperty('instruments');
      expect(state).toHaveProperty('signals');
      expect(state).toHaveProperty('macro');
      expect(state).toHaveProperty('cot');
      expect(state).toHaveProperty('cotSummary');
      expect(state).toHaveProperty('health');
      expect(state).toHaveProperty('metrics');
      expect(state).toHaveProperty('activeTab');
      expect(state).toHaveProperty('selectedInstrument');
    });

    it('defaults activeTab to "setups"', () => {
      expect(state.activeTab).toBe('setups');
    });

    it('defaults data keys to null', () => {
      expect(state.instruments).toBeNull();
      expect(state.signals).toBeNull();
      expect(state.cot).toBeNull();
    });
  });

  describe('setState', () => {
    it('updates the state value', () => {
      setState('activeTab', 'macro');
      expect(state.activeTab).toBe('macro');
    });

    it('updates with complex objects', () => {
      const instruments = { EURUSD: { price: 1.085 }, Gold: { price: 2050 } };
      setState('instruments', instruments);
      expect(state.instruments).toBe(instruments);
    });

    it('can set values to null', () => {
      setState('activeTab', 'cot');
      setState('activeTab', null);
      expect(state.activeTab).toBeNull();
    });
  });

  describe('subscribe', () => {
    it('calls the callback when the subscribed key changes', () => {
      const cb = vi.fn();
      subscribe('signals', cb);

      const data = [{ key: 'EURUSD', grade: 'A+' }];
      setState('signals', data);

      expect(cb).toHaveBeenCalledOnce();
      expect(cb).toHaveBeenCalledWith(data, 'signals');
    });

    it('does not call the callback for a different key', () => {
      const cb = vi.fn();
      subscribe('signals', cb);

      setState('macro', { gdp: 2.1 });

      expect(cb).not.toHaveBeenCalled();
    });

    it('supports multiple subscribers on the same key', () => {
      const cb1 = vi.fn();
      const cb2 = vi.fn();
      subscribe('cot', cb1);
      subscribe('cot', cb2);

      setState('cot', []);

      expect(cb1).toHaveBeenCalledOnce();
      expect(cb2).toHaveBeenCalledOnce();
    });

    it('returns an unsubscribe function', () => {
      const cb = vi.fn();
      const unsub = subscribe('health', cb);

      setState('health', { status: 'ok' });
      expect(cb).toHaveBeenCalledOnce();

      unsub();
      setState('health', { status: 'down' });
      expect(cb).toHaveBeenCalledOnce(); // still 1, not 2
    });

    it('handles unsubscribe when called multiple times', () => {
      const cb = vi.fn();
      const unsub = subscribe('activeTab', cb);

      unsub();
      unsub(); // should not throw

      setState('activeTab', 'cot');
      expect(cb).not.toHaveBeenCalled();
    });

    it('subscriber receives the new value', () => {
      let received = null;
      subscribe('selectedInstrument', (val) => {
        received = val;
      });

      setState('selectedInstrument', 'EURUSD');
      expect(received).toBe('EURUSD');
    });

    it('subscriber receives the key as second argument', () => {
      let receivedKey = null;
      subscribe('metrics', (_, key) => {
        receivedKey = key;
      });

      setState('metrics', {});
      expect(receivedKey).toBe('metrics');
    });
  });
});
