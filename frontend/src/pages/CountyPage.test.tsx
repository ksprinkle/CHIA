import { act, fireEvent, screen, waitFor, within } from '@testing-library/react'

import {
  makeCounties,
  makeExplorer,
  renderApp,
  stubApi,
  stubCountiesFetch,
} from '../test/harness'

/**
 * Forbidden evaluative / comparative / causal language for CE-C05
 * interpretation (governing specification section 14 boundary, approved D6).
 * "high"/"low" are checked as bare words only -- "highest-scoring" and
 * "lowest-scoring" are the approved, required phrasing and must not trip
 * these patterns (a `\b`-bounded match on "high"/"low" does not match inside
 * "highest"/"lowest").
 */
const FORBIDDEN_INTERPRETATION_LANGUAGE = [
  /\bstrongest\b/i,
  /\bweakest\b/i,
  /\bbest\b/i,
  /\bworst\b/i,
  /\bpoor\b/i,
  /\bgood\b/i,
  /\bhigh\b/i,
  /\blow\b/i,
  /\bconcerning\b/i,
  /\bvulnerable\b/i,
  /unusually (?:high|low)/i,
  /\bquartile/i,
  /\bband(?:s|ing)?\b/i,
  /compared? (?:to|with) (?:other|the) counties/i,
  /\brank(?:s|ed|ing)? (?:relative to|among|against) (?:other )?counties/i,
  /\brisk\b/i,
  /\bpredict/i,
  /\brecommend/i,
]

afterEach(() => {
  vi.unstubAllGlobals()
  vi.restoreAllMocks()
})

function stubValidCounty() {
  return stubApi({
    counties: makeCounties(['01001', '01003']),
    explorer: (fips) => makeExplorer(fips),
  })
}

describe('CountyPage (CE-C03 county profile)', () => {
  it('requests the Explorer read model for the selected FIPS only', async () => {
    const fetchMock = stubValidCounty()
    renderApp(['/counties/01001'])

    await screen.findByRole('heading', { level: 1 })

    const explorerCalls = fetchMock.mock.calls
      .map((call) => String(call[0]))
      .filter((url) => url.includes('/explorer'))
    expect(explorerCalls).toEqual(['/api/v1/counties/01001/explorer'])
  })

  it('renders the county profile header from the API payload', async () => {
    stubApi({
      counties: makeCounties(['01001', '01003']),
      explorer: (fips) =>
        makeExplorer(fips, {
          county: {
            county_name: 'Autauga County',
            state_name: 'Alabama',
            state_abbr: 'AL',
          },
          period: { value: 'v0.1', completeness_status: 'complete' },
        }),
    })
    renderApp(['/counties/01001'])

    const heading = await screen.findByRole('heading', {
      level: 1,
      name: /autauga county/i,
    })
    // Scope to the profile <header>: CE-C04's methodology panel legitimately
    // also renders "v0.1" (methodology version), so the period assertion is
    // pinned to the header where it belongs.
    const header = heading.closest('header') as HTMLElement
    expect(within(header).getByText('Alabama (AL)')).toBeInTheDocument()
    expect(within(header).getByText('01001')).toBeInTheDocument()
    expect(within(header).getByText('v0.1')).toBeInTheDocument()
    expect(within(header).getByText('Complete')).toBeInTheDocument()
  })

  it('renders the four dimensions in canonical order with descriptions', async () => {
    stubValidCounty()
    renderApp(['/counties/01001'])
    await screen.findByRole('heading', { level: 1 })

    const dimensionHeadings = screen
      .getAllByRole('heading', { level: 3 })
      .map((heading) => heading.textContent)
    expect(dimensionHeadings).toEqual([
      'Primary Care Access',
      'Dental Access',
      'Mental Health Access',
      'MUA/P Access',
    ])
    expect(
      screen.getByText('Primary Care Access description.'),
    ).toBeInTheDocument()
    expect(
      screen.getByText('Primary Care Access primary measure'),
    ).toBeInTheDocument()
  })

  it('shows API scores rounded for display with the percentile qualifier', async () => {
    stubApi({
      counties: makeCounties(['01001']),
      explorer: (fips) =>
        makeExplorer(fips, {
          dimensions: {
            primary_care: {
              score: 88.75776397515529,
              normalized: true,
              primary_measure: { normalized_value: 12.4 },
            },
          },
        }),
    })
    renderApp(['/counties/01001'])
    await screen.findByRole('heading', { level: 1 })

    // CE-E04's snapshot section legitimately also renders the rounded score,
    // so these are scoped to the dimensions detail region specifically.
    const dimensions = screen.getByRole('region', { name: /access dimensions/i })
    // The headline Result rounds for display (88.757... -> 89); nothing is
    // recalculated.
    expect(
      within(dimensions).getByText('89', { selector: '.dimension__score-value' }),
    ).toBeInTheDocument()
    expect(within(dimensions).getAllByText('County percentile rank')).toHaveLength(3)
    // CE-E11: the drill-down shows the exact, unrounded pipeline values.
    const primaryCareCard = within(dimensions)
      .getByRole('heading', { level: 3, name: 'Primary Care Access' })
      .closest('li') as HTMLElement
    expect(within(primaryCareCard).getByText('12.4')).toBeInTheDocument()
    expect(
      within(primaryCareCard).getByText('88.75776397515529'),
    ).toBeInTheDocument()
  })

  it('qualifies the MUA/P score as not percentile-normalized', async () => {
    stubValidCounty()
    renderApp(['/counties/01001'])
    await screen.findByRole('heading', { level: 1 })

    expect(
      screen.getByText(/not percentile-normalized in v0\.1/i),
    ).toBeInTheDocument()
  })

  it('shows the fixed score explanation and the geographic-coverage caveat', async () => {
    stubValidCounty()
    renderApp(['/counties/01001'])
    await screen.findByRole('heading', { level: 1 })

    expect(
      screen.getByText(
        /percentile values relative to the CHIA county universe/i,
      ),
    ).toBeInTheDocument()
    expect(
      screen.getByText(/greater geographic access burden/i),
    ).toBeInTheDocument()
    expect(
      screen.getByText(
        /not the percentage of residents who lack access to care/i,
      ),
    ).toBeInTheDocument()
  })

  it('marks an unavailable dimension without hiding the other three', async () => {
    stubApi({
      counties: makeCounties(['01001']),
      explorer: (fips) =>
        makeExplorer(fips, {
          dimensions: {
            dental: { available: false, score: null, score_status: null },
          },
          period: { completeness_status: 'partial' },
        }),
    })
    renderApp(['/counties/01001'])
    await screen.findByRole('heading', { level: 1 })

    // CE-E04's snapshot section legitimately also renders "Not available"
    // for the same unavailable dimension, so this is scoped to the
    // dimensions detail region specifically.
    const dimensions = screen.getByRole('region', { name: /access dimensions/i })
    expect(within(dimensions).getByText('Not available')).toBeInTheDocument()
    expect(screen.getAllByRole('heading', { level: 3 })).toHaveLength(4)
    expect(
      screen.getByRole('heading', { level: 3, name: /dental access/i }),
    ).toBeInTheDocument()
    expect(screen.getByText('Partial')).toBeInTheDocument()
  })

  it('shows an explicit loading state before the Explorer response resolves', async () => {
    const fetchMock = vi.fn((...args: unknown[]) => {
      if (String(args[0]).includes('/explorer')) {
        return new Promise<Response>(() => {})
      }
      return Promise.resolve({
        ok: true,
        status: 200,
        json: async () => makeCounties(['01001']),
      } as Response)
    })
    vi.stubGlobal('fetch', fetchMock)
    renderApp(['/counties/01001'])

    await waitFor(() =>
      expect(screen.getByRole('status')).toHaveTextContent(
        /loading county profile/i,
      ),
    )
  })

  it('shows an error state with retry on a 503', async () => {
    stubApi({ counties: makeCounties(['01001']), explorer: () => 503 })
    renderApp(['/counties/01001'])

    const alert = await screen.findByRole('alert')
    expect(alert).toHaveTextContent(/could not be loaded/i)
    expect(
      screen.getByRole('button', { name: /try again/i }),
    ).toBeInTheDocument()
  })

  it('shows an error state on a network failure', async () => {
    stubApi({
      counties: makeCounties(['01001']),
      explorer: () => new TypeError('network down'),
    })
    renderApp(['/counties/01001'])

    expect(await screen.findByRole('alert')).toHaveTextContent(
      /could not be loaded/i,
    )
  })

  it('retries the Explorer request when "Try again" is used', async () => {
    let calls = 0
    const fetchMock = stubApi({
      counties: makeCounties(['01001']),
      explorer: (fips) => {
        calls += 1
        return calls === 1 ? 503 : makeExplorer(fips)
      },
    })
    renderApp(['/counties/01001'])

    const button = await screen.findByRole('button', { name: /try again/i })
    fireEvent.click(button)

    await screen.findByRole('heading', { level: 1 })
    expect(
      fetchMock.mock.calls
        .map((call) => String(call[0]))
        .filter((url) => url.includes('/explorer')),
    ).toHaveLength(2)
  })

  it('distinguishes a malformed FIPS and issues no Explorer request', async () => {
    const fetchMock = stubApi({ counties: makeCounties(['01001']) })
    renderApp(['/counties/abcde'])

    expect(
      await screen.findByText(/not a five-digit county FIPS code/i),
    ).toBeInTheDocument()
    expect(
      screen.getByRole('link', { name: /return to the start/i }),
    ).toBeInTheDocument()
    expect(
      fetchMock.mock.calls
        .map((call) => String(call[0]))
        .some((url) => url.includes('/explorer')),
    ).toBe(false)
  })

  it('distinguishes an unknown well-formed FIPS (kept in place)', async () => {
    stubApi({ counties: makeCounties(['01001', '01003']) })
    const { router } = renderApp(['/counties/99999'])

    expect(
      await screen.findByText(/no county with fips 99999/i),
    ).toBeInTheDocument()
    expect(
      screen.getByRole('link', { name: /return to the start/i }),
    ).toBeInTheDocument()
    expect(router.state.location.pathname).toBe('/counties/99999')
  })

  it('surfaces the county-list error before requesting a profile', async () => {
    stubCountiesFetch(new TypeError('network down'))
    renderApp(['/counties/01001'])

    await waitFor(() =>
      expect(screen.getAllByRole('alert').length).toBeGreaterThan(0),
    )
  })

  it('does not render CE-C06 dialog content', async () => {
    stubValidCounty()
    renderApp(['/counties/01001'])
    await screen.findByRole('heading', { level: 1 })

    // CE-C05's interpretation section legitimately renders "Interpretation",
    // "highest"/"lowest", etc. (see the CE-C05 describe block below for the
    // precise forbidden-language boundary). CE-C04 disclosures are native
    // <details>, never a modal/dialog widget -- that boundary still applies.
    expect(screen.queryByRole('dialog')).toBeNull()
  })

  it('does not display stale prior-county data after the county changes', async () => {
    stubApi({
      counties: makeCounties(['01001', '01003']),
      explorer: (fips) =>
        makeExplorer(fips, { county: { county_name: `County-${fips}` } }),
    })
    const { router } = renderApp(['/counties/01001'])
    await screen.findByRole('heading', { level: 1, name: /county-01001/i })

    await act(async () => {
      await router.navigate('/counties/01003')
    })

    await waitFor(() =>
      expect(screen.queryByText(/county-01001/i)).toBeNull(),
    )
    expect(
      await screen.findByRole('heading', { level: 1, name: /county-01003/i }),
    ).toBeInTheDocument()
  })

  it('has a single h1 and labelled profile / dimensions regions', async () => {
    stubValidCounty()
    renderApp(['/counties/01001'])
    await screen.findByRole('heading', { level: 1 })

    expect(screen.getAllByRole('heading', { level: 1 })).toHaveLength(1)
    expect(
      screen.getByRole('region', { name: /access dimensions/i }),
    ).toBeInTheDocument()
  })
})

describe('CountyPage (CE-C04 evidence / methodology / composite)', () => {
  it('renders the whole page from a single shared Explorer request', async () => {
    const fetchMock = stubValidCounty()
    renderApp(['/counties/01001'])
    await screen.findByRole('heading', { level: 2, name: /experimental composite/i })

    const explorerCalls = fetchMock.mock.calls
      .map((call) => String(call[0]))
      .filter((url) => url.includes('/explorer'))
    expect(explorerCalls).toEqual(['/api/v1/counties/01001/explorer'])
  })

  it('renders supporting evidence for every dimension, incl. MUA/P six items', async () => {
    stubValidCounty()
    renderApp(['/counties/01001'])
    await screen.findByRole('heading', { level: 1 })

    // one <summary> disclosure per dimension
    expect(screen.getAllByText('Supporting evidence')).toHaveLength(4)

    const muaEvidence = [
      'MUA/P Mean Score',
      'MUA/P Maximum Score',
      'MUA/P Feature Count',
      'MUA Feature Count',
      'MUP Feature Count',
      'MUA/P Unique Source Count',
    ]
    for (const name of muaEvidence) {
      expect(screen.getByText(name)).toBeInTheDocument()
    }
    expect(screen.getByText('Primary Care HPSA Area-Weighted Score')).toBeInTheDocument()
  })

  it('renders evidence raw values without rounding', async () => {
    stubApi({
      counties: makeCounties(['01001']),
      explorer: (fips) =>
        makeExplorer(fips, {
          dimensions: {
            primary_care: {
              supporting_evidence: [
                {
                  variable_id: 'PC_SUP_1',
                  display_name: 'PC Area-Weighted Score',
                  unit: 'score',
                  direction: 'higher_burden',
                  raw_value: 14.99984814229961,
                  quality_flag: 'source_validated',
                },
              ],
            },
          },
        }),
    })
    renderApp(['/counties/01001'])
    await screen.findByRole('heading', { level: 1 })

    expect(
      screen.getByText(/14\.99984814229961 score/),
    ).toBeInTheDocument()
  })

  it('renders a native <details> disclosure (not a modal) that toggles open', async () => {
    stubValidCounty()
    renderApp(['/counties/01001'])
    await screen.findByRole('heading', { level: 1 })

    const summary = screen.getAllByText('Supporting evidence')[0]
    const details = summary.closest('details') as HTMLDetailsElement
    expect(details).toBeInTheDocument()
    expect(details.open).toBe(false)
    fireEvent.click(summary)
    expect(details.open).toBe(true)
    expect(screen.queryByRole('dialog')).toBeNull()
  })

  it('renders methodology fields and per-dimension calculation methods', async () => {
    stubApi({
      counties: makeCounties(['01001']),
      explorer: (fips) =>
        makeExplorer(fips, {
          dimensions: {
            primary_care: {
              calculation_method: 'PC calc: percentile rank of the primary variable.',
            },
          },
        }),
    })
    renderApp(['/counties/01001'])
    const methodology = await screen.findByRole('region', { name: /methodology/i })

    expect(within(methodology).getByText('county_percentile_rank_average')).toBeInTheDocument()
    expect(within(methodology).getByText('prototype')).toBeInTheDocument()
    expect(
      within(methodology).getByText(
        /Four-domain county-level healthcare access profile/i,
      ),
    ).toBeInTheDocument()
    expect(
      within(methodology).getByText('PC calc: percentile rank of the primary variable.'),
    ).toBeInTheDocument()
    expect(
      within(methodology).getByText('Mental Health Access calculation method.'),
    ).toBeInTheDocument()
  })

  it('renders all four provenance sources with the CE-E12B source vintage and artifact metadata', async () => {
    stubValidCounty()
    renderApp(['/counties/01001'])
    const sources = await screen.findByRole('region', { name: /sources/i })

    for (const name of ['Primary Care HPSA', 'Dental HPSA', 'Mental Health HPSA', 'MUA/P']) {
      expect(within(sources).getByText(name)).toBeInTheDocument()
    }
    expect(within(sources).getAllByText('HRSA')).toHaveLength(4)
    expect(within(sources).getByText('Dental HPSA Spatial Coverage')).toBeInTheDocument()
    // dimension-to-source association via source_id
    expect(within(sources).getByText('Primary Care Access')).toBeInTheDocument()

    // CE-E12B: source-data vintage, retrieval location + date, and the exact
    // build-input artifact (filename + SHA-256) for every source.
    expect(
      within(sources).getAllByText('HRSA Data Warehouse snapshot 2026-08-29'),
    ).toHaveLength(4)
    expect(within(sources).getAllByText('2026-08-29')).toHaveLength(4)
    const links = within(sources).getAllByRole('link')
    expect(links).toHaveLength(4)
    for (const link of links) {
      expect(link).toHaveAttribute('href', 'https://data.hrsa.gov/data/download')
    }
    expect(
      within(sources).getByText(
        'CHIA_Primary_Care_HPSA_Spatial_Coverage_Validated_FINAL.xlsx',
      ),
    ).toBeInTheDocument()
    expect(
      within(sources).getByText(
        '709e9ed6070f71e466b65b0928d1dbe23d3dd685ecfb81d4cb1cc0ee637c2d93',
      ),
    ).toBeInTheDocument()
  })

  it('renders the experimental composite value, label and status', async () => {
    stubValidCounty()
    renderApp(['/counties/01001'])
    const composite = await screen.findByRole('region', {
      name: /experimental composite/i,
    })

    // 59.75 -> 60 (whole-number display rounding, not recalculated)
    expect(within(composite).getByText('60')).toBeInTheDocument()
    expect(within(composite).getByText('Experimental / Provisional')).toBeInTheDocument()
    expect(within(composite).getByText(/experimental_provisional/i)).toBeInTheDocument()
    expect(
      within(composite).getByText(
        /equal-weight combination of the four dimension access scores/i,
      ),
    ).toBeInTheDocument()
    expect(
      within(composite).getByText(/not a validated measure/i),
    ).toBeInTheDocument()
  })

  it('places the composite after the four dimensions', async () => {
    stubValidCounty()
    renderApp(['/counties/01001'])
    await screen.findByRole('heading', { level: 1 })

    const dimensions = screen.getByRole('region', { name: /access dimensions/i })
    const composite = screen.getByRole('region', { name: /experimental composite/i })
    expect(
      dimensions.compareDocumentPosition(composite) &
        Node.DOCUMENT_POSITION_FOLLOWING,
    ).toBeTruthy()
    // not a fifth item in the dimensions list
    expect(within(dimensions).queryByText(/experimental composite/i)).toBeNull()
  })

  it('does not recalculate the composite (renders the persisted value)', async () => {
    stubApi({
      counties: makeCounties(['01001']),
      explorer: (fips) => {
        // Dimension scores that would average to 50; persisted composite is 12.3.
        const payload = makeExplorer(fips, {
          dimensions: {
            primary_care: { score: 40, primary_measure: { normalized_value: 40 } },
            dental: { score: 60, primary_measure: { normalized_value: 60 } },
            mental_health: { score: 40, primary_measure: { normalized_value: 40 } },
            mua_p: { score: 60 },
          },
        })
        return {
          ...payload,
          experimental_composite: {
            ...payload.experimental_composite,
            composite_value: 12.3,
          },
        }
      },
    })
    renderApp(['/counties/01001'])
    const composite = await screen.findByRole('region', {
      name: /experimental composite/i,
    })

    expect(within(composite).getByText('12')).toBeInTheDocument()
    expect(within(composite).queryByText('50')).toBeNull()
  })

  it('shows an unavailable composite with named missing dimensions and no number', async () => {
    stubApi({
      counties: makeCounties(['01001']),
      explorer: (fips) => {
        const payload = makeExplorer(fips)
        return {
          ...payload,
          experimental_composite: {
            label: 'Experimental / Provisional',
            composite_value: null,
            status: 'experimental_provisional',
            missing_dimensions: ['DENTAL'],
          },
        }
      },
    })
    renderApp(['/counties/01001'])
    const composite = await screen.findByRole('region', {
      name: /experimental composite/i,
    })

    expect(within(composite).getByText(/not available/i)).toBeInTheDocument()
    expect(within(composite).getByText(/DENTAL/)).toBeInTheDocument()
    expect(within(composite).getByText('Experimental / Provisional')).toBeInTheDocument()
    expect(within(composite).queryByText(/^\d+$/)).toBeNull()
  })

  it('omits a dimension evidence block when the evidence list is empty', async () => {
    stubApi({
      counties: makeCounties(['01001']),
      explorer: (fips) =>
        makeExplorer(fips, {
          dimensions: {
            dental: { supporting_evidence: [], calculation_method: null },
          },
        }),
    })
    renderApp(['/counties/01001'])
    await screen.findByRole('heading', { level: 1 })

    // 3 disclosures instead of 4 (dental has neither evidence nor a method)
    expect(screen.getAllByText('Supporting evidence')).toHaveLength(3)
    // dental itself still renders
    expect(
      screen.getByRole('heading', { level: 3, name: /dental access/i }),
    ).toBeInTheDocument()
  })

  it('keeps all CE-C03 content intact alongside the CE-C04 additions', async () => {
    stubApi({
      counties: makeCounties(['01001']),
      explorer: (fips) =>
        makeExplorer(fips, {
          county: { county_name: 'Autauga County', state_name: 'Alabama', state_abbr: 'AL' },
        }),
    })
    renderApp(['/counties/01001'])
    await screen.findByRole('heading', { level: 1, name: /autauga county/i })

    expect(screen.getByText('Alabama (AL)')).toBeInTheDocument()
    expect(screen.getByText('01001')).toBeInTheDocument()
    expect(screen.getByText('Complete')).toBeInTheDocument()
    expect(
      screen.getAllByRole('heading', { level: 3 }).map((h) => h.textContent),
    ).toEqual([
      'Primary Care Access',
      'Dental Access',
      'Mental Health Access',
      'MUA/P Access',
    ])
    expect(
      screen.getByText(/percentile values relative to the CHIA county universe/i),
    ).toBeInTheDocument()
    expect(
      screen.getByText(/not the percentage of residents who lack access to care/i),
    ).toBeInTheDocument()
    expect(
      screen.getByText(/not percentile-normalized in v0\.1/i),
    ).toBeInTheDocument()
    expect(screen.getAllByRole('heading', { level: 1 })).toHaveLength(1)
  })
})

describe('CountyPage (CE-C05 interpretation)', () => {
  it('renders completeness, highest/lowest, gap, and composite-availability sentences', async () => {
    stubValidCounty()
    renderApp(['/counties/01001'])
    const interpretation = await screen.findByRole('region', {
      name: /interpretation/i,
    })

    // Default fixture: primary_care 88, dental 29, mental_health 23, mua_p 99.
    expect(
      within(interpretation).getByText(/4 of 4 dimensions/i),
    ).toBeInTheDocument()
    expect(
      within(interpretation).getByText(/MUA\/P Access.*highest-scoring/i),
    ).toBeInTheDocument()
    expect(
      within(interpretation).getByText(/Mental Health Access.*lowest-scoring/i),
    ).toBeInTheDocument()
    expect(
      within(interpretation).getByText(/difference between.*is 76 points/i),
    ).toBeInTheDocument()
    expect(
      within(interpretation).getByText(
        /experimental composite is available for this county/i,
      ),
    ).toBeInTheDocument()
  })

  it('includes MUA/P in the comparison with a non-percentile qualifier, never calling it a percentile', async () => {
    stubApi({
      counties: makeCounties(['01001']),
      explorer: (fips) =>
        makeExplorer(fips, {
          dimensions: {
            primary_care: { score: 10 },
            dental: { score: 20 },
            mental_health: { score: 30 },
            mua_p: { score: 95, normalized: false },
          },
        }),
    })
    renderApp(['/counties/01001'])
    const interpretation = await screen.findByRole('region', {
      name: /interpretation/i,
    })

    expect(
      within(interpretation).getByText(/MUA\/P Access.*highest-scoring/i),
    ).toBeInTheDocument()
    expect(
      within(interpretation).getByText(
        /MUA\/P Access.s score is a coverage value, not a percentile rank/i,
      ),
    ).toBeInTheDocument()
    // The only mention of "percentile" is the qualifier's negation above --
    // MUA/P's score is never asserted to *be* a percentile.
    expect(
      within(interpretation).queryByText(/MUA\/P Access.s (?:score )?is a percentile/i),
    ).toBeNull()
  })

  it('names all dimensions tied for the highest score', async () => {
    stubApi({
      counties: makeCounties(['01001']),
      explorer: (fips) =>
        makeExplorer(fips, {
          dimensions: {
            primary_care: { score: 80 },
            dental: { score: 80 },
            mental_health: { score: 20 },
            mua_p: { score: 50, normalized: false },
          },
        }),
    })
    renderApp(['/counties/01001'])
    const interpretation = await screen.findByRole('region', {
      name: /interpretation/i,
    })

    expect(
      within(interpretation).getByText(
        /Primary Care Access and Dental Access are jointly this county's highest-scoring dimensions/i,
      ),
    ).toBeInTheDocument()
    expect(
      within(interpretation).getByText(/Mental Health Access.*lowest-scoring/i),
    ).toBeInTheDocument()
  })

  it('names all dimensions tied for the lowest score', async () => {
    stubApi({
      counties: makeCounties(['01001']),
      explorer: (fips) =>
        makeExplorer(fips, {
          dimensions: {
            primary_care: { score: 90 },
            dental: { score: 10 },
            mental_health: { score: 10 },
            mua_p: { score: 50, normalized: false },
          },
        }),
    })
    renderApp(['/counties/01001'])
    const interpretation = await screen.findByRole('region', {
      name: /interpretation/i,
    })

    expect(
      within(interpretation).getByText(
        /Dental Access and Mental Health Access are jointly this county's lowest-scoring dimensions/i,
      ),
    ).toBeInTheDocument()
    expect(
      within(interpretation).getByText(/Primary Care Access.*highest-scoring/i),
    ).toBeInTheDocument()
  })

  it('shows the insufficient-data fallback with fewer than two available scores', async () => {
    stubApi({
      counties: makeCounties(['01001']),
      explorer: (fips) =>
        makeExplorer(fips, {
          dimensions: {
            dental: { available: false, score: null },
            mental_health: { available: false, score: null },
            mua_p: { available: false, score: null },
          },
        }),
    })
    renderApp(['/counties/01001'])
    const interpretation = await screen.findByRole('region', {
      name: /interpretation/i,
    })

    expect(
      within(interpretation).getByText(/1 of 4 dimensions/i),
    ).toBeInTheDocument()
    expect(
      within(interpretation).getByText(
        /not enough available dimension data to compare across dimensions for this county/i,
      ),
    ).toBeInTheDocument()
    expect(
      within(interpretation).queryByText(/highest-scoring/i),
    ).toBeNull()
    expect(within(interpretation).queryByText(/lowest-scoring/i)).toBeNull()
    expect(
      within(interpretation).queryByText(/difference between/i),
    ).toBeNull()
  })

  it('shows composite unavailability naming the API missing_dimensions verbatim', async () => {
    stubApi({
      counties: makeCounties(['01001']),
      explorer: (fips) => {
        const payload = makeExplorer(fips)
        return {
          ...payload,
          experimental_composite: {
            ...payload.experimental_composite,
            composite_value: null,
            missing_dimensions: ['DENTAL'],
          },
        }
      },
    })
    renderApp(['/counties/01001'])
    const interpretation = await screen.findByRole('region', {
      name: /interpretation/i,
    })

    expect(
      within(interpretation).getByText(
        /experimental composite is not available because DENTAL is missing/i,
      ),
    ).toBeInTheDocument()
  })

  it('does not use forbidden evaluative, comparative, or causal language', async () => {
    stubApi({
      counties: makeCounties(['01001']),
      explorer: (fips) =>
        makeExplorer(fips, {
          dimensions: {
            primary_care: { score: 95 },
            dental: { score: 95 },
            mental_health: { score: 5 },
            mua_p: { score: 5, normalized: false },
          },
        }),
    })
    renderApp(['/counties/01001'])
    const interpretation = await screen.findByRole('region', {
      name: /interpretation/i,
    })
    const text = interpretation.textContent ?? ''

    for (const pattern of FORBIDDEN_INTERPRETATION_LANGUAGE) {
      expect(text).not.toMatch(pattern)
    }
  })

  it('places the interpretation section after the dimensions and before the composite', async () => {
    stubValidCounty()
    renderApp(['/counties/01001'])
    await screen.findByRole('heading', { level: 1 })

    const dimensions = screen.getByRole('region', { name: /access dimensions/i })
    const interpretation = screen.getByRole('region', { name: /interpretation/i })
    const composite = screen.getByRole('region', { name: /experimental composite/i })

    expect(
      dimensions.compareDocumentPosition(interpretation) &
        Node.DOCUMENT_POSITION_FOLLOWING,
    ).toBeTruthy()
    expect(
      interpretation.compareDocumentPosition(composite) &
        Node.DOCUMENT_POSITION_FOLLOWING,
    ).toBeTruthy()
  })

  it('is a single labelled region with one h2', async () => {
    stubValidCounty()
    renderApp(['/counties/01001'])
    const interpretation = await screen.findByRole('region', {
      name: /interpretation/i,
    })

    expect(
      within(interpretation).getByRole('heading', { level: 2, name: /interpretation/i }),
    ).toBeInTheDocument()
    expect(screen.queryByRole('dialog')).toBeNull()
  })

  it('keeps CE-C03 and CE-C04 content intact alongside the interpretation section', async () => {
    stubValidCounty()
    renderApp(['/counties/01001'])
    await screen.findByRole('region', { name: /interpretation/i })

    // C03
    expect(
      screen.getAllByRole('heading', { level: 3 }).map((h) => h.textContent),
    ).toEqual([
      'Primary Care Access',
      'Dental Access',
      'Mental Health Access',
      'MUA/P Access',
    ])
    // C04
    expect(screen.getAllByText('Supporting evidence')).toHaveLength(4)
    expect(
      screen.getByRole('region', { name: /experimental composite/i }),
    ).toBeInTheDocument()
    expect(
      screen.getByRole('region', { name: /methodology/i }),
    ).toBeInTheDocument()
    expect(screen.getByRole('region', { name: /sources/i })).toBeInTheDocument()
  })
})

describe('CountyPage (CE-E04 visual profile)', () => {
  it('renders the breadcrumb as United States > State > County', async () => {
    stubApi({
      counties: makeCounties(['01001']),
      explorer: (fips) =>
        makeExplorer(fips, {
          county: {
            county_name: 'Autauga County',
            state_name: 'Alabama',
            state_abbr: 'AL',
          },
        }),
    })
    renderApp(['/counties/01001'])
    await screen.findByRole('heading', { level: 1, name: /autauga county/i })

    const breadcrumb = screen.getByRole('navigation', { name: /breadcrumb/i })
    expect(within(breadcrumb).getByRole('link', { name: /^united states$/i })).toHaveAttribute(
      'href',
      '/',
    )
    expect(within(breadcrumb).getByRole('link', { name: /^alabama$/i })).toHaveAttribute(
      'href',
      '/states/01',
    )
    // County is the current-page segment: present, but not a link.
    expect(
      within(breadcrumb).getByText('Autauga County', { selector: '[aria-current="page"]' }),
    ).toBeInTheDocument()
    expect(within(breadcrumb).queryByRole('link', { name: /autauga county/i })).toBeNull()
  })

  it('links the state breadcrumb segment to the correct /states/{state_fips} for a second, differently-shaped entity (DC)', async () => {
    stubApi({
      counties: makeCounties(['11001']),
      explorer: (fips) =>
        makeExplorer(fips, {
          county: {
            county_name: 'District of Columbia',
            state_name: 'District of Columbia',
            state_abbr: 'DC',
          },
        }),
    })
    renderApp(['/counties/11001'])
    await screen.findByRole('heading', { level: 1, name: /district of columbia/i })

    const breadcrumb = screen.getByRole('navigation', { name: /breadcrumb/i })
    expect(within(breadcrumb).getByRole('link', { name: /^united states$/i })).toHaveAttribute(
      'href',
      '/',
    )
    expect(
      within(breadcrumb).getByRole('link', { name: /^district of columbia$/i }),
    ).toHaveAttribute('href', '/states/11')
    expect(
      within(breadcrumb).getByText('District of Columbia', {
        selector: '[aria-current="page"]',
      }),
    ).toBeInTheDocument()
  })

  it('renders a scannable healthcare access snapshot using the existing dimension values', async () => {
    stubValidCounty()
    renderApp(['/counties/01001'])
    await screen.findByRole('heading', { level: 1 })

    const snapshot = screen.getByRole('region', { name: /healthcare access snapshot/i })
    for (const name of [
      'Primary Care Access',
      'Dental Access',
      'Mental Health Access',
      'MUA/P Access',
    ]) {
      expect(within(snapshot).getByText(name)).toBeInTheDocument()
    }
    // Default fixture: primary_care 88, dental 29, mental_health 23 (all
    // percentile), mua_p 99 (coverage, not percentile) -- see makeExplorer.
    expect(within(snapshot).getByText('88')).toBeInTheDocument()
    expect(within(snapshot).getAllByText('percentile')).toHaveLength(3)
    expect(within(snapshot).getByText('% coverage')).toBeInTheDocument()
    // Snapshot precedes the detailed dimensions section (visual summary
    // before the four-dimension detail, per the approved reading order).
    const dimensions = screen.getByRole('region', { name: /access dimensions/i })
    expect(
      snapshot.compareDocumentPosition(dimensions) & Node.DOCUMENT_POSITION_FOLLOWING,
    ).toBeTruthy()
  })

  it('the snapshot marks an unavailable dimension distinctly from a genuine zero', async () => {
    stubApi({
      counties: makeCounties(['01001']),
      explorer: (fips) =>
        makeExplorer(fips, {
          dimensions: {
            primary_care: { available: true, score: 0, primary_measure: { normalized_value: 0 } },
            dental: { available: false, score: null, score_status: null },
          },
        }),
    })
    renderApp(['/counties/01001'])
    await screen.findByRole('heading', { level: 1 })

    const snapshot = screen.getByRole('region', { name: /healthcare access snapshot/i })
    // Genuine zero is a real, displayed value -- not "Not available".
    expect(within(snapshot).getByText('0')).toBeInTheDocument()
    expect(within(snapshot).getAllByText('Not available')).toHaveLength(1)
  })

  it('methodology is available but collapsed by default, and can be expanded', async () => {
    stubValidCounty()
    renderApp(['/counties/01001'])
    const methodology = await screen.findByRole('region', { name: /methodology/i })

    const summary = within(methodology).getByText('View methodology')
    const details = summary.closest('details') as HTMLDetailsElement
    expect(details).toBeInTheDocument()
    expect(details.open).toBe(false)
    // Content still exists in the document even while collapsed.
    expect(within(methodology).getByText('county_percentile_rank_average')).toBeInTheDocument()

    fireEvent.click(summary)
    expect(details.open).toBe(true)
  })

  it('provenance/sources is available but collapsed by default, and can be expanded', async () => {
    stubValidCounty()
    renderApp(['/counties/01001'])
    const sources = await screen.findByRole('region', { name: /sources/i })

    const summary = within(sources).getByText('View sources')
    const details = summary.closest('details') as HTMLDetailsElement
    expect(details).toBeInTheDocument()
    expect(details.open).toBe(false)
    expect(within(sources).getByText('Primary Care HPSA')).toBeInTheDocument()

    fireEvent.click(summary)
    expect(details.open).toBe(true)
  })

  it('supporting evidence remains available per dimension alongside the redesign', async () => {
    stubValidCounty()
    renderApp(['/counties/01001'])
    await screen.findByRole('heading', { level: 1 })

    expect(screen.getAllByText('Supporting evidence')).toHaveLength(4)
  })

  it('does not render a bare "0" for a small non-zero experimental composite value', async () => {
    stubApi({
      counties: makeCounties(['01001']),
      explorer: (fips) => {
        const payload = makeExplorer(fips)
        return {
          ...payload,
          experimental_composite: {
            ...payload.experimental_composite,
            composite_value: 0.45,
          },
        }
      },
    })
    renderApp(['/counties/01001'])
    const composite = await screen.findByRole('region', {
      name: /experimental composite/i,
    })

    expect(within(composite).queryByText('0')).toBeNull()
    expect(within(composite).getByText('0.5')).toBeInTheDocument()
  })

  it('still renders a genuine zero composite as "0" (distinct from null/missing)', async () => {
    stubApi({
      counties: makeCounties(['01001']),
      explorer: (fips) => {
        const payload = makeExplorer(fips)
        return {
          ...payload,
          experimental_composite: {
            ...payload.experimental_composite,
            composite_value: 0,
          },
        }
      },
    })
    renderApp(['/counties/01001'])
    const composite = await screen.findByRole('region', {
      name: /experimental composite/i,
    })

    expect(within(composite).getByText('0')).toBeInTheDocument()
    expect(within(composite).queryByText(/not available/i)).toBeNull()
  })

  it('preserves loading/error/not-found behavior alongside the redesign', async () => {
    stubApi({ counties: makeCounties(['01001']), explorer: () => 503 })
    renderApp(['/counties/01001'])

    const alert = await screen.findByRole('alert')
    expect(alert).toHaveTextContent(/could not be loaded/i)
    expect(screen.getByRole('button', { name: /try again/i })).toBeInTheDocument()
  })
})

describe('CountyPage (CE-E05 visualization layer)', () => {
  it('renders a percentile position indicator for each of the three percentile dimensions', async () => {
    stubValidCounty()
    renderApp(['/counties/01001'])
    await screen.findByRole('heading', { level: 1 })

    const snapshot = screen.getByRole('region', { name: /healthcare access snapshot/i })
    expect(snapshot.querySelectorAll('.percentile-indicator')).toHaveLength(3)
  })

  it('positions the percentile marker at 0% for a genuine 0th percentile, and it is not "Not available"', async () => {
    stubApi({
      counties: makeCounties(['01001']),
      explorer: (fips) =>
        makeExplorer(fips, {
          dimensions: {
            primary_care: {
              available: true,
              score: 0,
              primary_measure: { normalized_value: 0 },
            },
          },
        }),
    })
    renderApp(['/counties/01001'])
    await screen.findByRole('heading', { level: 1 })

    const snapshot = screen.getByRole('region', { name: /healthcare access snapshot/i })
    const marker = snapshot.querySelector('.percentile-indicator__marker') as HTMLElement
    expect(marker).toBeInTheDocument()
    expect(marker.style.left).toBe('0%')
    expect(within(snapshot).getByText('0')).toBeInTheDocument()
    // Still 3 percentile indicators -- genuine zero is not treated as unavailable.
    expect(snapshot.querySelectorAll('.percentile-indicator')).toHaveLength(3)
  })

  it('positions the percentile marker at 100% for a maximal percentile', async () => {
    stubApi({
      counties: makeCounties(['01001']),
      explorer: (fips) =>
        makeExplorer(fips, {
          dimensions: {
            dental: { score: 100, primary_measure: { normalized_value: 100 } },
          },
        }),
    })
    renderApp(['/counties/01001'])
    await screen.findByRole('heading', { level: 1 })

    const snapshot = screen.getByRole('region', { name: /healthcare access snapshot/i })
    const markers = Array.from(
      snapshot.querySelectorAll('.percentile-indicator__marker'),
    ) as HTMLElement[]
    expect(markers.some((marker) => marker.style.left === '100%')).toBe(true)
  })

  it('positions the percentile marker for a representative non-zero, non-boundary percentile', async () => {
    stubValidCounty() // default fixture: primary_care 88, dental 29, mental_health 23
    renderApp(['/counties/01001'])
    await screen.findByRole('heading', { level: 1 })

    const snapshot = screen.getByRole('region', { name: /healthcare access snapshot/i })
    const markerPositions = Array.from(
      snapshot.querySelectorAll('.percentile-indicator__marker'),
    ).map((marker) => (marker as HTMLElement).style.left)
    expect(markerPositions.sort()).toEqual(['23%', '29%', '88%'])
  })

  it('renders a distinct filled coverage indicator for MUA/P, never a percentile marker', async () => {
    stubValidCounty() // default fixture: mua_p score 99, normalized: false
    renderApp(['/counties/01001'])
    await screen.findByRole('heading', { level: 1 })

    const snapshot = screen.getByRole('region', { name: /healthcare access snapshot/i })
    expect(snapshot.querySelectorAll('.coverage-indicator')).toHaveLength(1)
    const fill = snapshot.querySelector('.coverage-indicator__fill') as HTMLElement
    expect(fill.style.width).toBe('99%')
    // MUA/P must never render as a percentile-position marker.
    expect(snapshot.querySelectorAll('.percentile-indicator')).toHaveLength(3)
  })

  it('renders no indicator at all for an unavailable dimension, distinct from a genuine zero', async () => {
    stubApi({
      counties: makeCounties(['01001']),
      explorer: (fips) =>
        makeExplorer(fips, {
          dimensions: {
            dental: { available: false, score: null, score_status: null },
          },
        }),
    })
    renderApp(['/counties/01001'])
    await screen.findByRole('heading', { level: 1 })

    const snapshot = screen.getByRole('region', { name: /healthcare access snapshot/i })
    // primary_care + mental_health remain percentile-indicated; dental (now
    // unavailable) gets neither a percentile marker nor a coverage bar.
    expect(snapshot.querySelectorAll('.percentile-indicator')).toHaveLength(2)
    expect(snapshot.querySelectorAll('.coverage-indicator')).toHaveLength(1)
    expect(within(snapshot).getByText('Not available')).toBeInTheDocument()
  })

  it('keeps the indicator decorative -- the numeric value and semantic label remain plain visible text', async () => {
    stubValidCounty()
    renderApp(['/counties/01001'])
    await screen.findByRole('heading', { level: 1 })

    const snapshot = screen.getByRole('region', { name: /healthcare access snapshot/i })
    for (const indicator of snapshot.querySelectorAll('.percentile-indicator')) {
      expect(indicator).toHaveAttribute('aria-hidden', 'true')
    }
    for (const indicator of snapshot.querySelectorAll('.coverage-indicator')) {
      expect(indicator).toHaveAttribute('aria-hidden', 'true')
    }
    // The real values/labels remain ordinary visible text (unchanged from CE-E04).
    expect(within(snapshot).getAllByText('percentile')).toHaveLength(3)
    expect(within(snapshot).getByText('% coverage')).toBeInTheDocument()
    expect(within(snapshot).getByText('88')).toBeInTheDocument()
    expect(within(snapshot).getByText('99')).toBeInTheDocument()
  })

  it('does not rely on color alone: percentile and coverage use structurally different widgets', async () => {
    stubValidCounty()
    renderApp(['/counties/01001'])
    await screen.findByRole('heading', { level: 1 })

    const snapshot = screen.getByRole('region', { name: /healthcare access snapshot/i })
    // Different DOM shapes (marker-on-track vs. filled bar) plus a distinct
    // text unit ("percentile" vs. "% coverage") -- not merely a different
    // color applied to an otherwise-identical widget.
    expect(snapshot.querySelector('.percentile-indicator__marker')).toBeInTheDocument()
    expect(snapshot.querySelector('.coverage-indicator__fill')).toBeInTheDocument()
    expect(snapshot.querySelector('.coverage-indicator__marker')).toBeNull()
    expect(snapshot.querySelector('.percentile-indicator__fill')).toBeNull()
  })

  it('does not introduce a chart-library dependency or measure-selection UI', async () => {
    stubValidCounty()
    renderApp(['/counties/01001'])
    await screen.findByRole('heading', { level: 1 })

    // No canvas/svg-chart element and no measure selector anywhere on the page.
    expect(document.querySelector('canvas')).toBeNull()
    expect(screen.queryByRole('combobox', { name: /measure/i })).toBeNull()
  })

  it('keeps all CE-E04 content intact alongside the CE-E05 indicators', async () => {
    stubValidCounty()
    renderApp(['/counties/01001'])
    await screen.findByRole('heading', { level: 1 })

    expect(
      screen.getByRole('navigation', { name: /breadcrumb/i }),
    ).toBeInTheDocument()
    expect(
      screen.getByRole('region', { name: /healthcare access snapshot/i }),
    ).toBeInTheDocument()
    expect(
      screen.getAllByRole('heading', { level: 3 }).map((h) => h.textContent),
    ).toEqual([
      'Primary Care Access',
      'Dental Access',
      'Mental Health Access',
      'MUA/P Access',
    ])
    expect(screen.getAllByText('Supporting evidence')).toHaveLength(4)
    expect(
      screen.getByRole('region', { name: /experimental composite/i }),
    ).toBeInTheDocument()
    expect(screen.getByRole('region', { name: /methodology/i })).toBeInTheDocument()
    expect(screen.getByRole('region', { name: /sources/i })).toBeInTheDocument()
  })
})

describe('CountyPage (CE-E06 measure exploration & drill-down)', () => {
  const DIMENSION_NAMES = [
    'Primary Care Access',
    'Dental Access',
    'Mental Health Access',
    'MUA/P Access',
  ]

  function dimensionListItem(dimensionName: string): HTMLElement {
    const heading = screen.getByRole('heading', { level: 3, name: dimensionName })
    return heading.closest('li') as HTMLElement
  }

  function investigateDetails(dimensionName: string): HTMLDetailsElement {
    const item = dimensionListItem(dimensionName)
    const summary = within(item).getByText(`Investigate ${dimensionName}`)
    return summary.closest('details') as HTMLDetailsElement
  }

  it('gives each dimension its own "Investigate {dimension name}" disclosure, collapsed by default', async () => {
    stubValidCounty()
    renderApp(['/counties/01001'])
    await screen.findByRole('heading', { level: 1 })

    for (const name of DIMENSION_NAMES) {
      const details = investigateDetails(name)
      expect(details).toBeInTheDocument()
      expect(details.open).toBe(false)
    }
  })

  it('keeps dimension name, description, score, qualifier, and the CE-E05 indicator visible while the disclosure is closed', async () => {
    stubValidCounty()
    renderApp(['/counties/01001'])
    await screen.findByRole('heading', { level: 1 })

    const item = dimensionListItem('Primary Care Access')
    expect(investigateDetails('Primary Care Access').open).toBe(false)

    expect(
      within(item).getByRole('heading', { level: 3, name: 'Primary Care Access' }),
    ).toBeInTheDocument()
    expect(within(item).getByText('Primary Care Access description.')).toBeInTheDocument()
    expect(within(item).getByText('88', { selector: '.dimension__score-value' })).toBeInTheDocument()
    expect(within(item).getByText('County percentile rank')).toBeInTheDocument()
    expect(item.querySelector('.percentile-indicator')).toBeInTheDocument()
  })

  it("contains underlying/source-measure data within the dimension's own disclosure", async () => {
    stubValidCounty()
    renderApp(['/counties/01001'])
    await screen.findByRole('heading', { level: 1 })

    const details = investigateDetails('Primary Care Access')
    expect(within(details).getByText('Primary Care Access primary measure')).toBeInTheDocument()
    expect(within(details).getByText('42.5 percent')).toBeInTheDocument()
  })

  it('associates supporting evidence with the correct dimension inside its own disclosure', async () => {
    stubValidCounty()
    renderApp(['/counties/01001'])
    await screen.findByRole('heading', { level: 1 })

    const dentalDetails = investigateDetails('Dental Access')
    expect(within(dentalDetails).getByText('Dental HPSA Area-Weighted Score')).toBeInTheDocument()

    const muaDetails = investigateDetails('MUA/P Access')
    expect(within(muaDetails).getByText('MUA/P Mean Score')).toBeInTheDocument()
    expect(within(dentalDetails).queryByText('MUA/P Mean Score')).toBeNull()
  })

  it('shows methodology scoped to that dimension only, not the page-level methodology block', async () => {
    stubValidCounty()
    renderApp(['/counties/01001'])
    await screen.findByRole('heading', { level: 1 })

    const details = investigateDetails('Primary Care Access')
    expect(
      within(details).getByText('Primary Care Access calculation method.'),
    ).toBeInTheDocument()
    expect(within(details).getByText('county_percentile_rank_average')).toBeInTheDocument()
    expect(within(details).queryByText('Dental Access calculation method.')).toBeNull()
    expect(within(details).queryByText('CHIA Access Profile v0.1')).toBeNull()
  })

  it('shows provenance/source scoped to that dimension only, not the full source list', async () => {
    stubValidCounty()
    renderApp(['/counties/01001'])
    await screen.findByRole('heading', { level: 1 })

    const details = investigateDetails('Dental Access')
    expect(within(details).getByText('Dental HPSA')).toBeInTheDocument()
    expect(within(details).getByText('Dental HPSA Spatial Coverage')).toBeInTheDocument()
    expect(within(details).queryByText('Primary Care HPSA')).toBeNull()
    expect(within(details).queryByText('MUA/P')).toBeNull()
  })

  it("opens one dimension's disclosure without opening the others (no accordion behavior)", async () => {
    stubValidCounty()
    renderApp(['/counties/01001'])
    await screen.findByRole('heading', { level: 1 })

    const allDetails = DIMENSION_NAMES.map((name) => investigateDetails(name))
    expect(allDetails.every((details) => details.open === false)).toBe(true)

    fireEvent.click(within(dimensionListItem('Dental Access')).getByText('Investigate Dental Access'))

    expect(allDetails[1].open).toBe(true)
    expect(allDetails[0].open).toBe(false)
    expect(allDetails[2].open).toBe(false)
    expect(allDetails[3].open).toBe(false)
  })

  it('closes again on a second toggle, hiding the detailed analytical material', async () => {
    stubValidCounty()
    renderApp(['/counties/01001'])
    await screen.findByRole('heading', { level: 1 })

    const summary = within(dimensionListItem('Mental Health Access')).getByText(
      'Investigate Mental Health Access',
    )
    const details = summary.closest('details') as HTMLDetailsElement
    expect(details.open).toBe(false)
    fireEvent.click(summary)
    expect(details.open).toBe(true)
    fireEvent.click(summary)
    expect(details.open).toBe(false)
  })

  it('leaves the page-level Methodology and Provenance panels present and unchanged', async () => {
    stubValidCounty()
    renderApp(['/counties/01001'])
    await screen.findByRole('heading', { level: 1 })

    const methodology = screen.getByRole('region', { name: /methodology/i })
    expect(within(methodology).getByText('CHIA Access Profile v0.1')).toBeInTheDocument()
    for (const name of DIMENSION_NAMES) {
      expect(within(methodology).getByText(`${name} calculation method.`)).toBeInTheDocument()
    }

    const sources = screen.getByRole('region', { name: /sources/i })
    for (const name of ['Primary Care HPSA', 'Dental HPSA', 'Mental Health HPSA', 'MUA/P']) {
      expect(within(sources).getByText(name)).toBeInTheDocument()
    }
  })

  it("never mixes one dimension's methodology into another dimension's disclosure", async () => {
    stubValidCounty()
    renderApp(['/counties/01001'])
    await screen.findByRole('heading', { level: 1 })

    const calcMethods = DIMENSION_NAMES.map((name) => `${name} calculation method.`)
    const detailsList = DIMENSION_NAMES.map((name) => investigateDetails(name))

    detailsList.forEach((details, index) => {
      expect(within(details).getByText(calcMethods[index])).toBeInTheDocument()
      calcMethods.forEach((otherMethod, otherIndex) => {
        if (otherIndex !== index) {
          expect(within(details).queryByText(otherMethod)).toBeNull()
        }
      })
    })
  })

  it('preserves genuine-zero, missing, percentile, and MUA/P coverage semantics inside the disclosure', async () => {
    stubApi({
      counties: makeCounties(['01001']),
      explorer: (fips) =>
        makeExplorer(fips, {
          dimensions: {
            primary_care: {
              available: true,
              score: 0,
              primary_measure: { normalized_value: 0 },
            },
            dental: { available: false, score: null, score_status: null },
          },
        }),
    })
    renderApp(['/counties/01001'])
    await screen.findByRole('heading', { level: 1 })

    const primaryCare = dimensionListItem('Primary Care Access')
    expect(
      within(primaryCare).getByText('0', { selector: '.dimension__score-value' }),
    ).toBeInTheDocument()
    expect(primaryCare.querySelector('.percentile-indicator__marker')).toBeInTheDocument()

    const dental = dimensionListItem('Dental Access')
    expect(within(dental).getByText('Not available')).toBeInTheDocument()
    expect(dental.querySelector('.percentile-indicator')).toBeNull()
    expect(dental.querySelector('.coverage-indicator')).toBeNull()

    const mua = dimensionListItem('MUA/P Access')
    expect(mua.querySelector('.coverage-indicator')).toBeInTheDocument()
    expect(mua.querySelector('.percentile-indicator')).toBeNull()
  })

  it('keeps native <details>/<summary> semantics -- no dialog/modal, no ARIA misuse', async () => {
    stubValidCounty()
    renderApp(['/counties/01001'])
    await screen.findByRole('heading', { level: 1 })

    const summary = within(dimensionListItem('Primary Care Access')).getByText(
      'Investigate Primary Care Access',
    )
    expect(summary.tagName).toBe('SUMMARY')
    expect(summary.closest('details')).toBeInTheDocument()
    expect(screen.queryByRole('dialog')).toBeNull()
  })
})

describe('CountyPage (CE-E11 provenance labeling + CSV export)', () => {
  function primaryCareItem(): HTMLElement {
    return screen
      .getByRole('heading', { level: 3, name: 'Primary Care Access' })
      .closest('li') as HTMLElement
  }

  it('shows the primary variable id alongside the display name in the drill-down', async () => {
    stubValidCounty()
    renderApp(['/counties/01001'])
    await screen.findByRole('heading', { level: 1 })

    const details = within(primaryCareItem()).getByText(
      'Investigate Primary Care Access',
    ).closest('details') as HTMLElement
    expect(
      within(details).getByText('Primary Care Access primary measure'),
    ).toBeInTheDocument()
    expect(
      within(details).getByText('PC_HPSA_GEOGRAPHIC_COVERAGE', { selector: 'code' }),
    ).toBeInTheDocument()
  })

  it('presents the source -> normalized -> score chain with exact (unrounded) values', async () => {
    stubApi({
      counties: makeCounties(['01001']),
      explorer: (fips) =>
        makeExplorer(fips, {
          dimensions: {
            primary_care: {
              score: 63.4179104477612,
              primary_measure: {
                raw_value: 12.5,
                unit: 'percent',
                normalized_value: 63.4179104477612,
              },
            },
          },
        }),
    })
    renderApp(['/counties/01001'])
    await screen.findByRole('heading', { level: 1 })

    const details = within(primaryCareItem()).getByText(
      'Investigate Primary Care Access',
    ).closest('details') as HTMLElement

    const labels = within(details)
      .getAllByRole('term')
      .map((dt) => dt.textContent)
    expect(labels).toEqual(
      expect.arrayContaining([
        'Primary measure',
        'Variable',
        'Source value',
        'Normalized value',
        'Dimension score',
      ]),
    )
    // Source value keeps its verbatim raw form; normalized value and score are
    // exact, not the rounded figures shown in the headline Result.
    expect(within(details).getByText('12.5 percent')).toBeInTheDocument()
    expect(within(details).getAllByText('63.4179104477612')).toHaveLength(2)
    expect(within(details).queryByText('63')).toBeNull()
  })

  it('labels the dimension-scoped provenance with the source id and a linking sentence', async () => {
    stubValidCounty()
    renderApp(['/counties/01001'])
    await screen.findByRole('heading', { level: 1 })

    const details = within(primaryCareItem()).getByText(
      'Investigate Primary Care Access',
    ).closest('details') as HTMLElement
    expect(
      within(details).getByText(/the source value above is drawn from this dataset/i),
    ).toBeInTheDocument()
    expect(within(details).getByText('Primary Care HPSA')).toBeInTheDocument()
    expect(within(details).getByText('1', { selector: 'code' })).toBeInTheDocument()
  })

  it('shows each supporting-evidence variable id', async () => {
    stubValidCounty()
    renderApp(['/counties/01001'])
    await screen.findByRole('heading', { level: 1 })

    const details = within(primaryCareItem()).getByText(
      'Investigate Primary Care Access',
    ).closest('details') as HTMLElement
    expect(
      within(details).getByText('PC_HPSA_GEOGRAPHIC_COVERAGE_SUP_1', { selector: 'code' }),
    ).toBeInTheDocument()
  })

  it('renders the CSV export section after the page-level Sources panel, always visible', async () => {
    stubValidCounty()
    renderApp(['/counties/01001'])
    await screen.findByRole('heading', { level: 1 })

    const sources = screen.getByRole('region', { name: /sources/i })
    const exportRegion = screen.getByRole('region', { name: /county data export/i })
    expect(
      sources.compareDocumentPosition(exportRegion) & Node.DOCUMENT_POSITION_FOLLOWING,
    ).toBeTruthy()

    const button = within(exportRegion).getByRole('button', {
      name: "Download this county's data (CSV)",
    })
    // Not nested inside any collapsed <details>.
    expect(button.closest('details')).toBeNull()
  })

  it('preserves the CE-E06 collapsed-disclosure behavior (each dimension still starts closed)', async () => {
    stubValidCounty()
    renderApp(['/counties/01001'])
    await screen.findByRole('heading', { level: 1 })

    for (const name of [
      'Primary Care Access',
      'Dental Access',
      'Mental Health Access',
      'MUA/P Access',
    ]) {
      const summary = screen.getByText(`Investigate ${name}`)
      expect((summary.closest('details') as HTMLDetailsElement).open).toBe(false)
    }
  })
})
