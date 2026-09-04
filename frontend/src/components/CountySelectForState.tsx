import type { ChangeEvent } from 'react'
import { useNavigate } from 'react-router-dom'

import type { County } from '../lib/types'

export interface CountySelectForStateProps {
  counties: County[]
  stateName: string
}

/**
 * CE-E03 accessible, state-scoped county selector.
 *
 * The required non-map alternative for county selection within a state
 * (governing v0.2 UX specification, section 5.10: "County selection cannot
 * depend exclusively on clicking the geographic map... An equivalent
 * accessible county-selection mechanism must be available... The map and
 * non-map selection mechanism should represent the same underlying
 * choices"). Consumes the same `counties` list as `StateCountyMap` -- see
 * `lib/counties.ts`'s `deriveCountiesForState` -- so the two controls can
 * never define a different set of supported counties.
 *
 * This is a distinct, dedicated control from the existing global
 * `CountySelector` (which lists all 3,143 counties nationally, unchanged by
 * CE-E03); it is not a wrapper or rework of it. The label includes the state
 * name both for a distinct accessible name (avoiding ambiguity with the
 * global county selector's "County" label on the same page) and because
 * county names are meant to be presented with state context already
 * established (section 5.3).
 *
 * Selecting an option navigates to `/counties/:countyFips`, identically to
 * selecting the county on the map. This control always renders un-selected:
 * the state page has no persistent "current county" of its own, and
 * selecting a value immediately navigates away.
 */
export function CountySelectForState({ counties, stateName }: CountySelectForStateProps) {
  const navigate = useNavigate()

  function handleChange(event: ChangeEvent<HTMLSelectElement>) {
    const countyFips = event.target.value
    if (countyFips) {
      navigate(`/counties/${countyFips}`)
    }
  }

  return (
    <div className="county-select-for-state">
      <label className="county-select-for-state__label" htmlFor="county-select-for-state">
        County in {stateName}
      </label>
      <select
        id="county-select-for-state"
        className="county-select-for-state__control"
        value=""
        onChange={handleChange}
      >
        <option value="" disabled>
          Select a county
        </option>
        {counties.map((county) => (
          <option key={county.county_fips} value={county.county_fips}>
            {county.county_name}
          </option>
        ))}
      </select>
    </div>
  )
}
