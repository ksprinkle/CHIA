import type { ChangeEvent } from 'react'
import { useNavigate, useParams } from 'react-router-dom'

import { ErrorState } from './ErrorState'
import { Loading } from './Loading'
import { useCountyDirectory } from '../lib/countyDirectory'

/**
 * CE-C02 county selector.
 *
 * A native `<select>` with an associated visible `<label>` (governing
 * specification, section 17). Options are built only from `GET /api/v1/counties`
 * values: `county_name` verbatim plus `county_fips` (`0 — 01001`). Choosing a
 * county navigates to `/counties/:countyFips`; the URL is authoritative, so the
 * control's value is derived from the route parameter.
 */
export function CountySelector() {
  const navigate = useNavigate()
  const { countyFips } = useParams<{ countyFips: string }>()
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

  const knownFips = new Set(directory.counties.map((county) => county.county_fips))
  const selectedValue =
    countyFips && knownFips.has(countyFips) ? countyFips : ''

  function handleChange(event: ChangeEvent<HTMLSelectElement>) {
    const nextFips = event.target.value
    if (nextFips) {
      navigate(`/counties/${nextFips}`)
    }
  }

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
        {directory.counties.map((county) => (
          <option key={county.county_fips} value={county.county_fips}>
            {county.county_name} — {county.county_fips}
          </option>
        ))}
      </select>
    </div>
  )
}
