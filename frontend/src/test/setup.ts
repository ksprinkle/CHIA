import '@testing-library/jest-dom/vitest'

/*
 * React Router 6.4 builds a `Request` object during client-side navigation.
 * In the jsdom test environment the `AbortSignal` React Router attaches comes
 * from jsdom, which undici's global `Request` rejects
 * ("Expected signal to be an instance of AbortSignal").
 *
 * The CE-C02 route table defines no loaders or actions, so this `Request` is
 * only used to read the target URL. A permissive test-only shim is sufficient
 * and has no effect on the application build or on `fetch` (which the tests
 * stub directly).
 */
class TestRequest {
  readonly url: string
  readonly method: string
  readonly signal: unknown

  constructor(
    input: string | URL | { url: string },
    init?: { method?: string; signal?: unknown },
  ) {
    this.url =
      typeof input === 'string' || input instanceof URL
        ? String(input)
        : input.url
    this.method = init?.method ?? 'GET'
    this.signal = init?.signal ?? null
  }
}

globalThis.Request = TestRequest as unknown as typeof Request
