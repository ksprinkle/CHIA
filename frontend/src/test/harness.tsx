import { render } from '@testing-library/react'
import { RouterProvider, createMemoryRouter } from 'react-router-dom'

import { CountyDirectoryProvider } from '../lib/countyDirectory'
import { routes } from '../router'
import type { CountyListResponse } from '../lib/types'

type FetchImpl = (...args: unknown[]) => Promise<Response> | Response

/** Stub the global `fetch` for `GET /api/v1/counties` (Vitest, no MSW). */
export function stubCountiesFetch(payload: CountyListResponse | Error | FetchImpl) {
  let impl: FetchImpl
  if (typeof payload === 'function') {
    impl = payload
  } else if (payload instanceof Error) {
    impl = () => {
      throw payload
    }
  } else {
    impl = async () =>
      ({ ok: true, status: 200, json: async () => payload }) as Response
  }
  const fetchMock = vi.fn(impl)
  vi.stubGlobal('fetch', fetchMock)
  return fetchMock
}

export function makeCounties(fipsList: string[]): CountyListResponse {
  return {
    count: fipsList.length,
    counties: fipsList.map((fips) => ({
      county_fips: fips,
      state_fips: fips.slice(0, 2),
      state_abbr: 'AL',
      county_name: '0',
      state_name: '',
    })),
  }
}

/** Render the real route table in a memory router, wrapped in the provider. */
export function renderApp(initialEntries: string[] = ['/']) {
  const router = createMemoryRouter(routes, { initialEntries })
  return {
    router,
    ...render(
      <CountyDirectoryProvider>
        <RouterProvider router={router} />
      </CountyDirectoryProvider>,
    ),
  }
}
