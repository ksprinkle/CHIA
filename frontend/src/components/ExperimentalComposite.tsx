import type { ExperimentalComposite as ExperimentalCompositeData } from '../lib/types'

/**
 * CE-C04 experimental composite.
 *
 * Renders the persisted composite exactly as returned by the API -- value,
 * fixed label, status, and (when the value is null) the API-provided missing
 * dimensions. It is never recomputed and no weights/formula/constants appear
 * here. Placed after the four dimensions and kept visually secondary to them
 * (governing specification sections 9 and 12).
 */
const COMPOSITE_DISCLOSURE =
  'The experimental composite is an equal-weight combination of the four dimension access scores. It is shown only when all four dimension scores are available, and it is provisional — not a validated measure.'

export function ExperimentalComposite({
  composite,
}: {
  composite: ExperimentalCompositeData
}) {
  const {
    composite_value: compositeValue,
    label,
    status,
    missing_dimensions: missingDimensions,
  } = composite

  return (
    <section className="composite" aria-labelledby="composite-heading">
      <h2 id="composite-heading">Experimental composite</h2>
      <p className="composite__label">{label}</p>

      {compositeValue === null ? (
        <p className="composite__unavailable">
          Not available
          {missingDimensions.length > 0
            ? ` — missing: ${missingDimensions.join(', ')}`
            : null}
        </p>
      ) : (
        <p className="composite__value">{String(Math.round(compositeValue))}</p>
      )}

      {status ? <p className="composite__status">Status: {status}</p> : null}
      <p className="composite__disclosure">{COMPOSITE_DISCLOSURE}</p>
    </section>
  )
}
