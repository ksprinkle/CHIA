import { useMemo, useState } from 'react'
import { Link, useParams } from 'react-router-dom'

import { ChoroplethLegend } from '../components/ChoroplethLegend'
import { CountyScoreTable } from '../components/CountyScoreTable'
import { CountySelectForState } from '../components/CountySelectForState'
import { DimensionSelector } from '../components/DimensionSelector'
import { ErrorState } from '../components/ErrorState'
import { Loading } from '../components/Loading'
import { NotFound } from '../components/NotFound'
import { StateCountyMap } from '../components/StateCountyMap'
import { useCountyDirectory } from '../lib/countyDirectory'
import { deriveCountiesForState } from '../lib/counties'
import { DIMENSIONS } from '../lib/dimensions'
import { deriveStates } from '../lib/states'
import type { StateSummary } from '../lib/states'
import { useStateDimensionScores } from '../lib/stateScores'
import type { AccessProfile, County, CountyDimensionScores } from '../lib/types'

const TWO_DIGIT_FIPS = /^\d{2}$/

function BackToUnitedStates() {
  return (
    <p className="state-page__back">
      <Link to="/">United States</Link>
    </p>
  )
}

/**
 * Inner view for a resolved state: the CE-E03 county map + accessible county
 * selector, plus the CE-E10 analytical layer (dimension selector, choropleth
 * colouring of the same map, legend, and the accessible data table).
 *
 * The CE-E09 `dimension-scores` request is made here so it only fires for a
 * state that actually exists. While it is loading or has failed, the map
 * renders exactly as CE-E03 (neutral, fully navigable); the analytical
 * controls appear only once scores are available. The active dimension is
 * local component state -- no route or URL change.
 */
function StateView({
  state,
  counties,
}: {
  state: StateSummary
  counties: County[]
}) {
  const scores = useStateDimensionScores(state.state_fips)
  const [dimensionKey, setDimensionKey] = useState<keyof AccessProfile>(
    DIMENSIONS[0].key,
  )
  const activeDimension =
    DIMENSIONS.find((dimension) => dimension.key === dimensionKey) ?? DIMENSIONS[0]

  const scoresByFips = useMemo<Map<string, CountyDimensionScores> | null>(() => {
    if (scores.status !== 'ready' || scores.data === null) return null
    return new Map(scores.data.counties.map((county) => [county.county_fips, county]))
  }, [scores.status, scores.data])

  const choroplethActive = scoresByFips !== null

  return (
    <>
      {choroplethActive ? (
        <DimensionSelector value={dimensionKey} onChange={setDimensionKey} />
      ) : null}

      <StateCountyMap
        stateFips={state.state_fips}
        counties={counties}
        scores={choroplethActive ? scoresByFips : undefined}
        activeDimension={choroplethActive ? activeDimension : undefined}
      />

      {scores.status === 'loading' ? (
        <p className="state-page__scores-status" role="status">
          Loading county map colours…
        </p>
      ) : null}

      {scores.status === 'error' ? (
        <ErrorState
          message="The county map colours could not be loaded. County selection still works."
          onRetry={scores.retry}
        />
      ) : null}

      {choroplethActive ? <ChoroplethLegend dimension={activeDimension} /> : null}

      <CountySelectForState counties={counties} stateName={state.state_name} />

      {choroplethActive ? (
        <CountyScoreTable
          counties={counties}
          scoresByFips={scoresByFips}
          dimension={activeDimension}
        />
      ) : null}
    </>
  )
}

/**
 * State route (`/states/:stateFips`).
 *
 * CE-E02 established FIPS validation, state resolution (`deriveStates`), and
 * loading/error/not-found handling, all unchanged. CE-E03 added the county
 * map (`StateCountyMap`) and the accessible, state-scoped county selector
 * (`CountySelectForState`), both consuming the same
 * `deriveCountiesForState(directory.counties, stateFips)` list. CE-E10 adds an
 * analytical choropleth layer on top of that same map (see `StateView`),
 * consuming the CE-E09 `/states/{state_fips}/dimension-scores` endpoint; it
 * does not change the county navigation contract.
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
      <StateView state={state} counties={counties} />
    </section>
  )
}
