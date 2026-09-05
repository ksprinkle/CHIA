import type { ChangeEvent } from 'react'

import { DIMENSIONS } from '../lib/dimensions'
import type { DimensionMeta } from '../lib/dimensions'
import type { AccessProfile } from '../lib/types'

export interface DimensionSelectorProps {
  value: keyof AccessProfile
  onChange: (key: keyof AccessProfile) => void
}

/**
 * CE-E10 measure selector for the state county choropleth (governing v0.2 UX
 * specification section 7.1).
 *
 * A native, labelled `<select>` over the four access dimensions. Selecting a
 * value re-colours the map, updates the legend, and updates the accessible
 * data table; it does not navigate and holds no URL state (local component
 * state only, per the approved CE-E10 scope).
 */
export function DimensionSelector({ value, onChange }: DimensionSelectorProps) {
  function handleChange(event: ChangeEvent<HTMLSelectElement>) {
    onChange(event.target.value as keyof AccessProfile)
  }

  return (
    <div className="dimension-selector">
      <label className="dimension-selector__label" htmlFor="map-dimension">
        Colour counties by
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
