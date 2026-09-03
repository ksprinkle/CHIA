/**
 * Base path for the CHIA read-only API.
 *
 * In development the Vite dev server proxies `/api` to the FastAPI backend
 * (see `vite.config.ts`). In a deployed context the frontend is expected to be
 * served from the same origin as the API, so a relative base works there too.
 */
export const API_BASE_URL = '/api/v1'
