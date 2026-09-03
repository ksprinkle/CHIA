import { useParams } from 'react-router-dom'

/**
 * CE-C01 establishes that a county is addressable by FIPS in the URL
 * (governing specification, section 12). This placeholder only echoes the FIPS
 * path parameter; county selection/URL-state (CE-C02) and the county profile
 * (CE-C03) are delivered in later slices. No data is fetched or rendered here.
 */
export function CountyRoutePlaceholder() {
  const { countyFips } = useParams<{ countyFips: string }>()

  return (
    <section className="county-route" aria-labelledby="county-route-heading">
      <h1 id="county-route-heading">County route</h1>
      <p>
        This view is addressable by county FIPS
        {countyFips ? <code> {countyFips}</code> : null}.
      </p>
      <p className="home__hint">
        The county profile and dimension views are delivered in a later slice.
      </p>
    </section>
  )
}
