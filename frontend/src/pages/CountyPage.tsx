import { Link, useParams } from 'react-router-dom'

import { ErrorState } from '../components/ErrorState'
import { Loading } from '../components/Loading'
import { NotFound } from '../components/NotFound'
import { useCountyDirectory } from '../lib/countyDirectory'

const FIVE_DIGIT_FIPS = /^\d{5}$/

function BackToStart() {
  return (
    <p className="county-page__back">
      <Link to="/">Return to the start</Link>
    </p>
  )
}

/**
 * CE-C02 county route.
 *
 * Validates the `:countyFips` URL parameter and, for a valid known county,
 * renders a minimal acknowledgement built only from `GET /api/v1/counties`
 * data (`county_name` + `county_fips`, verbatim) plus a placeholder for the
 * county profile. It does NOT call `/explorer` and renders no dimensions,
 * scores, composite, methodology, provenance, or interpretation (CE-C03+).
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
    <section className="county-page" aria-labelledby="county-page-heading">
      <h1 id="county-page-heading">
        {county.county_name}{' '}
        <span className="county-page__fips">({county.county_fips})</span>
      </h1>
      <p className="home__hint">County profile — CE-C03</p>
    </section>
  )
}
