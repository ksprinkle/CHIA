/**
 * CE-DEP02: `API_BASE_URL` is deployment-aware.
 *
 * `lib/config.ts` reads `import.meta.env.VITE_API_BASE_URL` at module
 * evaluation, so each case stubs the env var, resets the module registry, and
 * re-imports the module.
 */

afterEach(() => {
  vi.unstubAllEnvs()
  vi.resetModules()
})

describe('API_BASE_URL (CE-DEP02)', () => {
  it('falls back to the root-relative /api/v1 when VITE_API_BASE_URL is unset', async () => {
    vi.stubEnv('VITE_API_BASE_URL', '')
    vi.resetModules()

    const { API_BASE_URL } = await import('./config')

    expect(API_BASE_URL).toBe('/api/v1')
  })

  it('uses VITE_API_BASE_URL verbatim when a deployed build supplies it', async () => {
    vi.stubEnv(
      'VITE_API_BASE_URL',
      'https://chia-county-explorer-api.onrender.com/api/v1',
    )
    vi.resetModules()

    const { API_BASE_URL } = await import('./config')

    expect(API_BASE_URL).toBe(
      'https://chia-county-explorer-api.onrender.com/api/v1',
    )
  })

  it('keeps the fallback root-relative (dev-proxy compatible), not base-prefixed', async () => {
    vi.stubEnv('VITE_API_BASE_URL', '')
    vi.resetModules()

    const { API_BASE_URL } = await import('./config')

    // Root-relative so it resolves against the origin and the Vite dev `/api`
    // proxy catches it regardless of the app's `base` (e.g. `/CHIA/`).
    expect(API_BASE_URL).toBe('/api/v1')
    expect(API_BASE_URL.startsWith('/api/')).toBe(true)
  })
})
