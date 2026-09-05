import {
  COVERAGE_RAMP,
  MISSING_FILL,
  PERCENTILE_RAMP,
  fillForScore,
  formatScoreValue,
  rampColor,
  rampFor,
} from './choropleth'

describe('choropleth colour ramp (CE-E10, no d3 dependency)', () => {
  it('rampColor returns the endpoint colours at t=0 and t=1', () => {
    expect(rampColor(PERCENTILE_RAMP, 0)).toBe(PERCENTILE_RAMP[0])
    expect(rampColor(PERCENTILE_RAMP, 1)).toBe(PERCENTILE_RAMP[2])
    expect(rampColor(PERCENTILE_RAMP, 0.5)).toBe(PERCENTILE_RAMP[1])
  })

  it('rampColor clamps out-of-range t', () => {
    expect(rampColor(PERCENTILE_RAMP, -5)).toBe(PERCENTILE_RAMP[0])
    expect(rampColor(PERCENTILE_RAMP, 42)).toBe(PERCENTILE_RAMP[2])
  })

  it('rampColor interpolates monotonically between stops (a valid #rrggbb each time)', () => {
    for (const t of [0.1, 0.25, 0.4, 0.6, 0.75, 0.9]) {
      expect(rampColor(COVERAGE_RAMP, t)).toMatch(/^#[0-9a-f]{6}$/)
    }
  })

  it('percentile and coverage use different ramps', () => {
    expect(rampFor('percentile')).toBe(PERCENTILE_RAMP)
    expect(rampFor('coverage')).toBe(COVERAGE_RAMP)
    expect(rampColor(PERCENTILE_RAMP, 0.5)).not.toBe(rampColor(COVERAGE_RAMP, 0.5))
  })
})

describe('fillForScore', () => {
  it('a null or undefined score is the distinct MISSING_FILL, never a ramp colour', () => {
    expect(fillForScore(null, 'percentile')).toBe(MISSING_FILL)
    expect(fillForScore(undefined, 'coverage')).toBe(MISSING_FILL)
    expect(MISSING_FILL).not.toBe(PERCENTILE_RAMP[0])
    expect(MISSING_FILL).not.toBe(COVERAGE_RAMP[0])
  })

  it('a genuine 0 is a real value -> the ramp\'s lightest colour, not MISSING_FILL', () => {
    expect(fillForScore(0, 'percentile')).toBe(PERCENTILE_RAMP[0])
    expect(fillForScore(0, 'percentile')).not.toBe(MISSING_FILL)
  })

  it('100 maps to the ramp\'s darkest colour', () => {
    expect(fillForScore(100, 'coverage')).toBe(COVERAGE_RAMP[2])
  })

  it('uses the score on its fixed 0-100 domain (not re-scaled to any observed range)', () => {
    // 50 is always the mid stop regardless of the other counties' values.
    expect(fillForScore(50, 'percentile')).toBe(PERCENTILE_RAMP[1])
  })
})

describe('formatScoreValue', () => {
  it('rounds to a whole number and labels percentile vs coverage distinctly', () => {
    expect(formatScoreValue(87.6, 'percentile')).toBe('88 percentile')
    expect(formatScoreValue(1.8, 'coverage')).toBe('2% coverage')
    expect(formatScoreValue(0, 'percentile')).toBe('0 percentile')
  })
})
