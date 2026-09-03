/**
 * CE-C01 initial application state: no county is assumed or selected.
 *
 * The county selector (populated from GET /api/v1/counties) and FIPS-based URL
 * state are CE-C02; the county profile and the four dimensions are CE-C03.
 */
export function HomePage() {
  return (
    <section className="home" aria-labelledby="home-heading">
      <h1 id="home-heading">CHIA County Explorer</h1>
      <p>
        Explore county-level healthcare access profiles from the Community Health
        Intelligence Atlas for the v0.1 methodology period.
      </p>
      <p className="home__hint">No county is currently selected.</p>
    </section>
  )
}
