import { ErrorState } from '../components/ErrorState'
import { Loading } from '../components/Loading'
import { UsStateMap } from '../components/UsStateMap'
import { useCountyDirectory } from '../lib/countyDirectory'
import { deriveStates } from '../lib/states'

/**
 * CE-E02 U.S. map landing page (governing v0.2 UX specification, section 14,
 * "CE-E02 -- U.S. Map Landing Experience").
 *
 * The U.S. map is the primary navigation surface. `UsStateMap` derives its
 * state list from `deriveStates(directory.counties)` (`lib/states.ts`).
 *
 * CE-E13 moved the accessible non-map alternative (`StateSelect`) into the
 * app header, where it is present on every route and is the first step of the
 * select-a-state-then-a-county flow; the landing page therefore no longer
 * renders its own copy. The state-gated county selector (also in the shell)
 * stays disabled here until a state is chosen.
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

      {directory.status === 'ready' ? <UsStateMap states={states} /> : null}
    </section>
  )
}
