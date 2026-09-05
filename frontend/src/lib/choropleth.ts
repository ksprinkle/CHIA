/**
 * CE-E10 state county choropleth colour ramps and value formatting.
 *
 * Hand-rolled linear hex interpolation -- deliberately NO `d3-scale`,
 * `d3-interpolate`, or `d3-color` import (they are transitive-only
 * dependencies of `react-simple-maps`; the CE-E03 `d3-geo` precedent).
 *
 * The two ramps are visually distinct so a percentile-normalized dimension is
 * never confused with MUA/P geographic coverage (governing specification
 * sections 7.4 / 12.5). Scores are used on their fixed 0-100 domain
 * (percentile rank, or coverage percentage) and are never re-scaled to the
 * state's own min/max, which would distort cross-state comparison and imply an
 * unsupported analytical classification (section 5 / 7.3).
 */
import type { DimensionMeta } from './dimensions'

/** Flat neutral fill for a county with no available score. Off both ramps. */
export const MISSING_FILL = '#c7ccd1'

type Ramp = readonly [string, string, string]

/** Percentile dimensions (primary care, dental, mental health): blue. */
export const PERCENTILE_RAMP: Ramp = ['#eef3f8', '#8fbcda', '#2f6ea8']

/** MUA/P geographic coverage: a distinct teal ramp. */
export const COVERAGE_RAMP: Ramp = ['#eef6f2', '#88ccb2', '#2f8f6b']

export function rampFor(kind: DimensionMeta['kind']): Ramp {
  return kind === 'coverage' ? COVERAGE_RAMP : PERCENTILE_RAMP
}

function hexToRgb(hex: string): [number, number, number] {
  const value = hex.replace('#', '')
  return [
    parseInt(value.slice(0, 2), 16),
    parseInt(value.slice(2, 4), 16),
    parseInt(value.slice(4, 6), 16),
  ]
}

function toHex(channel: number): string {
  return Math.round(channel).toString(16).padStart(2, '0')
}

function mix(from: string, to: string, t: number): string {
  const [r1, g1, b1] = hexToRgb(from)
  const [r2, g2, b2] = hexToRgb(to)
  return `#${toHex(r1 + (r2 - r1) * t)}${toHex(g1 + (g2 - g1) * t)}${toHex(
    b1 + (b2 - b1) * t,
  )}`
}

/** Colour for a position `t` (0..1) along a three-stop ramp. */
export function rampColor(ramp: Ramp, t: number): string {
  const clamped = Math.min(1, Math.max(0, t))
  const [low, mid, high] = ramp
  return clamped <= 0.5
    ? mix(low, mid, clamped / 0.5)
    : mix(mid, high, (clamped - 0.5) / 0.5)
}

/**
 * Fill for one county feature. A `null`/`undefined` score -- an unavailable
 * dimension -- is {@link MISSING_FILL}, never a ramp colour and never treated
 * as zero (governing specification sections 7.7 / 9.5 / 12.13). A genuine `0`
 * is a real observed value and gets the ramp's lightest colour.
 */
export function fillForScore(
  score: number | null | undefined,
  kind: DimensionMeta['kind'],
): string {
  if (score === null || score === undefined) return MISSING_FILL
  return rampColor(rampFor(kind), score / 100)
}

/**
 * Display string for a county's score on the active dimension, matching the
 * rounded whole-number treatment used in the County Profile snapshot
 * (`formatScore` + unit). Missing is the caller's responsibility.
 */
export function formatScoreValue(
  score: number,
  kind: DimensionMeta['kind'],
): string {
  const rounded = String(Math.round(score))
  return kind === 'coverage' ? `${rounded}% coverage` : `${rounded} percentile`
}
