/**
 * Test setup file for frontend tests
 * Configures the testing environment for React components
 */

import { expect, afterEach } from 'vitest';
import { cleanup } from '@testing-library/react';
import * as matchers from '@testing-library/jest-dom/matchers';

// Node >= 22 defines a global `localStorage` getter that resolves to undefined
// unless started with --localstorage-file; it shadows jsdom's storage, so
// components that persist state would crash under jsdom. Install a minimal
// in-memory Storage (same semantics as the Web Storage API) for the tests.
class MemoryStorage {
  constructor() {
    this._map = new Map();
  }

  get length() {
    return this._map.size;
  }

  key(index) {
    return Array.from(this._map.keys())[index] ?? null;
  }

  getItem(key) {
    const k = String(key);
    return this._map.has(k) ? this._map.get(k) : null;
  }

  setItem(key, value) {
    this._map.set(String(key), String(value));
  }

  removeItem(key) {
    this._map.delete(String(key));
  }

  clear() {
    this._map.clear();
  }
}

const storage = new MemoryStorage();
for (const target of new Set([globalThis, typeof window !== 'undefined' ? window : null])) {
  if (target) {
    Object.defineProperty(target, 'localStorage', {
      value: storage,
      configurable: true,
      writable: true,
    });
  }
}

// Extend Vitest's expect with jest-dom matchers
expect.extend(matchers);

// Cleanup after each test
afterEach(() => {
  cleanup();
});
