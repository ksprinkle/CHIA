import type { SupportingEvidenceItem } from '../lib/types'

/**
 * CE-C04 supporting evidence for one dimension.
 *
 * A native `<details>` disclosure, subordinate to the primary measure
 * (governing specification section 12 / 13). Renders API-provided values
 * verbatim: it never alters the dimension score, and evidence `raw_value` is
 * shown as provided (no rounding, no precision policy).
 *
 * CE-E11: each item also shows its persisted `variable_id` (a stable machine
 * identifier) alongside the human `display_name`, so a reader can trace the
 * exact variable a supporting figure came from.
 */
export function SupportingEvidence({
  items,
  calculationMethod,
}: {
  items: SupportingEvidenceItem[]
  calculationMethod: string | null
}) {
  if (items.length === 0 && !calculationMethod) return null

  return (
    <details className="evidence">
      <summary className="evidence__summary">Supporting evidence</summary>
      {calculationMethod ? (
        <p className="evidence__method">{calculationMethod}</p>
      ) : null}
      {items.length === 0 ? (
        <p className="evidence__empty">No supporting evidence.</p>
      ) : (
        <ul className="evidence__list">
          {items.map((item) => (
            <li key={item.variable_id} className="evidence__item">
              <span className="evidence__name">{item.display_name}</span>
              <code className="evidence__variable">{item.variable_id}</code>
              <span className="evidence__value">
                {item.raw_value === null
                  ? 'Not reported'
                  : item.unit
                    ? `${item.raw_value} ${item.unit}`
                    : `${item.raw_value}`}
              </span>
              {item.quality_flag ? (
                <span className="evidence__quality">{item.quality_flag}</span>
              ) : null}
            </li>
          ))}
        </ul>
      )}
    </details>
  )
}
