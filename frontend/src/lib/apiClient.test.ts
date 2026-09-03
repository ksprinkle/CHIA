import { API_BASE_URL } from './config'
import {
  ApiError,
  NotFoundError,
  getCountyExplorer,
  listCounties,
} from './apiClient'
import type { CountyListResponse } from './types'

interface FakeResponseInit {
  status?: number
  ok?: boolean
}

function fakeResponse(body: unknown, init: FakeResponseInit = {}): Response {
  const status = init.status ?? 200
  const ok = init.ok ?? (status >= 200 && status < 300)
  return {
    ok,
    status,
    json: async () => body,
  } as Response
}

afterEach(() => {
  vi.restoreAllMocks()
  vi.unstubAllGlobals()
})

describe('apiClient (read-only)', () => {
  it('listCounties() issues GET {base}/counties and returns the parsed body', async () => {
    const payload: CountyListResponse = {
      count: 1,
      counties: [
        {
          county_fips: '01001',
          state_fips: '01',
          state_abbr: 'AL',
          county_name: '0',
          state_name: '',
        },
      ],
    }
    const fetchMock = vi.fn().mockResolvedValue(fakeResponse(payload))
    vi.stubGlobal('fetch', fetchMock)

    const result = await listCounties()

    expect(fetchMock).toHaveBeenCalledTimes(1)
    const [url, init] = fetchMock.mock.calls[0]
    expect(url).toBe(`${API_BASE_URL}/counties`)
    expect(init).toMatchObject({ method: 'GET', headers: { Accept: 'application/json' } })
    expect(result).toEqual(payload)
  })

  it('getCountyExplorer() targets the explorer path for the given FIPS', async () => {
    const fetchMock = vi.fn().mockResolvedValue(fakeResponse({}))
    vi.stubGlobal('fetch', fetchMock)

    await getCountyExplorer('01001')

    expect(fetchMock.mock.calls[0][0]).toBe(`${API_BASE_URL}/counties/01001/explorer`)
  })

  it('maps HTTP 404 to NotFoundError (distinct from a server failure)', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue(fakeResponse({ detail: 'no such county' }, { status: 404 })),
    )

    await expect(getCountyExplorer('99999')).rejects.toBeInstanceOf(NotFoundError)
  })

  it('maps other non-2xx responses to ApiError with the status', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue(fakeResponse({}, { status: 503 })),
    )

    await expect(listCounties()).rejects.toMatchObject({
      name: 'ApiError',
      status: 503,
    })
  })

  it('maps a network failure to ApiError (not NotFoundError)', async () => {
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new TypeError('network down')))

    const error = await listCounties().catch((caught: unknown) => caught)
    expect(error).toBeInstanceOf(ApiError)
    expect(error).not.toBeInstanceOf(NotFoundError)
  })

  it('exports only fetch wrappers -- no county list or analytical helpers', async () => {
    const module = await import('./apiClient')
    expect(Object.keys(module).sort()).toEqual(
      ['ApiError', 'NotFoundError', 'getCountyExplorer', 'listCounties'].sort(),
    )
  })
})
