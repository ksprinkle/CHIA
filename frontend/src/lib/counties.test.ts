import { describe, expect, it } from 'vitest'

import { deriveCountiesForState } from './counties'
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

describe('CE-E03 deriveCountiesForState', () => {
  it('returns only counties belonging to the requested state', () => {
    const counties = [
      county({ county_fips: '01001', state_fips: '01', county_name: 'Autauga County' }),
      county({ county_fips: '01003', state_fips: '01', county_name: 'Baldwin County' }),
      county({ county_fips: '06075', state_fips: '06', county_name: 'San Francisco County' }),
    ]

    const result = deriveCountiesForState(counties, '01')

    expect(result.map((c) => c.county_fips)).toEqual(['01001', '01003'])
  })

  it('does not accidentally include counties from another state', () => {
    const counties = [
      county({ county_fips: '01001', state_fips: '01' }),
      county({ county_fips: '06075', state_fips: '06' }),
    ]

    const result = deriveCountiesForState(counties, '01')

    expect(result.some((c) => c.state_fips !== '01')).toBe(false)
    expect(result.find((c) => c.county_fips === '06075')).toBeUndefined()
  })

  it('uses stable county_fips/state_fips identifiers, not names', () => {
    const counties = [
      county({ county_fips: '18069', state_fips: '18', county_name: 'Huntington County' }),
      // Same county_name in a different state -- must not be conflated.
      county({ county_fips: '99999', state_fips: '99', county_name: 'Huntington County' }),
    ]

    const result = deriveCountiesForState(counties, '18')

    expect(result).toEqual([
      county({ county_fips: '18069', state_fips: '18', county_name: 'Huntington County' }),
    ])
  })

  it('orders counties by county_fips ascending', () => {
    const counties = [
      county({ county_fips: '01103', state_fips: '01' }),
      county({ county_fips: '01001', state_fips: '01' }),
      county({ county_fips: '01055', state_fips: '01' }),
    ]

    const result = deriveCountiesForState(counties, '01')

    expect(result.map((c) => c.county_fips)).toEqual(['01001', '01055', '01103'])
  })

  it('returns an empty list for a state with no matching counties', () => {
    const counties = [county({ county_fips: '01001', state_fips: '01' })]

    expect(deriveCountiesForState(counties, '56')).toEqual([])
  })
})
