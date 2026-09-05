/**
 * Read-only client for the CHIA County API.
 *
 * This module only issues HTTP GET requests and parses JSON. It contains no
 * county list, no analytical logic, no score calculation, and no county/state
 * name enrichment -- the API is the single source of truth.
 */
import { API_BASE_URL } from './config'
import type {
  CountyListResponse,
  ExplorerResponse,
  StateDimensionScoresResponse,
} from './types'

/** A non-successful API response, or an inability to reach the API. */
export class ApiError extends Error {
  readonly status: number

  constructor(message: string, status: number) {
    super(message)
    this.name = 'ApiError'
    this.status = status
  }
}

/** HTTP 404 -- the requested resource does not exist (distinct from a failure). */
export class NotFoundError extends ApiError {
  constructor(message: string) {
    super(message, 404)
    this.name = 'NotFoundError'
  }
}

async function getJson<T>(path: string, signal?: AbortSignal): Promise<T> {
  let response: Response
  try {
    response = await fetch(`${API_BASE_URL}${path}`, {
      method: 'GET',
      headers: { Accept: 'application/json' },
      signal,
    })
  } catch {
    throw new ApiError('The CHIA API could not be reached.', 0)
  }

  if (response.status === 404) {
    throw new NotFoundError('The requested resource was not found.')
  }
  if (!response.ok) {
    throw new ApiError(
      `The CHIA API responded with status ${response.status}.`,
      response.status,
    )
  }

  return (await response.json()) as T
}

/** GET /api/v1/counties -- the canonical county universe (CE-B01). */
export function listCounties(signal?: AbortSignal): Promise<CountyListResponse> {
  return getJson<CountyListResponse>('/counties', signal)
}

/**
 * GET /api/v1/counties/{county_fips}/explorer -- the server-assembled Explorer
 * read model for one county and the v0.1 period (CE-B02).
 */
export function getCountyExplorer(
  countyFips: string,
  signal?: AbortSignal,
): Promise<ExplorerResponse> {
  return getJson<ExplorerResponse>(
    `/counties/${encodeURIComponent(countyFips)}/explorer`,
    signal,
  )
}

/**
 * GET /api/v1/states/{state_fips}/dimension-scores -- every county in one
 * state with its four persisted access-dimension scores for the v0.1 period
 * (CE-E09). Read-only; the frontend never recomputes a score.
 */
export function getStateDimensionScores(
  stateFips: string,
  signal?: AbortSignal,
): Promise<StateDimensionScoresResponse> {
  return getJson<StateDimensionScoresResponse>(
    `/states/${encodeURIComponent(stateFips)}/dimension-scores`,
    signal,
  )
}
