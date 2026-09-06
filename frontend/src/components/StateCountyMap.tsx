import { useNavigate } from 'react-router-dom'
import { ComposableMap, Geographies, Geography } from 'react-simple-maps'

import type { DimensionMeta } from '../lib/dimensions'
import { fillForScore, formatScoreValue } from '../lib/choropleth'
import type { County, CountyDimensionScores } from '../lib/types'

const MAP_WIDTH = 800
const MAP_HEIGHT = 600

function countyGeographyUrl(stateFips: string): string {
  // CE-E01 committed asset. CE-DEP02: `import.meta.env.BASE_URL` (always
  // trailing-slashed) prefixes it so it resolves under the deployment base,
  // e.g. `/CHIA/geo/counties/06.topojson`.
  return `${import.meta.env.BASE_URL}geo/counties/${stateFips}.topojson`
}

export interface StateCountyMapProps {
  stateFips: string
  counties: County[]
  /**
   * CE-E10 analytical colouring. When BOTH are supplied the map paints each
   * county by its score on `activeDimension`; when omitted (scores loading or
   * failed) the map renders neutral, exactly as CE-E03. Supplying these never
   * changes the navigation contract: every county is still a keyboard- and
   * pointer-activatable control that navigates to `/counties/:countyFips`, and
   * its accessible name is unchanged (`Select {county name}`).
   */
  scores?: Map<string, CountyDimensionScores>
  activeDimension?: DimensionMeta
}

/**
 * CE-E03 state-level county map (governing v0.2 UX specification, section
 * 14 "CE-E03 -- State County Map", detailed in section 5), extended in
 * CE-E10 with an optional analytical choropleth layer (section 7).
 *
 * Renders the CE-E01 committed per-state county boundaries
 * (`frontend/public/geo/counties/<state_fips>.topojson`, untouched) for the
 * counties belonging to one state, and lets the user select a county,
 * navigating to `/counties/:countyFips`. `counties` is the single
 * authoritative per-state county dataset -- see `lib/counties.ts`'s
 * `deriveCountiesForState` -- consumed identically by `CountySelectForState`:
 * a geometry feature is only rendered as selectable when its GEOID (joined
 * by stable FIPS, never by name) matches an entry in `counties`.
 *
 * The map is zoomed/centered to the selected state's counties using only
 * react-simple-maps' own `path` -- no additional projection or geometry
 * library is introduced.
 *
 * CE-E10: when `scores` + `activeDimension` are provided, each county's
 * `fill` comes from `lib/choropleth.ts` (a hand-rolled ramp; no d3 import)
 * and an SVG `<title>` carries the county name and its value on hover. The
 * legend, dimension selector, and accessible data table live in `StatePage`.
 * When they are absent the map is visually identical to CE-E03.
 */
export function StateCountyMap({
  stateFips,
  counties,
  scores,
  activeDimension,
}: StateCountyMapProps) {
  const navigate = useNavigate()
  const countiesByFips = new Map(counties.map((county) => [county.county_fips, county]))
  const choropleth = scores !== undefined && activeDimension !== undefined

  function selectCounty(countyFips: string) {
    if (countiesByFips.has(countyFips)) {
      navigate(`/counties/${countyFips}`)
    }
  }

  return (
    <div className="state-county-map" role="group" aria-label="County map">
      <ComposableMap
        width={MAP_WIDTH}
        height={MAP_HEIGHT}
        projection="geoAlbersUsa"
        className="state-county-map__svg"
        role="img"
        aria-label="Select a county to open its profile"
      >
        <Geographies geography={countyGeographyUrl(stateFips)}>
          {({ geographies, path }) => {
            const supported = geographies.filter((geo) => countiesByFips.has(String(geo.id)))

            let transform = ''
            if (supported.length > 0) {
              let minX = Infinity
              let minY = Infinity
              let maxX = -Infinity
              let maxY = -Infinity

              for (const geo of supported) {
                const [[x0, y0], [x1, y1]] = path.bounds(geo)
                minX = Math.min(minX, x0)
                minY = Math.min(minY, y0)
                maxX = Math.max(maxX, x1)
                maxY = Math.max(maxY, y1)
              }

              const boundsWidth = Math.max(maxX - minX, 1)
              const boundsHeight = Math.max(maxY - minY, 1)
              const padding = 0.9
              const scale = Math.min(
                (MAP_WIDTH / boundsWidth) * padding,
                (MAP_HEIGHT / boundsHeight) * padding,
              )
              const centerX = (minX + maxX) / 2
              const centerY = (minY + maxY) / 2
              const translateX = MAP_WIDTH / 2 - scale * centerX
              const translateY = MAP_HEIGHT / 2 - scale * centerY
              transform = `translate(${translateX} ${translateY}) scale(${scale})`
            }

            return (
              <g transform={transform}>
                {supported.map((geo) => {
                  const countyFips = String(geo.id)
                  const county = countiesByFips.get(countyFips)
                  if (!county) return null

                  let fillStyle: { default: { fill: string } } | undefined
                  let titleText = county.county_name

                  if (choropleth) {
                    const entry = scores.get(countyFips)
                    const dimensionScore = entry
                      ? entry[activeDimension.key]
                      : undefined
                    const score =
                      dimensionScore && dimensionScore.available
                        ? dimensionScore.score
                        : null
                    fillStyle = {
                      default: { fill: fillForScore(score, activeDimension.kind) },
                    }
                    titleText =
                      score === null
                        ? `${county.county_name} — no data`
                        : `${county.county_name} — ${formatScoreValue(
                            score,
                            activeDimension.kind,
                          )}`
                  }

                  return (
                    <Geography
                      key={geo.rsmKey}
                      geography={geo}
                      className="state-county-map__county"
                      style={fillStyle}
                      tabIndex={0}
                      role="button"
                      aria-label={`Select ${county.county_name}`}
                      onClick={() => selectCounty(countyFips)}
                      onKeyDown={(event) => {
                        if (event.key === 'Enter' || event.key === ' ') {
                          event.preventDefault()
                          selectCounty(countyFips)
                        }
                      }}
                    >
                      <title>{titleText}</title>
                    </Geography>
                  )
                })}
              </g>
            )
          }}
        </Geographies>
      </ComposableMap>
    </div>
  )
}
