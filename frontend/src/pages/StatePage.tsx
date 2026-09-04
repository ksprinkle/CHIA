import { Link, useParams } from 'react-router-dom'

import { CountySelectForState } from '../components/CountySelectForState'
import { ErrorState } from '../components/ErrorState'
import { Loading } from '../components/Loading'
import { NotFound } from '../components/NotFound'
import { StateCountyMap } from '../components/StateCountyMap'
import { useCountyDirectory } from '../lib/countyDirectory'
import { deriveCountiesForState } from '../lib/counties'
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
 * State route (`/states/:stateFips`) -- decision (b) from the CE-E02
 * approval: selecting a state navigates here rather than merely
 * acknowledging the selection in place.
 *
 * CE-E02 established FIPS validation, state resolution (`deriveStates`,
 * `lib/states.ts`), and loading/error/not-found handling, all unchanged
 * here. CE-E03 replaces the former placeholder paragraph with the county
 * map (`StateCountyMap`) and the accessible, state-scoped county selector
 * (`CountySelectForState`). Both consume the same
 * `deriveCountiesForState(directory.counties, stateFips)` call
 * (`lib/counties.ts`) -- there is no second, independently defined county
 * list. Selecting a county through either control navigates to the existing
 * `/counties/:countyFips` route, unchanged. The existing global county
 * selector (rendered in `Layout`) remains available on this route too.
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

  const counties = deriveCountiesForState(directory.counties, stateFips)

  return (
    <section className="state-page" aria-labelledby="state-page-heading">
      <BackToUnitedStates />
      <h1 id="state-page-heading">{state.state_name}</h1>
      <p className="county-page__fips">FIPS {state.state_fips}</p>
      <StateCountyMap stateFips={state.state_fips} counties={counties} />
      <CountySelectForState counties={counties} stateName={state.state_name} />
    </section>
  )
}
