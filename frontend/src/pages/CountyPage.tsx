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
import type { DimensionProfile } from '../lib/types'

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

/**
 * Presentation-only rounding of an API-provided percentile score to the nearest
 * whole number (approved decision D4). The underlying value is never
 * recalculated or re-derived. Primary measures are not rounded: the API does
 * not define a display precision for them, so their `raw_value` is rendered as
 * provided.
 */
function formatScore(score: number): string {
  return String(Math.round(score))
}

function DimensionCard({ dimension }: { dimension: DimensionProfile }) {
  const {
    dimension_name: dimensionName,
    description,
    available,
    score,
    normalized,
    primary_measure: primaryMeasure,
    supporting_evidence: supportingEvidence,
    calculation_method: calculationMethod,
  } = dimension
  const hasScore = available && score !== null

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

      <SupportingEvidence
        items={supportingEvidence}
        calculationMethod={calculationMethod}
      />
    </li>
  )
}

function CountyProfile() {
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

      <section className="dimensions" aria-labelledby="dimensions-heading">
        <h2 id="dimensions-heading">Access dimensions</h2>
        <p className="dimensions__explanation">{SCORE_EXPLANATION}</p>
        <p className="dimensions__caveat">{GEOGRAPHIC_COVERAGE_CAVEAT}</p>
        <ol className="dimensions__list">
          {DIMENSION_ORDER.map((key) => (
            <DimensionCard key={key} dimension={accessProfile[key]} />
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
 * County route.
 *
 * Validates the `:countyFips` URL parameter (CE-C02 rules), then renders the
 * assembled Explorer read model for a valid known county from the single
 * shared `useCountyExplorer` payload: the county profile header and the four
 * access dimensions (CE-C03); per-dimension supporting evidence, the
 * experimental composite, methodology, and provenance (CE-C04); and
 * deterministic, application-generated interpretation (CE-C05). Loading,
 * error, not-found, and stale-data handling are unchanged from CE-C03/C04 --
 * CE-C05 introduces no new provider state.
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
      <CountyProfile />
    </CountyExplorerProvider>
  )
}
