import { DIMENSION_ORDER } from '../lib/dimensions'
import type { AccessProfile, SourceRef } from '../lib/types'

/**
 * CE-C04 provenance / sources (governing specification section 15).
 *
 * Renders the API-provided sources verbatim: `source_name`, `publisher`,
 * `dataset_name`, `reference_period`, and (CE-E12B) `url`, `accessed_at`,
 * `artifact_filename`, `content_sha256` -- the source-data vintage and the
 * exact build-input artifact (filename + SHA-256) so a profile is traceable
 * to a known source vintage. Every field is rendered only when present. The
 * dimension-to-source association comes from `dimension.source_id`.
 *
 * CE-E04: the full content is unchanged but now sits behind a native
 * `<details>` disclosure, collapsed by default (governing specification
 * section 6.11: provenance "should be accessible without overwhelming the
 * primary experience"), matching the existing `SupportingEvidence` pattern.
 * The section itself remains a labelled region via the `<h2>` outside the
 * disclosure, so it stays identifiable even collapsed.
 */
export function ProvenancePanel({
  sources,
  accessProfile,
}: {
  sources: SourceRef[]
  accessProfile: AccessProfile
}) {
  const dimensionNamesForSource = (sourceId: number): string[] =>
    DIMENSION_ORDER.filter(
      (key) => accessProfile[key].source_id === sourceId,
    ).map((key) => accessProfile[key].dimension_name)

  return (
    <section className="provenance" aria-labelledby="provenance-heading">
      <h2 id="provenance-heading">Sources</h2>

      <details className="provenance__disclosure">
        <summary className="provenance__summary">View sources</summary>

        {sources.length === 0 ? (
          <p className="provenance__empty">No sources recorded.</p>
        ) : (
          <ul className="provenance__list">
            {sources.map((source) => {
              const usedBy = dimensionNamesForSource(source.source_id)
              return (
                <li key={source.source_id} className="provenance__item">
                  <p className="provenance__name">{source.source_name}</p>
                  <dl className="provenance__meta">
                    {source.publisher ? (
                      <div>
                        <dt>Publisher</dt>
                        <dd>{source.publisher}</dd>
                      </div>
                    ) : null}
                    {source.dataset_name ? (
                      <div>
                        <dt>Dataset</dt>
                        <dd>{source.dataset_name}</dd>
                      </div>
                    ) : null}
                    {source.reference_period ? (
                      <div>
                        <dt>Reference period</dt>
                        <dd>{source.reference_period}</dd>
                      </div>
                    ) : null}
                    {source.url ? (
                      <div>
                        <dt>Source download</dt>
                        <dd>
                          <a
                            href={source.url}
                            target="_blank"
                            rel="noreferrer"
                            className="provenance__link"
                          >
                            {source.url}
                          </a>
                        </dd>
                      </div>
                    ) : null}
                    {source.accessed_at ? (
                      <div>
                        <dt>Accessed</dt>
                        <dd>{source.accessed_at}</dd>
                      </div>
                    ) : null}
                    {source.artifact_filename ? (
                      <div>
                        <dt>Source file</dt>
                        <dd>
                          <code className="provenance__artifact">
                            {source.artifact_filename}
                          </code>
                        </dd>
                      </div>
                    ) : null}
                    {source.content_sha256 ? (
                      <div>
                        <dt>SHA-256</dt>
                        <dd>
                          <code className="provenance__artifact">
                            {source.content_sha256}
                          </code>
                        </dd>
                      </div>
                    ) : null}
                    {usedBy.length > 0 ? (
                      <div>
                        <dt>Used by</dt>
                        <dd>{usedBy.join(', ')}</dd>
                      </div>
                    ) : null}
                  </dl>
                </li>
              )
            })}
          </ul>
        )}
      </details>
    </section>
  )
}
