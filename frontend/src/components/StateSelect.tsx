import type { ChangeEvent } from 'react'
import { useNavigate } from 'react-router-dom'

import type { StateSummary } from '../lib/states'

export interface StateSelectProps {
  states: StateSummary[]
  /**
   * The state FIPS currently in context, derived from the route (see
   * `stateFipsFromRoute`). Reflected as the control's selected value so the
   * app-header selector shows the current state on `/states/:fips` and
   * `/counties/:fips`. Omitted / `''` on the landing page, where no state is
   * selected.
   */
  value?: string
}

/**
 * CE-E02 accessible state selector, relocated by CE-E13 into the app header
 * (to the right of the title), where it is the first step of the
 * select-a-state-then-a-county flow and is present on every route.
 *
 * It remains the required non-map alternative for state selection (governing
 * v0.2 UX specification, sections 9.2 and 11.5: "the map cannot be the only
 * navigation mechanism"), and it consumes the same `states` list as
 * `UsStateMap` -- see `lib/states.ts` -- so the two controls can never define
 * a different set of supported states.
 *
 * Selecting an option navigates to `/states/:stateFips`, identically to
 * selecting the state on the map. On the landing page (`value` unset) it
 * renders un-selected; on a state or county route it reflects the state in
 * context.
 */
export function StateSelect({ states, value = '' }: StateSelectProps) {
  const navigate = useNavigate()

  function handleChange(event: ChangeEvent<HTMLSelectElement>) {
    const stateFips = event.target.value
    if (stateFips && stateFips !== value) {
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
        value={value}
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
