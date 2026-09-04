import { useNavigate } from 'react-router-dom'
import { ComposableMap, Geographies, Geography } from 'react-simple-maps'

import type { StateSummary } from '../lib/states'

/** CE-E01 committed geographic asset -- not regenerated or modified here. */
const US_STATES_GEOGRAPHY_URL = '/geo/us-states.topojson'

export interface UsStateMapProps {
  states: StateSummary[]
}

/**
 * CE-E02 U.S. map landing experience (governing v0.2 UX specification,
 * section 14, "CE-E02 -- U.S. Map Landing Experience").
 *
 * Renders the CE-E01 committed national state boundaries and lets the user
 * select a state, navigating to `/states/:stateFips`. `states` is the single
 * authoritative supported-state dataset (see `lib/states.ts`): a geography
 * feature is only rendered as selectable when its GEOID matches an entry in
 * `states`, so the map can never disagree with `StateSelect` (the required
 * accessible alternative) about which states exist.
 *
 * This component only navigates by state FIPS; it performs no analytical
 * calculation and carries no measure/visualization state (out of CE-E02
 * scope -- see CE-E05/CE-E06).
 */
export function UsStateMap({ states }: UsStateMapProps) {
  const navigate = useNavigate()
  const statesByFips = new Map(states.map((state) => [state.state_fips, state]))

  function selectState(stateFips: string) {
    if (statesByFips.has(stateFips)) {
      navigate(`/states/${stateFips}`)
    }
  }

  return (
    <div className="us-state-map" role="group" aria-label="Map of the United States">
      <ComposableMap
        projection="geoAlbersUsa"
        className="us-state-map__svg"
        role="img"
        aria-label="Select a state to explore its counties"
      >
        <Geographies geography={US_STATES_GEOGRAPHY_URL}>
          {({ geographies }) =>
            geographies.map((geo) => {
              const stateFips = String(geo.id)
              const state = statesByFips.get(stateFips)
              if (!state) return null

              return (
                <Geography
                  key={geo.rsmKey}
                  geography={geo}
                  className="us-state-map__state"
                  tabIndex={0}
                  role="button"
                  aria-label={`Select ${state.state_name}`}
                  onClick={() => selectState(stateFips)}
                  onKeyDown={(event) => {
                    if (event.key === 'Enter' || event.key === ' ') {
                      event.preventDefault()
                      selectState(stateFips)
                    }
                  }}
                />
              )
            })
          }
        </Geographies>
      </ComposableMap>
    </div>
  )
}
