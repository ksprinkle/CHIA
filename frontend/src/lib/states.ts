import type { County } from './types'

/**
 * One CHIA-supported state / state-equivalent, derived from the canonical
 * county universe (`GET /api/v1/counties`).
 *
 * This is the single authoritative supported-state dataset for CE-E02: both
 * `UsStateMap` and `StateSelect` derive their state list by calling
 * {@link deriveStates} on the same `CountyDirectory.counties` value from
 * `useCountyDirectory()`. Neither component maintains an independent list.
 */
export interface StateSummary {
  state_fips: string
  state_abbr: string
  state_name: string
}

/**
 * Derive the distinct, sorted list of states from the canonical county
 * universe. Ordered by `state_fips` ascending -- the same convention already
 * used for the county list (CE-B01), which for U.S. state FIPS codes also
 * coincides with alphabetical-by-name order.
 */
export function deriveStates(counties: County[]): StateSummary[] {
  const byFips = new Map<string, StateSummary>()

  for (const county of counties) {
    if (!byFips.has(county.state_fips)) {
      byFips.set(county.state_fips, {
        state_fips: county.state_fips,
        state_abbr: county.state_abbr,
        state_name: county.state_name,
      })
    }
  }

  return [...byFips.values()].sort((a, b) => a.state_fips.localeCompare(b.state_fips))
}

/**
 * The state FIPS implied by the current route, resolved against the same
 * canonical county universe: the `:stateFips` route param directly, or the
 * state the `:countyFips` county belongs to, or `null` on the landing page
 * (and for an unknown county FIPS).
 *
 * CE-E13: shared by the app-header `StateSelect` and the app-level
 * `CountySelector` so "which state is in context" is derived exactly once,
 * and the County selector's options are always scoped to that state via
 * {@link deriveCountiesForState} (no second county-filtering path).
 */
export function stateFipsFromRoute(
  counties: County[],
  params: { stateFips?: string; countyFips?: string },
): string | null {
  if (params.stateFips) return params.stateFips
  if (params.countyFips) {
    return (
      counties.find((county) => county.county_fips === params.countyFips)
        ?.state_fips ?? null
    )
  }
  return null
}
