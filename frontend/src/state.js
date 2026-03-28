/**
 * Minimal pub/sub reactive store.
 *
 * Usage:
 *   import { state, subscribe, setState } from './state.js';
 *   subscribe('instruments', (data) => renderTickers(data));
 *   setState('instruments', fetchedData);
 */

/** Global application state */
export const state = {
  instruments:        null,
  signals:            null,
  macro:              null,
  cot:                null,
  cotSummary:         null,
  health:             null,
  metrics:            null,
  activeTab:          'setups',
  selectedInstrument: null,
  botStatus:          null,
  botPositions:       null,
  botSignals:         null,
  botConfig:          null,
  botHistory:         null,
  geointel:           null,
  geoSignals:         null,
  geoEvents:          null,
  regime:             null,
  correlations:       null,
  signalLog:          null,
};

/** @type {Map<string, Set<Function>>} */
const listeners = new Map();

/**
 * Subscribe to changes on a specific state key.
 * @param {string}   key
 * @param {Function} callback  Receives (newValue, key)
 * @returns {Function} Unsubscribe function
 */
export function subscribe(key, callback) {
  if (!listeners.has(key)) listeners.set(key, new Set());
  listeners.get(key).add(callback);
  return () => listeners.get(key).delete(callback);
}

/**
 * Update a state key and notify subscribers.
 * @param {string} key
 * @param {*}      value
 */
export function setState(key, value) {
  state[key] = value;
  const subs = listeners.get(key);
  if (subs) subs.forEach((fn) => fn(value, key));
}
