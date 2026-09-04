import { act, fireEvent, screen, waitFor } from '@testing-library/react'

import {
  makeCounties,
  makeExplorer,
  renderApp,
  stubApi,
  stubCountiesFetch,
} from '../test/harness'

/** Content that belongs to CE-C04 / CE-C05 / CE-C06, not CE-C03. */
const LATER_SLICE_LEAKAGE = [
  /supporting evidence/i,
  /experimental \/ provisional/i,
  /experimental_provisional/i,
  /59\.75/, // mocked composite_value
  /composite/i,
  /methodology/i,
  /provenance/i,
  /CHIA Access Profile v0\.1 methodology/i, // mocked methodology name
  /HRSA HPSA provenance source/i, // mocked provenance source name
  /interpretation/i,
  /compared (?:to|with)/i,
  /\b(highest|lowest)\b/i,
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

    expect(
      await screen.findByRole('heading', { level: 1, name: /autauga county/i }),
    ).toBeInTheDocument()
    expect(screen.getByText('Alabama (AL)')).toBeInTheDocument()
    expect(screen.getByText('01001')).toBeInTheDocument()
    expect(screen.getByText('v0.1')).toBeInTheDocument()
    expect(screen.getByText('Complete')).toBeInTheDocument()
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

    // 88.757... -> 89 and 12.4 -> 12 (presentation only; not recalculated)
    expect(screen.getByText('89')).toBeInTheDocument()
    expect(screen.getByText('12')).toBeInTheDocument()
    expect(screen.getAllByText('County percentile rank')).toHaveLength(3)
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

    expect(screen.getByText('Not available')).toBeInTheDocument()
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

  it('does not render CE-C04 / CE-C05 / CE-C06 content', async () => {
    stubValidCounty()
    renderApp(['/counties/01001'])
    await screen.findByRole('heading', { level: 1 })

    for (const pattern of LATER_SLICE_LEAKAGE) {
      expect(screen.queryByText(pattern)).toBeNull()
    }
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
