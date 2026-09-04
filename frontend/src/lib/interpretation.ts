import { DIMENSION_ORDER } from './dimensions'
import type { ExplorerResponse } from './types'

export interface DimensionScoreInfo {
  key: (typeof DIMENSION_ORDER)[number]
  dimensionName: string
  score: number
  normalized: boolean
}

export interface Interpretation {
  totalCount: number
  availableCount: number
  /** True when fewer than two dimensions have an available score. */
  insufficientData: boolean
  /** All dimensions tied for the highest available score; empty when insufficientData. */
  highest: DimensionScoreInfo[]
  /** All dimensions tied for the lowest available score; empty when insufficientData. */
  lowest: DimensionScoreInfo[]
  /** Highest-minus-lowest gap, using the same whole-number rounding as the
   *  visible score badges; null when insufficientData. */
  scoreGap: number | null
  compositeAvailable: boolean
  /** Persisted `experimental_composite.missing_dimensions`, verbatim. */
  missingDimensions: string[]
}

/**
 * Deterministic, application-generated interpretation (governing
 * specification section 14): highest/lowest scoring dimension(s), the gap
 * between them, data completeness, and composite availability. A pure
 * function of the already-fetched Explorer payload -- no new field, no
 * network request, no recalculation of any persisted score or composite
 * value, and no invented threshold or band.
 */
export function deriveInterpretation(explorer: ExplorerResponse): Interpretation {
  const { access_profile: accessProfile, experimental_composite: composite } = explorer

  const scored: DimensionScoreInfo[] = []
  for (const key of DIMENSION_ORDER) {
    const dimension = accessProfile[key]
    if (dimension.available && dimension.score !== null) {
      scored.push({
        key,
        dimensionName: dimension.dimension_name,
        score: dimension.score,
        normalized: dimension.normalized,
      })
    }
  }

  const totalCount = DIMENSION_ORDER.length
  const availableCount = scored.length
  const insufficientData = availableCount < 2

  let highest: DimensionScoreInfo[] = []
  let lowest: DimensionScoreInfo[] = []
  let scoreGap: number | null = null

  if (!insufficientData) {
    const maxScore = Math.max(...scored.map((entry) => entry.score))
    const minScore = Math.min(...scored.map((entry) => entry.score))
    highest = scored.filter((entry) => entry.score === maxScore)
    lowest = scored.filter((entry) => entry.score === minScore)
    // Rounded first, like the visible score badges, so the stated gap always
    // matches the two numbers the reader can see on the page.
    scoreGap = Math.round(maxScore) - Math.round(minScore)
  }

  return {
    totalCount,
    availableCount,
    insufficientData,
    highest,
    lowest,
    scoreGap,
    compositeAvailable: composite.composite_value !== null,
    missingDimensions: composite.missing_dimensions,
  }
}
