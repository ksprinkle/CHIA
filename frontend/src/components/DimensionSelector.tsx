import type { ChangeEvent } from 'react'

import { DIMENSIONS } from '../lib/dimensions'
import type { DimensionMeta } from '../lib/dimensions'
import type { AccessProfile } from '../lib/types'

export interface DimensionSelectorProps {
  value: keyof AccessProfile
  onChange: (key: keyof AccessProfile) => void
  /**
   * Visible label. Defaults to the CE-E10 state-page wording ("Colour
   * counties by"); CE-E14b passes "Colour states by" when the same control
   * drives the national per-state choropleth.
   */
  label?: string
}

/**
 * CE-E10 measure selector for the county / state choropleth (governing v0.2
 * UX specification section 7.1).
 *
 * A native, labelled `<select>` over the four access dimensions. Selecting a
 * value re-colours the map, updates the legend, and updates the accessible
 * data table; it does not navigate and holds no URL state (local component
 * state only). Reused unchanged by CE-E14b for the national map.
 */
export function DimensionSelector({
  value,
  onChange,
  label = 'Colour counties by',
}: DimensionSelectorProps) {
  function handleChange(event: ChangeEvent<HTMLSelectElement>) {
    onChange(event.target.value as keyof AccessProfile)
  }

  return (
    <div className="dimension-selector">
      <label className="dimension-selector__label" htmlFor="map-dimension">
        {label}
      </label>
      <select
        id="map-dimension"
        className="dimension-selector__control"
        value={value}
        onChange={handleChange}
      >
        {DIMENSIONS.map((dimension: DimensionMeta) => (
          <option key={dimension.key} value={dimension.key}>
            {dimension.label}
          </option>
        ))}
      </select>
    </div>
  )
}
