/// <reference types="vite/client" />

interface ImportMetaEnv {
  /**
   * CE-DEP02: absolute API base URL supplied by a deployed build (e.g.
   * `https://chia-county-explorer-api.onrender.com/api/v1`). Unset in local
   * development and tests, where `lib/config.ts` falls back to `/api/v1`.
   */
  readonly VITE_API_BASE_URL?: string
}

interface ImportMeta {
  readonly env: ImportMetaEnv
}
