import type { AccessProfile } from './types'

/**
 * Fixed presentational metadata for the four canonical access dimensions.
 *
 * Not an analytical constant -- no thresholds, weights, or scores. `label` is
 * the display name used app-wide (matching the `/explorer` payload's
 * `dimension_name`); `kind` records the semantic scale a dimension's score
 * lives on:
 *
 *  - `percentile` -- a 0-100 county percentile rank (primary care, dental,
 *    mental health).
 *  - `coverage`   -- a 0-100 geographic-coverage percentage (MUA/P), which is
 *    NOT a percentile and must never share a percentile scale or legend
 *    (governing specification sections 7.4 / 12.5).
 */
export interface DimensionMeta {
  readonly key: keyof AccessProfile
  readonly label: string
  readonly kind: 'percentile' | 'coverage'
}

export const DIMENSIONS: readonly DimensionMeta[] = [
  { key: 'primary_care', label: 'Primary Care Access', kind: 'percentile' },
  { key: 'dental', label: 'Dental Access', kind: 'percentile' },
  { key: 'mental_health', label: 'Mental Health Access', kind: 'percentile' },
  { key: 'mua_p', label: 'MUA/P Access', kind: 'coverage' },
]

/**
 * Canonical dimension order: the `access_profile` response key order, which
 * matches the governing specification section 8 table. Derived from
 * {@link DIMENSIONS} so there is a single source of truth.
 */
export const DIMENSION_ORDER: readonly (keyof AccessProfile)[] = DIMENSIONS.map(
  (dimension) => dimension.key,
)
