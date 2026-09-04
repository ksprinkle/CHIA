import { useNavigate } from 'react-router-dom'
import { ComposableMap, Geographies, Geography } from 'react-simple-maps'

import type { County } from '../lib/types'

const MAP_WIDTH = 800
const MAP_HEIGHT = 600

function countyGeographyUrl(stateFips: string): string {
  return `/geo/counties/${stateFips}.topojson`
}

export interface StateCountyMapProps {
  stateFips: string
  counties: County[]
}

/**
 * CE-E03 state-level county map (governing v0.2 UX specification, section
 * 14 "CE-E03 -- State County Map", detailed in section 5).
 *
 * Renders the CE-E01 committed per-state county boundaries
 * (`frontend/public/geo/counties/<state_fips>.topojson`, untouched by this
 * slice) for the counties belonging to one state, and lets the user select a
 * county, navigating to `/counties/:countyFips`. `counties` is the single
 * authoritative per-state county dataset -- see `lib/counties.ts`'s
 * `deriveCountiesForState` -- consumed identically by `CountySelectForState`:
 * a geometry feature is only rendered as selectable when its GEOID (joined
 * by stable FIPS, never by name) matches an entry in `counties`, so the map
 * can never disagree with the accessible selector about which counties
 * exist.
 *
 * The map is zoomed/centered to the selected state's counties using only
 * react-simple-maps' own `path` (a d3 GeoPath already supplied by its
 * `Geographies` render-prop's `bounds()`) -- no additional projection or
 * geometry library is introduced.
 *
 * This is a neutral navigation map: every county receives identical visual
 * treatment. No measure/analytical value is displayed or implied (out of
 * CE-E03 scope -- see CE-E05/CE-E06).
 */
export function StateCountyMap({ stateFips, counties }: StateCountyMapProps) {
  const navigate = useNavigate()
  const countiesByFips = new Map(counties.map((county) => [county.county_fips, county]))

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

            // Zoom/center the state's counties within the shared national
            // AlbersUSA projection, using only `path` (a d3 GeoPath already
            // supplied by react-simple-maps' own render-prop) -- no
            // additional projection/geometry library is introduced. Typed
            // inline so `geo`/`path` keep react-simple-maps' own inferred
            // types rather than a hand-written (and mismatched) signature.
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

                  return (
                    <Geography
                      key={geo.rsmKey}
                      geography={geo}
                      className="state-county-map__county"
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
                    />
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
