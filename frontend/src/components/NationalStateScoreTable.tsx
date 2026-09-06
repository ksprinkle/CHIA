import { formatScoreValue } from '../lib/choropleth'
import type { DimensionMeta } from '../lib/dimensions'
import type { StateSummary } from '../lib/states'
import type { StateDimensionMedian } from '../lib/types'

export interface NationalStateScoreTableProps {
  states: StateSummary[]
  /** state_fips -> the state's display-only median entry for the active dimension. */
  mediansByState: Map<string, StateDimensionMedian>
  dimension: DimensionMeta
}

/**
 * CE-E14b accessible data table -- the structured, non-visual equivalent of
 * the national per-state choropleth (governing v0.2 UX specification sections
 * 7.12 / 9.6), mirroring `CountyScoreTable`.
 *
 * Every state's value is the **display-only median of that state's counties**
 * for the active dimension (CE-E14a), not a CHIA state-level score. The
 * "counties summarised" column makes that explicit. Collapsed by default
 * behind a native `<details>` disclosure.
 */
export function NationalStateScoreTable({
  states,
  mediansByState,
  dimension,
}: NationalStateScoreTableProps) {
  return (
    <details className="national-state-score-table">
      <summary className="national-state-score-table__summary">
        View state data table
      </summary>
      <table>
        <caption>
          {dimension.label} — median of each state’s counties — {states.length} states
        </caption>
        <thead>
          <tr>
            <th scope="col">State</th>
            <th scope="col">{dimension.label} (median of counties)</th>
            <th scope="col">Counties summarised</th>
          </tr>
        </thead>
        <tbody>
          {states.map((state) => {
            const entry = mediansByState.get(state.state_fips)
            const value =
              entry && entry.available && entry.median !== null
                ? formatScoreValue(entry.median, dimension.kind)
                : 'Not available'
            const counties = entry
              ? `${entry.available_county_count} of ${entry.county_count}`
              : '—'
            return (
              <tr key={state.state_fips}>
                <th scope="row">{state.state_name}</th>
                <td>{value}</td>
                <td>{counties}</td>
              </tr>
            )
          })}
        </tbody>
      </table>
    </details>
  )
}
