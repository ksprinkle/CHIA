import { describe, expect, it } from 'vitest'

import { deriveStates } from './states'
import type { County } from './types'

function county(overrides: Partial<County>): County {
  return {
    county_fips: '00000',
    state_fips: '00',
    state_abbr: 'ZZ',
    county_name: 'Test County',
    state_name: 'Test State',
    ...overrides,
  }
}

describe('CE-E02 deriveStates', () => {
  it('derives one entry per distinct state_fips', () => {
    const counties = [
      county({ county_fips: '01001', state_fips: '01', state_abbr: 'AL', state_name: 'Alabama' }),
      county({ county_fips: '01003', state_fips: '01', state_abbr: 'AL', state_name: 'Alabama' }),
      county({ county_fips: '06075', state_fips: '06', state_abbr: 'CA', state_name: 'California' }),
    ]

    const states = deriveStates(counties)

    expect(states).toHaveLength(2)
    expect(states.map((s) => s.state_fips)).toEqual(['01', '06'])
  })

  it('orders states by state_fips ascending', () => {
    const counties = [
      county({ county_fips: '56001', state_fips: '56', state_name: 'Wyoming' }),
      county({ county_fips: '02013', state_fips: '02', state_name: 'Alaska' }),
      county({ county_fips: '48001', state_fips: '48', state_name: 'Texas' }),
    ]

    const states = deriveStates(counties)

    expect(states.map((s) => s.state_fips)).toEqual(['02', '48', '56'])
  })

  it('preserves state_abbr and state_name verbatim (no enrichment)', () => {
    const counties = [
      county({
        county_fips: '11001',
        state_fips: '11',
        state_abbr: 'DC',
        state_name: 'District of Columbia',
      }),
    ]

    const states = deriveStates(counties)

    expect(states).toEqual([
      { state_fips: '11', state_abbr: 'DC', state_name: 'District of Columbia' },
    ])
  })

  it('returns an empty list for an empty county universe', () => {
    expect(deriveStates([])).toEqual([])
  })
})
