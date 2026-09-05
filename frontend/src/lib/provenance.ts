import type { SourceRef } from './types'

const ISO_DATE = /\d{4}-\d{2}-\d{2}/

/**
 * The user-facing source-data vintage for a county profile, derived from the
 * CE-E12B provenance metadata in the `/explorer` payload -- never hard-coded.
 *
 * v0.1's four sources are one HRSA Data Warehouse snapshot, so their
 * `reference_period` strings ("HRSA Data Warehouse snapshot 2026-08-29") and
 * `accessed_at` dates agree. This returns the ISO date they share:
 *
 *  1. the ISO date embedded in a single shared `reference_period`, else
 *  2. a single shared `accessed_at` that is an ISO date, else
 *  3. `null` -- the sources disagree or carry no vintage, so the caller omits
 *     the row rather than showing a misleading value.
 *
 * This is presentation only. It does not touch `county_period.period` or
 * `methodology.methodology_version`, both of which remain `v0.1`.
 */
export function deriveDataVintage(sources: SourceRef[]): string | null {
  const referencePeriods = new Set(
    sources
      .map((source) => source.reference_period)
      .filter((value): value is string => Boolean(value)),
  )
  if (referencePeriods.size === 1) {
    const match = [...referencePeriods][0].match(ISO_DATE)
    if (match) return match[0]
  }

  const accessedDates = new Set(
    sources
      .map((source) => source.accessed_at)
      .filter((value): value is string => Boolean(value)),
  )
  if (accessedDates.size === 1) {
    const only = [...accessedDates][0]
    if (ISO_DATE.test(only)) return only
  }

  return null
}
