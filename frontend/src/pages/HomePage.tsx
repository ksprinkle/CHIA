import { useMemo, useState } from 'react'

import { ChoroplethLegend } from '../components/ChoroplethLegend'
import { DimensionSelector } from '../components/DimensionSelector'
import { ErrorState } from '../components/ErrorState'
import { Loading } from '../components/Loading'
import { NationalStateScoreTable } from '../components/NationalStateScoreTable'
import { UsStateMap } from '../components/UsStateMap'
import { useCountyDirectory } from '../lib/countyDirectory'
import { DIMENSIONS } from '../lib/dimensions'
import { useNationalDimensionScores } from '../lib/nationalScores'
import { deriveStates } from '../lib/states'
import type { AccessProfile, StateDimensionMedian } from '../lib/types'

/**
 * CE-E02 U.S. map landing page (governing v0.2 UX specification, section 14),
 * extended in CE-E14b with an optional national-map measure view (section 4.6
 * / 4.7 / 7.2).
 *
 * Navigation mode (default): `UsStateMap` is a plain state-selection surface;
 * the accessible non-map alternative is the app-header `StateSelect` (CE-E13).
 *
 * Measure mode: choosing a measure colours each state by the **display-only
 * median of that state's counties** for that dimension (`GET
 * /api/v1/states/dimension-scores`, CE-E14a) -- reusing `DimensionSelector`,
 * `ChoroplethLegend`, and `lib/choropleth.ts` unchanged, and adding an
 * accessible per-state values table. The state colour is explicitly labelled
 * as a summary of the state's counties, not a CHIA state-level score (see
 * `Documentation/NATIONAL_MAP_STATE_SUMMARY.md.txt`). Selection is local page
 * state only -- no route or URL change (CE-E14b scope).
 */
export function HomePage() {
  const directory = useCountyDirectory()
  const states = directory.status === 'ready' ? deriveStates(directory.counties) : []

  const [dimensionKey, setDimensionKey] = useState<keyof AccessProfile | null>(null)
  const measureActive = dimensionKey !== null
  const national = useNationalDimensionScores(measureActive)

  const activeDimension =
    dimensionKey !== null
      ? DIMENSIONS.find((dimension) => dimension.key === dimensionKey) ?? null
      : null

  const mediansByState = useMemo<Map<string, StateDimensionMedian> | null>(() => {
    if (activeDimension === null || national.status !== 'ready' || national.data === null) {
      return null
    }
    return new Map(
      national.data.states.map((state) => [state.state_fips, state[activeDimension.key]]),
    )
  }, [activeDimension, national.status, national.data])

  const medianValues = useMemo<Map<string, number | null> | null>(() => {
    if (mediansByState === null) return null
    return new Map(
      [...mediansByState.entries()].map(([stateFips, entry]) => [stateFips, entry.median]),
    )
  }, [mediansByState])

  const choroplethActive = medianValues !== null && activeDimension !== null

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
          <div className="home__map-mode">
            {dimensionKey !== null && activeDimension !== null ? (
              <>
                <DimensionSelector
                  value={dimensionKey}
                  onChange={setDimensionKey}
                  label="Colour states by"
                />
                <button
                  type="button"
                  className="home__map-mode-exit"
                  onClick={() => setDimensionKey(null)}
                >
                  Return to navigation
                </button>
              </>
            ) : (
              <button
                type="button"
                className="home__map-mode-enter"
                onClick={() => setDimensionKey(DIMENSIONS[0].key)}
              >
                Colour states by a measure
              </button>
            )}
          </div>

          {measureActive && national.status === 'loading' ? (
            <p className="home__scores-status" role="status">
              Loading state map colours…
            </p>
          ) : null}

          {measureActive && national.status === 'error' ? (
            <ErrorState
              message="The state map colours could not be loaded. State navigation still works."
              onRetry={national.retry}
            />
          ) : null}

          <UsStateMap
            states={states}
            medians={choroplethActive ? medianValues : undefined}
            activeDimension={choroplethActive ? activeDimension : undefined}
          />

          {choroplethActive && activeDimension !== null && mediansByState !== null ? (
            <>
              <p className="national-map-note">
                Each state is coloured by the <strong>median of its counties’</strong>{' '}
                {activeDimension.label} — a summary of the state’s counties, not a
                CHIA state-level score. On a state’s own map each county is
                coloured individually.
              </p>
              <ChoroplethLegend dimension={activeDimension} />
              <NationalStateScoreTable
                states={states}
                mediansByState={mediansByState}
                dimension={activeDimension}
              />
            </>
          ) : null}
        </>
      ) : null}
    </section>
  )
}
