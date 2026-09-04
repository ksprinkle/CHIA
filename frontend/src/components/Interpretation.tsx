import { deriveInterpretation } from '../lib/interpretation'
import type { DimensionScoreInfo } from '../lib/interpretation'
import type { ExplorerResponse } from '../lib/types'

const INSUFFICIENT_DATA_MESSAGE =
  'Not enough available dimension data to compare across dimensions for this county.'

function joinNames(names: string[]): string {
  if (names.length === 0) return ''
  if (names.length === 1) return names[0]
  if (names.length === 2) return `${names[0]} and ${names[1]}`
  return `${names.slice(0, -1).join(', ')}, and ${names[names.length - 1]}`
}

/**
 * One highest-scoring / lowest-scoring sentence, with a factual qualifier
 * appended for any tied dimension that is not percentile-normalized (D2):
 * its score is never described as a percentile.
 */
function dimensionParagraph(
  entries: DimensionScoreInfo[],
  role: 'highest-scoring' | 'lowest-scoring',
): string {
  const names = entries.map((entry) => entry.dimensionName)
  const plural = entries.length > 1
  const sentence = `${joinNames(names)} ${
    plural ? 'are jointly' : 'is'
  } this county's ${role} dimension${plural ? 's' : ''}.`

  const qualifiers = entries
    .filter((entry) => !entry.normalized)
    .map(
      (entry) =>
        `${entry.dimensionName}'s score is a coverage value, not a percentile rank.`,
    )
    .join(' ')

  return qualifiers ? `${sentence} ${qualifiers}` : sentence
}

/**
 * CE-C05 interpretation section (governing specification section 14).
 *
 * Deterministic, application-generated descriptive text derived from the
 * single shared Explorer payload -- no additional request, no API change.
 * Limited to exactly five categories: highest/lowest scoring dimension(s),
 * the score gap between them, data completeness, and composite availability.
 * No cross-county comparison, no score thresholds/bands, and no individual-
 * level, clinical, causal, predictive, or evaluative language.
 */
export function Interpretation({ explorer }: { explorer: ExplorerResponse }) {
  const interpretation = deriveInterpretation(explorer)

  return (
    <section className="interpretation" aria-labelledby="interpretation-heading">
      <h2 id="interpretation-heading">Interpretation</h2>

      <p className="interpretation__completeness">
        {interpretation.availableCount} of {interpretation.totalCount} dimensions
        have an available score for this county.
      </p>

      {interpretation.insufficientData ? (
        <p className="interpretation__insufficient">{INSUFFICIENT_DATA_MESSAGE}</p>
      ) : (
        <>
          <p className="interpretation__highest">
            {dimensionParagraph(interpretation.highest, 'highest-scoring')}
          </p>
          <p className="interpretation__lowest">
            {dimensionParagraph(interpretation.lowest, 'lowest-scoring')}
          </p>
          <p className="interpretation__gap">
            The difference between the highest- and lowest-scoring dimensions
            is {interpretation.scoreGap} points.
          </p>
        </>
      )}

      <p className="interpretation__composite">
        {interpretation.compositeAvailable
          ? 'The experimental composite is available for this county.'
          : `The experimental composite is not available because ${joinNames(
              interpretation.missingDimensions,
            )} ${interpretation.missingDimensions.length > 1 ? 'are' : 'is'} missing.`}
      </p>
    </section>
  )
}
