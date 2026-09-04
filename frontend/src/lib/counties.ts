import type { County } from './types'

/**
 * Derive the counties belonging to one state from the canonical county
 * universe (`GET /api/v1/counties`).
 *
 * This is the single authoritative per-state county dataset for CE-E03:
 * both `StateCountyMap` and `CountySelectForState` derive their county list
 * by calling this on the same `CountyDirectory.counties` value from
 * `useCountyDirectory()`. Neither component maintains an independent list.
 * Ordered by `county_fips` ascending, matching the existing app-wide
 * convention (CE-B01 county list, CE-E02 state list).
 */
export function deriveCountiesForState(counties: County[], stateFips: string): County[] {
  return counties
    .filter((county) => county.state_fips === stateFips)
    .sort((a, b) => a.county_fips.localeCompare(b.county_fips))
}
