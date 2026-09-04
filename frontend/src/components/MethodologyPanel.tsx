import { DIMENSION_ORDER } from '../lib/dimensions'
import type { AccessProfile, MethodologyBlock } from '../lib/types'

/**
 * CE-C04 methodology exposure (governing specification section 15).
 *
 * Renders API-provided methodology metadata and each dimension's
 * `calculation_method` verbatim. It does not reproduce or derive the CE-A00
 * percentile formula, correct persisted text, or add methodological claims.
 *
 * CE-E04: the full content is unchanged but now sits behind a native
 * `<details>` disclosure, collapsed by default (governing specification
 * section 6.10: "Methodology should be presented in expandable or drill-down
 * form where practical"), matching the existing `SupportingEvidence`
 * pattern. The section itself remains a labelled region via the `<h2>`
 * outside the disclosure, so it stays identifiable even collapsed.
 */
export function MethodologyPanel({
  methodology,
  accessProfile,
}: {
  methodology: MethodologyBlock
  accessProfile: AccessProfile
}) {
  return (
    <section className="methodology" aria-labelledby="methodology-heading">
      <h2 id="methodology-heading">Methodology</h2>

      <details className="methodology__disclosure">
        <summary className="methodology__summary">View methodology</summary>

        <dl className="methodology__meta">
          <div>
            <dt>Methodology version</dt>
            <dd>{methodology.methodology_version}</dd>
          </div>
          <div>
            <dt>Name</dt>
            <dd>{methodology.name}</dd>
          </div>
          {methodology.normalization_method ? (
            <div>
              <dt>Normalization method</dt>
              <dd>{methodology.normalization_method}</dd>
            </div>
          ) : null}
          {methodology.status ? (
            <div>
              <dt>Status</dt>
              <dd>{methodology.status}</dd>
            </div>
          ) : null}
          {methodology.created_at ? (
            <div>
              <dt>Created</dt>
              <dd>{methodology.created_at}</dd>
            </div>
          ) : null}
        </dl>

        {methodology.description ? (
          <p className="methodology__description">{methodology.description}</p>
        ) : null}

        <p className="methodology__calc-label">Dimension calculation methods</p>
        <dl className="methodology__calc">
          {DIMENSION_ORDER.map((key) => {
            const dimension = accessProfile[key]
            return dimension.calculation_method ? (
              <div key={key}>
                <dt>{dimension.dimension_name}</dt>
                <dd>{dimension.calculation_method}</dd>
              </div>
            ) : null
          })}
        </dl>
      </details>
    </section>
  )
}
