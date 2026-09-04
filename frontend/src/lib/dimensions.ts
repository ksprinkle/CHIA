import type { AccessProfile } from './types'

/**
 * Canonical dimension order: the `access_profile` response key order, which
 * matches the governing specification section 8 table. Not an analytical
 * constant -- no thresholds, weights, or scores are defined here.
 */
export const DIMENSION_ORDER: readonly (keyof AccessProfile)[] = [
  'primary_care',
  'dental',
  'mental_health',
  'mua_p',
]
