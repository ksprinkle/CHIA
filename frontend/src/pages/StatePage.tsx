import { Link, useParams } from 'react-router-dom'

import { ErrorState } from '../components/ErrorState'
import { Loading } from '../components/Loading'
import { NotFound } from '../components/NotFound'
import { useCountyDirectory } from '../lib/countyDirectory'
import { deriveStates } from '../lib/states'

const TWO_DIGIT_FIPS = /^\d{2}$/

function BackToUnitedStates() {
  return (
    <p className="state-page__back">
      <Link to="/">United States</Link>
    </p>
  )
}

/**
 * CE-E02 state route (`/states/:stateFips`) -- decision (b) from the CE-E02
 * approval: selecting a state navigates here rather than merely
 * acknowledging the selection in place.
 *
 * This is intentionally a minimal placeholder: it identifies the selected
 * state and explicitly defers the county-level map to CE-E03. It reuses the
 * same `deriveStates` derivation as `UsStateMap` / `StateSelect`
 * (`lib/states.ts`) -- there is no separate state lookup. The existing
 * global county selector (rendered in `Layout`) remains available on this
 * route as the way to actually reach a county profile until CE-E03 adds the
 * state/county map.
 */
export function StatePage() {
  const { stateFips = '' } = useParams<{ stateFips: string }>()
  const directory = useCountyDirectory()

  if (!TWO_DIGIT_FIPS.test(stateFips)) {
    return (
      <>
        <NotFound
          title="Invalid state FIPS"
          message={`"${stateFips}" is not a two-digit state FIPS code.`}
        />
        <BackToUnitedStates />
      </>
    )
  }

  if (directory.status === 'loading') {
    return <Loading label="Loading states…" />
  }

  if (directory.status === 'error') {
    return (
      <ErrorState
        message="The state list could not be loaded."
        onRetry={directory.retry}
      />
    )
  }

  const state = deriveStates(directory.counties).find(
    (candidate) => candidate.state_fips === stateFips,
  )

  if (!state) {
    return (
      <>
        <NotFound
          title="State not found"
          message={`No state with FIPS ${stateFips} is in the CHIA state universe.`}
        />
        <BackToUnitedStates />
      </>
    )
  }

  return (
    <section className="state-page" aria-labelledby="state-page-heading">
      <BackToUnitedStates />
      <h1 id="state-page-heading">{state.state_name}</h1>
      <p className="county-page__fips">FIPS {state.state_fips}</p>
      <p className="state-page__placeholder">
        County-level exploration for {state.state_name} is not yet available in
        this view. Use the county selector above to open a specific county
        profile directly.
      </p>
    </section>
  )
}
