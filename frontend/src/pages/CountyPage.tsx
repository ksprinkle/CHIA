import { Link, useParams } from 'react-router-dom'

import { ErrorState } from '../components/ErrorState'
import { ExperimentalComposite } from '../components/ExperimentalComposite'
import { Interpretation } from '../components/Interpretation'
import { Loading } from '../components/Loading'
import { MethodologyPanel } from '../components/MethodologyPanel'
import { NotFound } from '../components/NotFound'
import { ProvenancePanel } from '../components/ProvenancePanel'
import { SupportingEvidence } from '../components/SupportingEvidence'
import { useCountyDirectory } from '../lib/countyDirectory'
import { DIMENSION_ORDER } from '../lib/dimensions'
import { CountyExplorerProvider, useCountyExplorer } from '../lib/countyExplorer'
import type { AccessProfile, DimensionProfile, SourceRef } from '../lib/types'

const FIVE_DIGIT_FIPS = /^\d{5}$/

/** Fixed score explanation (governing specification section 12.2). */
const SCORE_EXPLANATION =
  'Scores are percentile values relative to the CHIA county universe. Higher values indicate greater geographic access burden.'

/** Fixed geographic-coverage caveat (governing specification section 12.3). */
const GEOGRAPHIC_COVERAGE_CAVEAT =
  'Geographic coverage is not the percentage of residents who lack access to care.'

function BackToStart() {
  return (
    <p className="county-page__back">
      <Link to="/">Return to the start</Link>
    </p>
  )
}

function formatState(stateName: string, stateAbbr: string): string {
  const name = stateName.trim()
  if (name && stateAbbr) return `${name} (${stateAbbr})`
  return name || stateAbbr || '—'
}

function formatCompleteness(status: string | null): string {
  if (!status) return 'Unknown'
  return status.charAt(0).toUpperCase() + status.slice(1)
}

function formatScore(score: number): string {
  return String(Math.round(score))
}

/**
 * CE-E04 geographic breadcrumb (governing specification section 6.2):
 * `United States → {State} → {County}`. `stateFips` comes from the canonical
 * county directory record already resolved by `CountyPage` before rendering
 * the profile (the Explorer payload's own `county` block has no
 * `state_fips` field) -- no new API data and no type change was needed.
 */
function Breadcrumb({
  stateFips,
  stateName,
  countyName,
}: {
  stateFips: string
  stateName: string
  countyName: string
}) {
  return (
    <nav className="county-profile__breadcrumb" aria-label="Breadcrumb">
      <ol className="breadcrumb__list">
        <li className="breadcrumb__item">
          <Link to="/">United States</Link>
        </li>
        <li className="breadcrumb__item">
          <Link to={`/states/${stateFips}`}>{stateName}</Link>
        </li>
        <li className="breadcrumb__item" aria-current="page">
          {countyName}
        </li>
      </ol>
    </nav>
  )
}

function clampPercent(value: number): number {
  return Math.min(100, Math.max(0, value))
}

/**
 * CE-E05 percentile position indicator (governing specification section
 * 12.4/12.3): a marker on a fixed 0-100 track, communicating *relative
 * position* rather than a filled proportion. A dot marker is always a
 * fixed-size visible element regardless of position, so a genuine 0th
 * percentile is still clearly visible at the track's start -- unlike a
 * filled bar, it cannot visually "disappear" at zero.
 *
 * Purely decorative (`aria-hidden`): the adjacent visible text in
 * `SnapshotItem` is the actual accessible value/label, unchanged from
 * CE-E04 -- this marker never becomes the sole source of meaning.
 */
function PercentileIndicator({ value }: { value: number }) {
  return (
    <div className="percentile-indicator" aria-hidden="true">
      <div className="percentile-indicator__track">
        <span
          className="percentile-indicator__marker"
          style={{ left: `${clampPercent(value)}%` }}
        />
      </div>
    </div>
  )
}

/**
 * CE-E05 geographic-coverage indicator (governing specification section
 * 12.5/7.4): a filled proportion bar -- a different visual metaphor from
 * `PercentileIndicator`'s position marker -- so MUA/P is never presented on
 * the same semantic scale as the three percentile dimensions. Purely
 * decorative (`aria-hidden`); the adjacent visible text remains the actual
 * accessible value, which is what guarantees a genuine 0% coverage value is
 * never lost even though its fill is visually thin.
 */
function CoverageIndicator({ value }: { value: number }) {
  return (
    <div className="coverage-indicator" aria-hidden="true">
      <div className="coverage-indicator__track">
        <span
          className="coverage-indicator__fill"
          style={{ width: `${clampPercent(value)}%` }}
        />
      </div>
    </div>
  )
}

/**
 * CE-E04 healthcare access snapshot (governing specification section 6.3),
 * upgraded in CE-E05 (section 14 "Visualization Layer") with an actual
 * visual indicator per dimension. The visible text value/label from CE-E04
 * is unchanged and remains the accessible source of truth; the indicator is
 * a decorative supplement, never the only representation (section 12.12).
 * Percentile dimensions use `PercentileIndicator` (position on a 0-100
 * scale); MUA/P uses the visually distinct `CoverageIndicator` (filled
 * proportion) -- never the same widget or scale (section 7.4). Neither
 * indicator implies higher/lower is "better" or "worse": both are neutral
 * position/proportion displays with a single, non-graded color.
 */
function SnapshotItem({ dimension }: { dimension: DimensionProfile }) {
  const { dimension_name: dimensionName, available, score, normalized } = dimension
  const hasScore = available && score !== null

  return (
    <li className="snapshot__item">
      <span className="snapshot__name">{dimensionName}</span>
      {hasScore ? (
        <>
          <span className="snapshot__value">
            {formatScore(score)}
            <span className="snapshot__unit">
              {normalized ? 'percentile' : '% coverage'}
            </span>
          </span>
          {normalized ? (
            <PercentileIndicator value={score} />
          ) : (
            <CoverageIndicator value={score} />
          )}
        </>
      ) : (
        <span className="snapshot__value snapshot__value--unavailable">
          Not available
        </span>
      )}
    </li>
  )
}

function Snapshot({ accessProfile }: { accessProfile: AccessProfile }) {
  return (
    <section className="snapshot" aria-labelledby="snapshot-heading">
      <h2 id="snapshot-heading">Healthcare access snapshot</h2>
      <ul className="snapshot__list">
        {DIMENSION_ORDER.map((key) => (
          <SnapshotItem key={key} dimension={accessProfile[key]} />
        ))}
      </ul>
    </section>
  )
}

/**
 * CE-E06 dimension-scoped methodology (governing specification section
 * 6.10/8.6/13.11): shows only *this* dimension's own calculation method and
 * normalization method -- never the full page-level `MethodologyBlock`,
 * which remains intact and unchanged in `MethodologyPanel` as the
 * comprehensive reference view. No new analytical content: both values are
 * already persisted on `DimensionProfile`/`PrimaryMeasure`.
 */
function DimensionMethodology({
  calculationMethod,
  normalizationMethod,
}: {
  calculationMethod: string | null
  normalizationMethod: string | null
}) {
  if (!calculationMethod && !normalizationMethod) return null

  return (
    <div className="dimension-methodology">
      <h4 className="dimension-methodology__heading">Methodology</h4>
      <dl className="dimension-methodology__meta">
        {calculationMethod ? (
          <div>
            <dt>Calculation method</dt>
            <dd>{calculationMethod}</dd>
          </div>
        ) : null}
        {normalizationMethod ? (
          <div>
            <dt>Normalization method</dt>
            <dd>{normalizationMethod}</dd>
          </div>
        ) : null}
      </dl>
    </div>
  )
}

/**
 * CE-E06 dimension-scoped provenance (governing specification section
 * 6.11/8.7/13.11): shows only the single source that this dimension's
 * `source_id` identifies -- never the full source list, which remains
 * intact and unchanged in `ProvenancePanel` as the comprehensive reference
 * view. The source lookup uses the existing `source_id` join, the same one
 * `ProvenancePanel` already uses for its "Used by" column.
 */
function DimensionProvenance({ source }: { source: SourceRef | null }) {
  if (!source) return null

  return (
    <div className="dimension-provenance">
      <h4 className="dimension-provenance__heading">Provenance</h4>
      <p className="dimension-provenance__name">{source.source_name}</p>
      <dl className="dimension-provenance__meta">
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
      </dl>
    </div>
  )
}

/**
 * CE-E06 dimension drill-down (governing specification section 6.7/8.3):
 * `Result` (name, description, score, qualifier, CE-E05 visual indicator)
 * remains visible by default; the analytical trail -- underlying/source
 * data, Evidence, Methodology, Provenance -- sits behind one independent,
 * per-dimension `<details>` (`Investigate {dimension name}`), so the
 * initial profile does not expose all analytical detail simultaneously
 * (section 8.2). Each dimension's disclosure opens/closes on its own; there
 * is no accordion/exclusive-open behavior and no new state -- the native
 * `<details>` element's own `open` attribute is the only state involved
 * (section 13.4).
 *
 * The dimension's own `calculation_method` is shown once, in
 * `DimensionMethodology` -- `SupportingEvidence` is passed `null` for its
 * `calculationMethod` prop here so the same text is not duplicated inside
 * the Evidence disclosure as well (section 12.9 avoiding overload).
 */
function DimensionCard({
  dimension,
  sources,
}: {
  dimension: DimensionProfile
  sources: SourceRef[]
}) {
  const {
    dimension_name: dimensionName,
    description,
    available,
    score,
    normalized,
    primary_measure: primaryMeasure,
    supporting_evidence: supportingEvidence,
    calculation_method: calculationMethod,
    source_id: sourceId,
  } = dimension
  const hasScore = available && score !== null
  const source =
    sourceId === null
      ? null
      : (sources.find((candidate) => candidate.source_id === sourceId) ?? null)

  return (
    <li className="dimension">
      <h3 className="dimension__name">{dimensionName}</h3>
      {description ? (
        <p className="dimension__description">{description}</p>
      ) : null}

      {hasScore ? (
        <p className="dimension__score">
          <span className="dimension__score-value">{formatScore(score)}</span>
          <span className="dimension__score-qualifier">
            {normalized
              ? 'County percentile rank'
              : 'Coverage score — not percentile-normalized in v0.1'}
          </span>
        </p>
      ) : (
        <p className="dimension__score dimension__score--unavailable">
          Not available
        </p>
      )}

      {hasScore ? (
        normalized ? (
          <PercentileIndicator value={score} />
        ) : (
          <CoverageIndicator value={score} />
        )
      ) : null}

      <details className="dimension__disclosure">
        <summary className="dimension__summary">
          Investigate {dimensionName}
        </summary>

        <dl className="dimension__measure">
          <div>
            <dt>Primary measure</dt>
            <dd>{primaryMeasure.display_name}</dd>
          </div>
          <div>
            <dt>Reported value</dt>
            <dd>
              {primaryMeasure.raw_value === null
                ? 'Not reported'
                : primaryMeasure.unit
                  ? `${primaryMeasure.raw_value} ${primaryMeasure.unit}`
                  : `${primaryMeasure.raw_value}`}
            </dd>
          </div>
          {primaryMeasure.normalized_value !== null ? (
            <div>
              <dt>Percentile value</dt>
              <dd>{formatScore(primaryMeasure.normalized_value)}</dd>
            </div>
          ) : null}
          {primaryMeasure.quality_flag ? (
            <div>
              <dt>Data quality</dt>
              <dd>{primaryMeasure.quality_flag}</dd>
            </div>
          ) : null}
        </dl>

        <SupportingEvidence items={supportingEvidence} calculationMethod={null} />

        <DimensionMethodology
          calculationMethod={calculationMethod}
          normalizationMethod={primaryMeasure.normalization_method}
        />

        <DimensionProvenance source={source} />
      </details>
    </li>
  )
}

function CountyProfile({ stateFips }: { stateFips: string }) {
  const explorer = useCountyExplorer()

  if (explorer.status === 'loading') {
    return <Loading label="Loading county profile…" />
  }

  if (explorer.status === 'notfound') {
    return (
      <>
        <NotFound
          title="County not found"
          message="This county is not in the CHIA county universe."
        />
        <BackToStart />
      </>
    )
  }

  if (explorer.status !== 'ready' || explorer.data === null) {
    return (
      <>
        <ErrorState
          message="The county profile could not be loaded."
          onRetry={explorer.retry}
        />
        <BackToStart />
      </>
    )
  }

  const {
    county,
    period,
    access_profile: accessProfile,
    experimental_composite: experimentalComposite,
    methodology,
    provenance,
  } = explorer.data

  return (
    <section className="county-profile" aria-labelledby="county-profile-heading">
      <header className="county-profile__header">
        <Breadcrumb
          stateFips={stateFips}
          stateName={county.state_name}
          countyName={county.county_name}
        />
        <h1 id="county-profile-heading">{county.county_name}</h1>
        <p className="county-profile__state">
          {formatState(county.state_name, county.state_abbr)}
        </p>
        <dl className="county-profile__meta">
          <div>
            <dt>FIPS</dt>
            <dd>{county.county_fips}</dd>
          </div>
          <div>
            <dt>Period</dt>
            <dd>{period.value}</dd>
          </div>
          <div>
            <dt>Data completeness</dt>
            <dd>{formatCompleteness(period.completeness_status)}</dd>
          </div>
        </dl>
      </header>

      <Snapshot accessProfile={accessProfile} />

      <section className="dimensions" aria-labelledby="dimensions-heading">
        <h2 id="dimensions-heading">Access dimensions</h2>
        <p className="dimensions__explanation">{SCORE_EXPLANATION}</p>
        <p className="dimensions__caveat">{GEOGRAPHIC_COVERAGE_CAVEAT}</p>
        <ol className="dimensions__list">
          {DIMENSION_ORDER.map((key) => (
            <DimensionCard
              key={key}
              dimension={accessProfile[key]}
              sources={provenance.sources}
            />
          ))}
        </ol>
      </section>

      <Interpretation explorer={explorer.data} />

      <ExperimentalComposite composite={experimentalComposite} />
      <MethodologyPanel methodology={methodology} accessProfile={accessProfile} />
      <ProvenancePanel
        sources={provenance.sources}
        accessProfile={accessProfile}
      />
    </section>
  )
}

/**
 * County route (`/counties/:countyFips`).
 *
 * Validates the `:countyFips` URL parameter (CE-C02 rules), then renders the
 * assembled Explorer read model for a valid known county: the CE-E04 visual
 * profile (breadcrumb, header, healthcare access snapshot, the four access
 * dimensions with per-dimension evidence, "What Stands Out?" interpretation,
 * experimental composite, and methodology/provenance behind collapsed
 * disclosures). Loading, error, and not-found handling are unchanged from
 * CE-C03/C04. `state_fips` for the breadcrumb comes from the canonical
 * county directory record resolved here (`County`, not the Explorer
 * payload's `CountyBlock`, which has no `state_fips` field).
 */
export function CountyPage() {
  const { countyFips = '' } = useParams<{ countyFips: string }>()
  const directory = useCountyDirectory()

  if (!FIVE_DIGIT_FIPS.test(countyFips)) {
    return (
      <>
        <NotFound
          title="Invalid county FIPS"
          message={`"${countyFips}" is not a five-digit county FIPS code.`}
        />
        <BackToStart />
      </>
    )
  }

  if (directory.status === 'loading') {
    return <Loading label="Loading counties…" />
  }

  if (directory.status === 'error') {
    return (
      <ErrorState
        message="The county list could not be loaded."
        onRetry={directory.retry}
      />
    )
  }

  const county = directory.counties.find(
    (candidate) => candidate.county_fips === countyFips,
  )

  if (!county) {
    return (
      <>
        <NotFound
          title="County not found"
          message={`No county with FIPS ${countyFips} is in the CHIA county universe.`}
        />
        <BackToStart />
      </>
    )
  }

  return (
    <CountyExplorerProvider countyFips={countyFips}>
      <CountyProfile stateFips={county.state_fips} />
    </CountyExplorerProvider>
  )
}
