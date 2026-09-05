import type { ChangeEvent } from 'react'
import { useNavigate, useParams } from 'react-router-dom'

import { ErrorState } from './ErrorState'
import { Loading } from './Loading'
import { deriveCountiesForState } from '../lib/counties'
import { useCountyDirectory } from '../lib/countyDirectory'
import { stateFipsFromRoute } from '../lib/states'

/**
 * CE-C02 county selector, state-gated by CE-E13.
 *
 * A native `<select>` with an associated visible `<label>` (governing
 * specification, section 17), rendered in the app-level county-selection nav
 * on every route -- the step that follows choosing a state.
 *
 * The state in context is `stateFipsFromRoute(...)`: the `:stateFips` route
 * param, or the state a `:countyFips` belongs to. With no state selected (the
 * landing page) the control is disabled and shows "Select a state first".
 * Once a state is in context the options are exactly that state's counties,
 * taken from `deriveCountiesForState` -- the same single source the
 * state-scoped `CountySelectForState` and `StateCountyMap` use, so there is no
 * second county-filtering path. Choosing a county navigates to
 * `/counties/:countyFips`; the URL stays authoritative, so the control's
 * value is derived from the route parameter.
 */
export function CountySelector() {
  const navigate = useNavigate()
  const params = useParams<{ stateFips?: string; countyFips?: string }>()
  const directory = useCountyDirectory()

  if (directory.status === 'loading') {
    return <Loading label="Loading counties…" />
  }

  if (directory.status === 'error') {
    return (
      <ErrorState
        title="County list unavailable"
        message="The list of counties could not be loaded."
        onRetry={directory.retry}
      />
    )
  }

  if (directory.status === 'empty') {
    return (
      <p className="county-selector__empty" role="status">
        No counties are available.
      </p>
    )
  }

  function handleChange(event: ChangeEvent<HTMLSelectElement>) {
    const nextFips = event.target.value
    if (nextFips) {
      navigate(`/counties/${nextFips}`)
    }
  }

  const selectedStateFips = stateFipsFromRoute(directory.counties, params)

  if (!selectedStateFips) {
    return (
      <div className="county-selector">
        <label className="county-selector__label" htmlFor="county-select">
          County
        </label>
        <select
          id="county-select"
          className="county-selector__control"
          value=""
          onChange={handleChange}
          disabled
        >
          <option value="">Select a state first</option>
        </select>
      </div>
    )
  }

  const counties = deriveCountiesForState(directory.counties, selectedStateFips)
  const knownFips = new Set(counties.map((county) => county.county_fips))
  const selectedValue =
    params.countyFips && knownFips.has(params.countyFips) ? params.countyFips : ''

  return (
    <div className="county-selector">
      <label className="county-selector__label" htmlFor="county-select">
        County
      </label>
      <select
        id="county-select"
        className="county-selector__control"
        value={selectedValue}
        onChange={handleChange}
      >
        <option value="" disabled>
          Select a county
        </option>
        {counties.map((county) => (
          <option key={county.county_fips} value={county.county_fips}>
            {county.county_name} — {county.county_fips}
          </option>
        ))}
      </select>
    </div>
  )
}
