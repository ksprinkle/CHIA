import { render } from '@testing-library/react'
import { RouterProvider, createMemoryRouter } from 'react-router-dom'

import { CountyDirectoryProvider } from '../lib/countyDirectory'
import { routes } from '../router'
import type {
  AccessProfile,
  CountyListResponse,
  DimensionProfile,
  ExplorerResponse,
} from '../lib/types'

type FetchImpl = (...args: unknown[]) => Promise<Response> | Response

function okJson(body: unknown): Response {
  return { ok: true, status: 200, json: async () => body } as Response
}

function errStatus(status: number): Response {
  return {
    ok: false,
    status,
    json: async () => ({ detail: `status ${status}` }),
  } as Response
}

/**
 * Stub the global `fetch` for `GET /api/v1/counties` (Vitest, no MSW).
 *
 * URL-aware: an Explorer request (`/counties/{fips}/explorer`) resolves to 404
 * so a county-route test that does not explicitly stub the Explorer degrades to
 * a "not found" profile rather than parsing a county-list payload. Tests that
 * need a real Explorer payload use {@link stubApi}.
 */
export function stubCountiesFetch(payload: CountyListResponse | Error | FetchImpl) {
  let impl: FetchImpl
  if (typeof payload === 'function') {
    impl = payload
  } else if (payload instanceof Error) {
    impl = () => {
      throw payload
    }
  } else {
    impl = (...args: unknown[]) => {
      if (String(args[0]).includes('/explorer')) return errStatus(404)
      return okJson(payload)
    }
  }
  const fetchMock = vi.fn(impl)
  vi.stubGlobal('fetch', fetchMock)
  return fetchMock
}

interface ApiStub {
  counties?: CountyListResponse | Error
  /** Return an ExplorerResponse, an Error to throw, or an HTTP status number. */
  explorer?: (fips: string) => ExplorerResponse | Error | number
}

/** Stub the global `fetch` for both CHIA API endpoints, routed by URL. */
export function stubApi(stub: ApiStub = {}) {
  const impl: FetchImpl = (...args: unknown[]) => {
    const url = String(args[0])
    const explorerFips = url.match(/\/counties\/(\d{5})\/explorer/)?.[1]
    if (explorerFips !== undefined) {
      const result = stub.explorer ? stub.explorer(explorerFips) : 404
      if (typeof result === 'number') return errStatus(result)
      if (result instanceof Error) throw result
      return okJson(result)
    }
    if (url.includes('/counties')) {
      const counties = stub.counties ?? makeCounties([])
      if (counties instanceof Error) throw counties
      return okJson(counties)
    }
    throw new Error(`stubApi: unstubbed fetch ${url}`)
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

interface DimensionOverride extends Partial<Omit<DimensionProfile, 'primary_measure'>> {
  primary_measure?: Partial<DimensionProfile['primary_measure']>
}

interface ExplorerOverrides {
  county?: Partial<ExplorerResponse['county']>
  period?: Partial<ExplorerResponse['period']>
  dimensions?: Partial<Record<keyof AccessProfile, DimensionOverride>>
}

function makeDimension(
  id: string,
  name: string,
  variableId: string,
  normalized: boolean,
  score: number | null,
): DimensionProfile {
  return {
    dimension_id: id,
    dimension_name: name,
    description: `${name} description.`,
    primary_variable_id: variableId,
    calculation_method: `${name} calculation method.`,
    direction: 'higher_burden',
    normalized,
    available: score !== null,
    score,
    score_status: score !== null ? 'calculated' : null,
    source_id: null,
    primary_measure: {
      variable_id: variableId,
      display_name: `${name} primary measure`,
      unit: 'percent',
      raw_value: 42.5,
      normalized_value: normalized ? score : null,
      normalization_method: normalized ? 'county_percentile_rank_average' : null,
      quality_flag: 'source_validated',
    },
    supporting_evidence: [
      {
        variable_id: `${variableId}_SUPPORT`,
        display_name: `${name} supporting evidence detail`,
        unit: 'score',
        direction: 'higher_burden',
        raw_value: 7.77,
        quality_flag: 'source_validated',
      },
    ],
  }
}

/**
 * A full, real-shaped ExplorerResponse for tests. Includes populated C04
 * payload sections (supporting evidence, composite, provenance, methodology)
 * with distinctive values so leakage assertions are meaningful.
 */
export function makeExplorer(
  countyFips: string,
  overrides: ExplorerOverrides = {},
): ExplorerResponse {
  const accessProfile: AccessProfile = {
    primary_care: makeDimension(
      'PRIMARY_CARE',
      'Primary Care Access',
      'PC_HPSA_GEOGRAPHIC_COVERAGE',
      true,
      88,
    ),
    dental: makeDimension(
      'DENTAL',
      'Dental Access',
      'DENTAL_HPSA_GEOGRAPHIC_COVERAGE',
      true,
      29,
    ),
    mental_health: makeDimension(
      'MENTAL_HEALTH',
      'Mental Health Access',
      'MH_HPSA_GEOGRAPHIC_COVERAGE',
      true,
      23,
    ),
    mua_p: makeDimension(
      'MUA_P',
      'MUA/P Access',
      'MUAP_GEOGRAPHIC_COVERAGE',
      false,
      99,
    ),
  }

  for (const [key, patch] of Object.entries(overrides.dimensions ?? {})) {
    const dimensionKey = key as keyof AccessProfile
    const current = accessProfile[dimensionKey]
    accessProfile[dimensionKey] = {
      ...current,
      ...patch,
      primary_measure: {
        ...current.primary_measure,
        ...(patch.primary_measure ?? {}),
      },
    }
  }

  return {
    county: {
      county_fips: countyFips,
      county_name: `County ${countyFips}`,
      state_abbr: 'AL',
      state_name: 'Alabama',
      ...overrides.county,
    },
    period: {
      value: 'v0.1',
      completeness_status: 'complete',
      ...overrides.period,
    },
    access_profile: accessProfile,
    experimental_composite: {
      label: 'Experimental / Provisional',
      composite_value: 59.75,
      status: 'experimental_provisional',
      missing_dimensions: [],
    },
    provenance: {
      sources: [
        {
          source_id: 1,
          source_name: 'HRSA HPSA provenance source',
          publisher: 'HRSA',
          dataset_name: 'HPSA Spatial Coverage',
          reference_period: 'v0.1 source period',
          url: null,
          accessed_at: null,
        },
      ],
    },
    methodology: {
      methodology_version: 'v0.1',
      name: 'CHIA Access Profile v0.1 methodology',
      description: 'Methodology description block.',
      status: 'prototype',
      created_at: null,
      normalization_method: 'county_percentile_rank_average',
    },
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
