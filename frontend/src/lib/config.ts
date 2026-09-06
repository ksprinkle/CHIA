/**
 * Base URL for the CHIA read-only API.
 *
 * A deployed (split-origin) build injects the absolute API origin at build
 * time through `VITE_API_BASE_URL`, e.g.
 * `https://chia-county-explorer-api.onrender.com/api/v1`.
 *
 * When it is unset -- local development and the test suite -- this falls back
 * to the root-relative `/api/v1`, which the Vite dev server proxies to the
 * FastAPI backend (see `vite.config.ts`). Keeping the fallback root-relative
 * (not base-prefixed) is deliberate: the proxy matches on the request path,
 * independently of the app's `base`.
 */
const configuredApiBaseUrl = import.meta.env.VITE_API_BASE_URL

export const API_BASE_URL =
  typeof configuredApiBaseUrl === 'string' && configuredApiBaseUrl.length > 0
    ? configuredApiBaseUrl
    : '/api/v1'
