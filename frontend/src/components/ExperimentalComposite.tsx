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

/**
 * CE-E04 display-correctness fix (governing specification section 6.12): a
 * small non-zero value (e.g. ~0.45) must not silently round to a bare "0",
 * which would be visually indistinguishable from a genuine zero. Whole-number
 * rounding is kept for every value that doesn't collide with zero this way;
 * the underlying persisted value is never altered or recalculated.
 */
function formatCompositeValue(value: number): string {
  const rounded = Math.round(value)
  if (rounded === 0 && value !== 0) {
    return value.toFixed(1)
  }
  return String(rounded)
}

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
        <p className="composite__value">{formatCompositeValue(compositeValue)}</p>
      )}

      {status ? <p className="composite__status">Status: {status}</p> : null}
      <p className="composite__disclosure">{COMPOSITE_DISCLOSURE}</p>
    </section>
  )
}
