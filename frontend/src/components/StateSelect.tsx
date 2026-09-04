import type { ChangeEvent } from 'react'
import { useNavigate } from 'react-router-dom'

import type { StateSummary } from '../lib/states'

export interface StateSelectProps {
  states: StateSummary[]
}

/**
 * CE-E02 accessible state selector.
 *
 * The required non-map alternative for state selection (governing v0.2 UX
 * specification, sections 9.2 and 11.5: "the map cannot be the only
 * navigation mechanism"). Consumes the same `states` list as `UsStateMap` --
 * see `lib/states.ts` -- so the two controls can never define a different
 * set of supported states.
 *
 * Selecting an option navigates to `/states/:stateFips`, identically to
 * selecting the state on the map. This control always renders un-selected:
 * the landing page has no persistent "current state" of its own, and
 * selecting a value immediately navigates away.
 */
export function StateSelect({ states }: StateSelectProps) {
  const navigate = useNavigate()

  function handleChange(event: ChangeEvent<HTMLSelectElement>) {
    const stateFips = event.target.value
    if (stateFips) {
      navigate(`/states/${stateFips}`)
    }
  }

  return (
    <div className="state-select">
      <label className="state-select__label" htmlFor="state-select">
        State
      </label>
      <select
        id="state-select"
        className="state-select__control"
        value=""
        onChange={handleChange}
      >
        <option value="" disabled>
          Select a state
        </option>
        {states.map((state) => (
          <option key={state.state_fips} value={state.state_fips}>
            {state.state_name}
          </option>
        ))}
      </select>
    </div>
  )
}
