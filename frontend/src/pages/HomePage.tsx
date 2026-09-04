import { ErrorState } from '../components/ErrorState'
import { Loading } from '../components/Loading'
import { StateSelect } from '../components/StateSelect'
import { UsStateMap } from '../components/UsStateMap'
import { useCountyDirectory } from '../lib/countyDirectory'
import { deriveStates } from '../lib/states'

/**
 * CE-E02 U.S. map landing page (governing v0.2 UX specification, section 14,
 * "CE-E02 -- U.S. Map Landing Experience").
 *
 * Replaces the CE-C01 text-first landing state with the U.S. map as the
 * primary navigation surface: `UsStateMap` and the accessible `StateSelect`
 * both derive their state list from `deriveStates(directory.counties)`
 * (`lib/states.ts`) -- there is no second, independently defined state list.
 * The existing global county selector (`CountySelector`, rendered in
 * `Layout` on every route) is unchanged and remains the CE-E02-required
 * alternative navigation path.
 */
export function HomePage() {
  const directory = useCountyDirectory()
  const states = directory.status === 'ready' ? deriveStates(directory.counties) : []

  return (
    <section className="home" aria-labelledby="home-heading">
      <h1 id="home-heading">CHIA County Explorer</h1>
      <p>
        Explore county-level healthcare access profiles from the Community Health
        Intelligence Atlas for the v0.1 methodology period.
      </p>
      <p className="home__hint">No county is currently selected.</p>

      {directory.status === 'loading' ? <Loading label="Loading states…" /> : null}

      {directory.status === 'error' ? (
        <ErrorState
          message="The state list could not be loaded."
          onRetry={directory.retry}
        />
      ) : null}

      {directory.status === 'empty' ? (
        <p className="home__hint">No states are available.</p>
      ) : null}

      {directory.status === 'ready' ? (
        <>
          <UsStateMap states={states} />
          <StateSelect states={states} />
        </>
      ) : null}
    </section>
  )
}
