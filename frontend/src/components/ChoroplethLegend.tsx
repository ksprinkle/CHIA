import { MISSING_FILL, rampFor } from '../lib/choropleth'
import type { DimensionMeta } from '../lib/dimensions'

export interface ChoroplethLegendProps {
  dimension: DimensionMeta
}

const COPY: Record<
  DimensionMeta['kind'],
  { scaleName: string; low: string; high: string; caption: string }
> = {
  percentile: {
    scaleName: 'Percentile rank (0–100)',
    low: 'Lower percentile',
    high: 'Higher percentile',
    caption:
      'County percentile rank across the CHIA county universe. Higher values indicate greater geographic access burden.',
  },
  coverage: {
    scaleName: 'Geographic coverage (0–100%)',
    low: '0% covered',
    high: '100% covered',
    caption:
      'MUA/P geographic coverage of the county. This is a coverage percentage, not a percentile, and not the percentage of residents who lack access to care.',
  },
}

/**
 * CE-E10 choropleth legend (governing v0.2 UX specification section 7.6).
 *
 * Makes the semantic distinction between the three percentile dimensions and
 * MUA/P geographic coverage explicit in text and scale labels -- not by
 * colour alone (section 9.5). Each `kind` gets its own ramp and its own
 * caption; a distinct "No data" swatch covers unavailable scores.
 */
export function ChoroplethLegend({ dimension }: ChoroplethLegendProps) {
  const copy = COPY[dimension.kind]
  const [low, mid, high] = rampFor(dimension.kind)

  return (
    <section className="choropleth-legend" aria-label={`Map legend: ${dimension.label}`}>
      <p className="choropleth-legend__measure">
        <strong>{dimension.label}</strong>
        <span className="choropleth-legend__scale">{copy.scaleName}</span>
      </p>
      <div
        className="choropleth-legend__ramp"
        style={{
          background: `linear-gradient(to right, ${low}, ${mid}, ${high})`,
        }}
        aria-hidden="true"
      />
      <p className="choropleth-legend__ends">
        <span>{copy.low}</span>
        <span>{copy.high}</span>
      </p>
      <p className="choropleth-legend__missing">
        <span
          className="choropleth-legend__swatch"
          style={{ background: MISSING_FILL }}
          aria-hidden="true"
        />
        No data — county has no available score for this measure.
      </p>
      <p className="choropleth-legend__caption">{copy.caption}</p>
    </section>
  )
}
