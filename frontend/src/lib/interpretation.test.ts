import { deriveInterpretation } from './interpretation'
import { makeExplorer } from '../test/harness'

describe('deriveInterpretation (CE-C05, pure)', () => {
  it('identifies a single highest and lowest dimension with the score gap', () => {
    // Default fixture: primary_care 88, dental 29, mental_health 23, mua_p 99.
    const explorer = makeExplorer('01001')
    const result = deriveInterpretation(explorer)

    expect(result.totalCount).toBe(4)
    expect(result.availableCount).toBe(4)
    expect(result.insufficientData).toBe(false)
    expect(result.highest.map((d) => d.key)).toEqual(['mua_p'])
    expect(result.lowest.map((d) => d.key)).toEqual(['mental_health'])
    expect(result.scoreGap).toBe(99 - 23)
  })

  it('names all dimensions tied for the highest score', () => {
    const explorer = makeExplorer('01001', {
      dimensions: {
        primary_care: { score: 80 },
        dental: { score: 80 },
        mental_health: { score: 20 },
        mua_p: { score: 50 },
      },
    })
    const result = deriveInterpretation(explorer)

    expect(result.highest.map((d) => d.key).sort()).toEqual([
      'dental',
      'primary_care',
    ])
    expect(result.lowest.map((d) => d.key)).toEqual(['mental_health'])
    expect(result.scoreGap).toBe(80 - 20)
  })

  it('names all dimensions tied for the lowest score', () => {
    const explorer = makeExplorer('01001', {
      dimensions: {
        primary_care: { score: 90 },
        dental: { score: 10 },
        mental_health: { score: 10 },
        mua_p: { score: 50 },
      },
    })
    const result = deriveInterpretation(explorer)

    expect(result.lowest.map((d) => d.key).sort()).toEqual([
      'dental',
      'mental_health',
    ])
    expect(result.highest.map((d) => d.key)).toEqual(['primary_care'])
  })

  it('names all four dimensions as tied when every score is equal', () => {
    const explorer = makeExplorer('01001', {
      dimensions: {
        primary_care: { score: 50 },
        dental: { score: 50 },
        mental_health: { score: 50 },
        mua_p: { score: 50 },
      },
    })
    const result = deriveInterpretation(explorer)

    expect(result.highest.map((d) => d.key).sort()).toEqual([
      'dental',
      'mental_health',
      'mua_p',
      'primary_care',
    ])
    expect(result.lowest.map((d) => d.key).sort()).toEqual([
      'dental',
      'mental_health',
      'mua_p',
      'primary_care',
    ])
    expect(result.scoreGap).toBe(0)
  })

  it('includes MUA/P in the comparison and flags it as non-normalized', () => {
    const explorer = makeExplorer('01001', {
      dimensions: {
        primary_care: { score: 10 },
        dental: { score: 20 },
        mental_health: { score: 30 },
        mua_p: { score: 95, normalized: false },
      },
    })
    const result = deriveInterpretation(explorer)

    expect(result.highest).toHaveLength(1)
    expect(result.highest[0].key).toBe('mua_p')
    expect(result.highest[0].normalized).toBe(false)
  })

  it('reports insufficient data with exactly one available score', () => {
    const explorer = makeExplorer('01001', {
      dimensions: {
        primary_care: { available: true, score: 50 },
        dental: { available: false, score: null },
        mental_health: { available: false, score: null },
        mua_p: { available: false, score: null },
      },
    })
    const result = deriveInterpretation(explorer)

    expect(result.availableCount).toBe(1)
    expect(result.insufficientData).toBe(true)
    expect(result.highest).toEqual([])
    expect(result.lowest).toEqual([])
    expect(result.scoreGap).toBeNull()
  })

  it('reports insufficient data with zero available scores', () => {
    const explorer = makeExplorer('01001', {
      dimensions: {
        primary_care: { available: false, score: null },
        dental: { available: false, score: null },
        mental_health: { available: false, score: null },
        mua_p: { available: false, score: null },
      },
    })
    const result = deriveInterpretation(explorer)

    expect(result.availableCount).toBe(0)
    expect(result.insufficientData).toBe(true)
    expect(result.highest).toEqual([])
    expect(result.lowest).toEqual([])
    expect(result.scoreGap).toBeNull()
  })

  it('reports composite availability from the API composite_value', () => {
    const explorer = makeExplorer('01001')
    const result = deriveInterpretation(explorer)

    expect(result.compositeAvailable).toBe(true)
    expect(result.missingDimensions).toEqual([])
  })

  it('reports composite unavailability with the API missing_dimensions verbatim', () => {
    const payload = makeExplorer('01001')
    const explorer = {
      ...payload,
      experimental_composite: {
        ...payload.experimental_composite,
        composite_value: null,
        missing_dimensions: ['DENTAL'],
      },
    }
    const result = deriveInterpretation(explorer)

    expect(result.compositeAvailable).toBe(false)
    expect(result.missingDimensions).toEqual(['DENTAL'])
  })

  it('never mutates or recalculates the persisted score values', () => {
    const explorer = makeExplorer('01001', {
      dimensions: { primary_care: { score: 12.34 } },
    })
    deriveInterpretation(explorer)

    expect(explorer.access_profile.primary_care.score).toBe(12.34)
  })
})
