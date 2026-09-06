import { useNavigate } from 'react-router-dom'
import { ComposableMap, Geographies, Geography } from 'react-simple-maps'

import { fillForScore, formatScoreValue } from '../lib/choropleth'
import type { DimensionMeta } from '../lib/dimensions'
import type { StateSummary } from '../lib/states'

/**
 * CE-E01 committed geographic asset -- not regenerated or modified here.
 * CE-DEP02: prefixed with `import.meta.env.BASE_URL` (always trailing-slashed)
 * so it resolves under the deployment base, e.g. `/CHIA/geo/us-states.topojson`.
 */
const US_STATES_GEOGRAPHY_URL = `${import.meta.env.BASE_URL}geo/us-states.topojson`

export interface UsStateMapProps {
  states: StateSummary[]
  /**
   * CE-E14b analytical colouring. `medians` maps `state_fips` -> the state's
   * **display-only** median of its counties' scores on `activeDimension`
   * (from `GET /api/v1/states/dimension-scores`, CE-E14a). When BOTH are
   * supplied each state is filled by `lib/choropleth.ts`'s `fillForScore`
   * (the same ramp the state county map uses) and its `<title>` carries the
   * value; a state absent from the map, or a `null` median, renders as
   * `MISSING_FILL` / "no data". When omitted the map is visually identical to
   * CE-E02 (navigation mode).
   *
   * Supplying these never changes the navigation contract: every state is
   * still a keyboard- and pointer-activatable control that navigates to
   * `/states/:stateFips`, and its accessible name stays `Select {state name}`.
   */
  medians?: Map<string, number | null>
  activeDimension?: DimensionMeta
}

/**
 * CE-E02 U.S. map landing experience (governing v0.2 UX specification,
 * section 14, "CE-E02 -- U.S. Map Landing Experience"), extended in CE-E14b
 * with an optional per-state analytical choropleth layer (section 4.6 / 7.2).
 *
 * Renders the CE-E01 committed national state boundaries and lets the user
 * select a state, navigating to `/states/:stateFips`. `states` is the single
 * authoritative supported-state dataset (see `lib/states.ts`): a geography
 * feature is only rendered as selectable when its GEOID matches an entry in
 * `states`, so the map can never disagree with `StateSelect` (the required
 * accessible alternative) about which states exist.
 *
 * Each state feature carries an SVG `<title>`: the state name in navigation
 * mode (governing spec section 4.4, CE-E10.1), and the state name plus its
 * display-only median value in measure mode. The `aria-label`
 * (`Select {state name}`) remains the authoritative accessible name (it wins
 * over `<title>` in the accessible-name computation), so keyboard and
 * screen-reader behaviour is unchanged.
 *
 * The measure selector, legend, per-state labelling note, and the accessible
 * state-values table live in `HomePage`. This component performs no analytical
 * calculation -- `medians` are rendered exactly as supplied.
 */
export function UsStateMap({ states, medians, activeDimension }: UsStateMapProps) {
  const navigate = useNavigate()
  const statesByFips = new Map(states.map((state) => [state.state_fips, state]))
  const choropleth = medians !== undefined && activeDimension !== undefined

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

              let fillStyle: { default: { fill: string } } | undefined
              let titleText = state.state_name

              if (choropleth) {
                const median = medians.get(stateFips) ?? null
                fillStyle = {
                  default: { fill: fillForScore(median, activeDimension.kind) },
                }
                titleText =
                  median === null
                    ? `${state.state_name} — no data`
                    : `${state.state_name} — ${formatScoreValue(
                        median,
                        activeDimension.kind,
                      )}`
              }

              return (
                <Geography
                  key={geo.rsmKey}
                  geography={geo}
                  className="us-state-map__state"
                  style={fillStyle}
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
                >
                  <title>{titleText}</title>
                </Geography>
              )
            })
          }
        </Geographies>
      </ComposableMap>
    </div>
  )
}
