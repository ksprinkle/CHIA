import { formatScoreValue } from '../lib/choropleth'
import type { DimensionMeta } from '../lib/dimensions'
import type { County, CountyDimensionScores } from '../lib/types'

export interface CountyScoreTableProps {
  counties: County[]
  scoresByFips: Map<string, CountyDimensionScores>
  dimension: DimensionMeta
}

/**
 * CE-E10 accessible data table -- the structured, non-visual equivalent of
 * the county choropleth (governing v0.2 UX specification sections 7.12 /
 * 9.6). Lists every county in the state (same FIPS-ascending list the map and
 * the accessible county selector use) with its value on the active dimension,
 * so a user who cannot interpret the colour scale still gets every number.
 *
 * Collapsed by default behind a native `<details>` disclosure, matching the
 * progressive-disclosure pattern used elsewhere in the profile.
 */
export function CountyScoreTable({
  counties,
  scoresByFips,
  dimension,
}: CountyScoreTableProps) {
  return (
    <details className="county-score-table">
      <summary className="county-score-table__summary">
        View county data table
      </summary>
      <table>
        <caption>
          {dimension.label} — {counties.length} counties
        </caption>
        <thead>
          <tr>
            <th scope="col">County</th>
            <th scope="col">{dimension.label}</th>
          </tr>
        </thead>
        <tbody>
          {counties.map((county) => {
            const entry = scoresByFips.get(county.county_fips)
            const dimensionScore = entry ? entry[dimension.key] : undefined
            const value =
              dimensionScore && dimensionScore.available && dimensionScore.score !== null
                ? formatScoreValue(dimensionScore.score, dimension.kind)
                : 'Not available'
            return (
              <tr key={county.county_fips}>
                <th scope="row">{county.county_name}</th>
                <td>{value}</td>
              </tr>
            )
          })}
        </tbody>
      </table>
    </details>
  )
}
