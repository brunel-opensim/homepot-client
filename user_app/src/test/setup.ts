import '@testing-library/jest-dom'

// Node 22+ ships an experimental `localStorage` global that is `undefined`
// unless `--localstorage-file` is provided, and it shadows jsdom's own
// `window.localStorage` (leaving both undefined). `sessionStorage` is
// unaffected. Provide a minimal in-memory polyfill so production code and
// tests that touch `localStorage` run in CI without a localstorage file.
if (typeof globalThis.localStorage === 'undefined') {
  const store = new Map<string, string>()
  const api: Storage = {
    get length() {
      return store.size
    },
    clear() {
      store.clear()
    },
    getItem(key: string) {
      return store.has(key) ? store.get(key)! : null
    },
    key(index: number) {
      return Array.from(store.keys())[index] ?? null
    },
    removeItem(key: string) {
      store.delete(key)
    },
    setItem(key: string, value: string) {
      store.set(key, String(value))
    },
  }
  Object.defineProperty(globalThis, 'localStorage', { value: api, configurable: true })
  Object.defineProperty(globalThis.window ?? globalThis, 'localStorage', { value: api, configurable: true })
}
