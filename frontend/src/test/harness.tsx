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

/**
 * These previously returned a plain object (not a real `Promise`). The app's
 * own `await fetch(...)` tolerates that (awaiting a non-thenable resolves
 * immediately), but CE-E02's `react-simple-maps` calls `fetch(url).then(...)`
 * directly, which throws "fetch(...).then is not a function" against a bare
 * object. Wrapping in a genuine `Promise.resolve` fixes that without
 * changing behaviour for any existing (non-`.then`-chaining) caller.
 */
function okJson(body: unknown): Promise<Response> {
  return Promise.resolve({ ok: true, status: 200, json: async () => body } as Response)
}

function errStatus(status: number): Promise<Response> {
  return Promise.resolve({
    ok: false,
    status,
    json: async () => ({ detail: `status ${status}` }),
  } as Response)
}

/**
 * CE-E02: a minimal, valid TopoJSON fixture standing in for the real
 * committed `frontend/public/geo/us-states.topojson` asset. Two features
 * (`01` Alabama, `06` California) is enough to exercise `UsStateMap` /
 * `StateSelect` interaction without depending on the real ~1.9 MB asset in
 * unit tests. Every stub below routes a `/geo/` request here so that
 * `HomePage` rendering the map never hits an unstubbed-fetch failure.
 */
export const STUB_US_STATES_TOPOJSON = {
  type: 'Topology',
  arcs: [
    [
      [0, 0],
      [1, 0],
      [1, 1],
      [0, 1],
      [0, 0],
    ],
    [
      [2, 0],
      [3, 0],
      [3, 1],
      [2, 1],
      [2, 0],
    ],
  ],
  objects: {
    states: {
      type: 'GeometryCollection',
      geometries: [
        { type: 'Polygon', id: '01', properties: { name: 'Alabama' }, arcs: [[0]] },
        { type: 'Polygon', id: '06', properties: { name: 'California' }, arcs: [[1]] },
      ],
    },
  },
}

function isGeographyRequest(url: string): boolean {
  return url.includes('/geo/')
}

/**
 * Stub the global `fetch` for `GET /api/v1/counties` (Vitest, no MSW).
 *
 * URL-aware: an Explorer request (`/counties/{fips}/explorer`) resolves to 404
 * so a county-route test that does not explicitly stub the Explorer degrades to
 * a "not found" profile rather than parsing a county-list payload. A
 * geography request (`/geo/...`, CE-E02) resolves to {@link
 * STUB_US_STATES_TOPOJSON}. Tests that need a real Explorer payload use
 * {@link stubApi}.
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
      const url = String(args[0])
      if (isGeographyRequest(url)) return okJson(STUB_US_STATES_TOPOJSON)
      if (url.includes('/explorer')) return errStatus(404)
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
    if (isGeographyRequest(url)) return okJson(STUB_US_STATES_TOPOJSON)
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

/**
 * CE-E02: counties spanning two distinct states (matching
 * {@link STUB_US_STATES_TOPOJSON}'s `01`/`06` features), for tests that
 * exercise state derivation, the map, and the accessible state selector.
 */
export function makeMultiStateCounties(): CountyListResponse {
  const counties: CountyListResponse['counties'] = [
    {
      county_fips: '01001',
      state_fips: '01',
      state_abbr: 'AL',
      county_name: 'Autauga County',
      state_name: 'Alabama',
    },
    {
      county_fips: '01003',
      state_fips: '01',
      state_abbr: 'AL',
      county_name: 'Baldwin County',
      state_name: 'Alabama',
    },
    {
      county_fips: '06075',
      state_fips: '06',
      state_abbr: 'CA',
      county_name: 'San Francisco County',
      state_name: 'California',
    },
  ]
  return { count: counties.length, counties }
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
  sourceId: number,
  evidenceNames: string[],
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
    source_id: sourceId,
    primary_measure: {
      variable_id: variableId,
      display_name: `${name} primary measure`,
      unit: 'percent',
      raw_value: 42.5,
      normalized_value: normalized ? score : null,
      normalization_method: normalized ? 'county_percentile_rank_average' : null,
      quality_flag: 'source_validated',
    },
    supporting_evidence: evidenceNames.map((evidenceName, index) => ({
      variable_id: `${variableId}_SUP_${index + 1}`,
      display_name: evidenceName,
      unit: index === evidenceNames.length - 1 ? 'count' : 'score',
      direction: 'higher_burden',
      raw_value: 2.5 + index,
      quality_flag: 'source_validated',
    })),
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
      1,
      [
        'Primary Care HPSA Area-Weighted Score',
        'Primary Care HPSA Maximum Score',
        'Primary Care HPSA Designation Count',
      ],
    ),
    dental: makeDimension(
      'DENTAL',
      'Dental Access',
      'DENTAL_HPSA_GEOGRAPHIC_COVERAGE',
      true,
      29,
      2,
      [
        'Dental HPSA Area-Weighted Score',
        'Dental HPSA Maximum Score',
        'Dental HPSA Designation Count',
      ],
    ),
    mental_health: makeDimension(
      'MENTAL_HEALTH',
      'Mental Health Access',
      'MH_HPSA_GEOGRAPHIC_COVERAGE',
      true,
      23,
      3,
      [
        'Mental Health HPSA Area-Weighted Score',
        'Mental Health HPSA Maximum Score',
        'Mental Health HPSA Designation Count',
      ],
    ),
    mua_p: makeDimension(
      'MUA_P',
      'MUA/P Access',
      'MUAP_GEOGRAPHIC_COVERAGE',
      false,
      99,
      4,
      [
        'MUA/P Mean Score',
        'MUA/P Maximum Score',
        'MUA/P Feature Count',
        'MUA Feature Count',
        'MUP Feature Count',
        'MUA/P Unique Source Count',
      ],
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
          source_name: 'Primary Care HPSA',
          publisher: 'HRSA',
          dataset_name: 'Primary Care HPSA Spatial Coverage',
          reference_period: 'v0.1 source period',
          url: null,
          accessed_at: null,
        },
        {
          source_id: 2,
          source_name: 'Dental HPSA',
          publisher: 'HRSA',
          dataset_name: 'Dental HPSA Spatial Coverage',
          reference_period: 'v0.1 source period',
          url: null,
          accessed_at: null,
        },
        {
          source_id: 3,
          source_name: 'Mental Health HPSA',
          publisher: 'HRSA',
          dataset_name: 'Mental Health HPSA Spatial Coverage',
          reference_period: 'v0.1 source period',
          url: null,
          accessed_at: null,
        },
        {
          source_id: 4,
          source_name: 'MUA/P',
          publisher: 'HRSA',
          dataset_name: 'MUA/P Spatial Coverage',
          reference_period: 'v0.1 source period',
          url: null,
          accessed_at: null,
        },
      ],
    },
    methodology: {
      methodology_version: 'v0.1',
      name: 'CHIA Access Profile v0.1',
      description:
        'Four-domain county-level healthcare access profile using validated geographic coverage measures, county percentile-rank normalization, and an experimental equal-weight composite burden measure.',
      status: 'prototype',
      created_at: '2026-09-02 00:09:27',
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
