import { fireEvent, screen, waitFor, within } from '@testing-library/react'

import {
  makeCounties,
  makeMultiStateCounties,
  makeStateScores,
  renderApp,
  stubApi,
  stubCountiesFetch,
} from '../test/harness'

afterEach(() => {
  vi.unstubAllGlobals()
  vi.restoreAllMocks()
})

describe('StatePage (CE-E02/CE-E03)', () => {
  it('shows a loading state before the county/state directory resolves', () => {
    stubCountiesFetch(() => new Promise<Response>(() => {}))
    renderApp(['/states/01'])

    // The global county-selector nav also reflects the same (shared)
    // directory loading state -- see CountyPage.test.tsx's identical
    // "getAllByRole" pattern for this dual-render.
    expect(screen.getAllByRole('status').length).toBeGreaterThan(0)
    expect(screen.getByText(/loading states/i)).toBeInTheDocument()
  })

  it('identifies the selected state, preserving CE-E02 state identification', async () => {
    stubCountiesFetch(makeMultiStateCounties())
    renderApp(['/states/01'])

    expect(
      await screen.findByRole('heading', { level: 1, name: /^alabama$/i }),
    ).toBeInTheDocument()
    expect(screen.getByText(/fips 01/i)).toBeInTheDocument()
  })

  it('preserves return-to-United-States navigation', async () => {
    stubCountiesFetch(makeMultiStateCounties())
    renderApp(['/states/01'])

    await screen.findByRole('heading', { level: 1, name: /^alabama$/i })
    expect(screen.getByRole('link', { name: /united states/i })).toHaveAttribute('href', '/')
  })

  it('CE-E03: renders the state county map and the accessible state-scoped county selector', async () => {
    stubCountiesFetch(makeMultiStateCounties())
    renderApp(['/states/01'])

    await screen.findByRole('heading', { level: 1, name: /^alabama$/i })
    expect(screen.getByRole('group', { name: /county map/i })).toBeInTheDocument()
    expect(
      await screen.findByRole('combobox', { name: /county in alabama/i }),
    ).toBeInTheDocument()
  })

  it('leaves the existing global county selector available on the state route', async () => {
    stubCountiesFetch(makeMultiStateCounties())
    renderApp(['/states/01'])

    await screen.findByRole('heading', { level: 1, name: /^alabama$/i })
    // Anchored: CE-E03 also adds "County in Alabama" on the same page, which
    // would otherwise ambiguously match a loose /county/i query.
    expect(screen.getByRole('combobox', { name: /^county$/i })).toBeInTheDocument()
  })

  it('renders NotFound for a malformed state FIPS', async () => {
    stubCountiesFetch(makeMultiStateCounties())
    renderApp(['/states/abc'])

    expect(await screen.findByText(/not a two-digit state fips code/i)).toBeInTheDocument()
  })

  it('renders NotFound for a well-formed but unknown state FIPS', async () => {
    stubCountiesFetch(makeCounties(['01001']))
    renderApp(['/states/99'])

    expect(
      await screen.findByText(/no state with fips 99 is in the chia state universe/i),
    ).toBeInTheDocument()
  })

  it('shows an alert with retry when the directory fails to load', async () => {
    stubCountiesFetch(new TypeError('network down'))
    renderApp(['/states/01'])

    // Matches CountyPage.test.tsx's "surfaces the county-list error" pattern:
    // the global county-selector nav also renders its own alert for the same
    // (shared) directory error.
    await waitFor(() => expect(screen.getAllByRole('alert').length).toBeGreaterThan(0))
    expect(screen.getByText(/the state list could not be loaded/i)).toBeInTheDocument()
  })
})

describe('StatePage (CE-E10 analytical heat map)', () => {
  it('renders the measure selector, legend, and county data table once scores load', async () => {
    stubCountiesFetch(makeMultiStateCounties())
    renderApp(['/states/01'])
    await screen.findByRole('heading', { level: 1, name: /^alabama$/i })

    const selector = await screen.findByRole('combobox', {
      name: /colour counties by/i,
    })
    expect(within(selector).getAllByRole('option').map((o) => o.textContent)).toEqual([
      'Primary Care Access',
      'Dental Access',
      'Mental Health Access',
      'MUA/P Access',
    ])
    expect((selector as HTMLSelectElement).value).toBe('primary_care')

    expect(
      screen.getByRole('region', { name: /map legend: primary care access/i }),
    ).toBeInTheDocument()
    expect(screen.getByText('View county data table')).toBeInTheDocument()
  })

  it('the legend makes the percentile-vs-coverage distinction explicit in text', async () => {
    stubCountiesFetch(makeMultiStateCounties())
    renderApp(['/states/01'])
    const selector = await screen.findByRole('combobox', {
      name: /colour counties by/i,
    })

    // Percentile dimension.
    let legend = screen.getByRole('region', { name: /map legend/i })
    expect(within(legend).getByText(/percentile rank \(0–100\)/i)).toBeInTheDocument()

    // Switch to MUA/P coverage -> a different, clearly-labelled scale.
    fireEvent.change(selector, { target: { value: 'mua_p' } })
    legend = screen.getByRole('region', { name: /map legend: mua\/p access/i })
    expect(within(legend).getByText(/geographic coverage \(/i)).toBeInTheDocument()
    expect(within(legend).getByText(/not a percentile/i)).toBeInTheDocument()
    // No percentile framing on the coverage legend.
    expect(within(legend).queryByText(/percentile rank/i)).toBeNull()
  })

  it('changing the measure recolours the map and updates the data table (no navigation)', async () => {
    stubCountiesFetch(makeMultiStateCounties())
    const { router } = renderApp(['/states/01'])
    const selector = await screen.findByRole('combobox', {
      name: /colour counties by/i,
    })
    const map = screen.getByRole('group', { name: /county map/i })
    const fipsBefore = (
      within(map).getByRole('button', { name: /select autauga county/i }) as unknown as SVGElement
    ).style.fill

    fireEvent.change(selector, { target: { value: 'dental' } })

    const table = screen.getByRole('table')
    expect(within(table).getByText(/dental access —/i)).toBeInTheDocument()
    const fipsAfter = (
      within(map).getByRole('button', { name: /select autauga county/i }) as unknown as SVGElement
    ).style.fill
    expect(fipsAfter).not.toBe(fipsBefore)
    expect(router.state.location.pathname).toBe('/states/01') // did not navigate
  })

  it('the data table lists every county in the state with its active-dimension value', async () => {
    stubCountiesFetch(makeMultiStateCounties())
    renderApp(['/states/01'])
    await screen.findByRole('combobox', { name: /colour counties by/i })

    const table = screen.getByRole('table')
    const rowHeaders = within(table)
      .getAllByRole('rowheader')
      .map((cell) => cell.textContent)
    expect(rowHeaders).toEqual(['Autauga County', 'Baldwin County'])
    // Each data cell is a percentile value or "Not available".
    for (const cell of within(table).getAllByRole('cell')) {
      expect(cell.textContent).toMatch(/^\d+ percentile$|^Not available$/)
    }
  })

  it('keeps map <-> selector parity: the same counties in the map, the accessible selector, and the table', async () => {
    stubCountiesFetch(makeMultiStateCounties())
    renderApp(['/states/01'])

    const map = await screen.findByRole('group', { name: /county map/i })
    const mapCounties = within(map)
      .getAllByRole('button')
      .map((b) => b.getAttribute('aria-label')?.replace(/^Select /, ''))
      .sort()
    const selectCounties = within(
      screen.getByRole('combobox', { name: /county in alabama/i }),
    )
      .getAllByRole('option')
      .filter((o) => (o as HTMLOptionElement).value !== '')
      .map((o) => o.textContent)
      .sort()
    const tableCounties = within(screen.getByRole('table'))
      .getAllByRole('rowheader')
      .map((c) => c.textContent)
      .sort()

    expect(mapCounties).toEqual(selectCounties)
    expect(mapCounties).toEqual(tableCounties)
    expect(mapCounties).toEqual(['Autauga County', 'Baldwin County'])
  })

  it('an unavailable score shows "Not available" in the table and "no data" on the map, distinct from a genuine zero', async () => {
    stubApi({
      counties: makeMultiStateCounties(),
      stateScores: () =>
        makeStateScores('01', makeMultiStateCounties().counties, {
          '01001': { primary_care: { available: false } },
          '01003': { primary_care: { available: true, score: 0 } },
        }),
    })
    renderApp(['/states/01'])
    await screen.findByRole('combobox', { name: /colour counties by/i })

    const table = screen.getByRole('table')
    const rows = within(table).getAllByRole('row')
    // header row + 2 counties
    expect(within(rows[1]).getByText('Not available')).toBeInTheDocument()
    expect(within(rows[2]).getByText('0 percentile')).toBeInTheDocument()

    const map = screen.getByRole('group', { name: /county map/i })
    expect(
      within(map)
        .getByRole('button', { name: /select autauga county/i })
        .querySelector('title')?.textContent,
    ).toBe('Autauga County — no data')
  })

  it('while scores are loading, the map still renders and the analytical controls are absent', async () => {
    stubCountiesFetch((...args: unknown[]) => {
      const url = String(args[0])
      if (url.includes('/geo/')) {
        return Promise.resolve({
          ok: true,
          status: 200,
          json: async () => ({
            type: 'Topology',
            arcs: [[[0, 0], [1, 0], [1, 1], [0, 1], [0, 0]]],
            objects: {
              counties: {
                type: 'GeometryCollection',
                geometries: [
                  { type: 'Polygon', id: '01001', properties: { NAME: 'Autauga' }, arcs: [[0]] },
                ],
              },
            },
          }),
        } as Response)
      }
      if (url.includes('/dimension-scores')) return new Promise<Response>(() => {})
      if (url.includes('/explorer')) {
        return Promise.resolve({ ok: false, status: 404, json: async () => ({}) } as Response)
      }
      return Promise.resolve({
        ok: true,
        status: 200,
        json: async () => makeMultiStateCounties(),
      } as Response)
    })
    renderApp(['/states/01'])

    await screen.findByRole('heading', { level: 1, name: /^alabama$/i })
    expect(screen.getByRole('group', { name: /county map/i })).toBeInTheDocument()
    expect(
      await screen.findByText(/loading county map colours/i),
    ).toBeInTheDocument()
    expect(
      screen.queryByRole('combobox', { name: /colour counties by/i }),
    ).toBeNull()
    expect(screen.queryByRole('table')).toBeNull()
    // The accessible county selector and county navigation are unaffected.
    expect(
      screen.getByRole('combobox', { name: /county in alabama/i }),
    ).toBeInTheDocument()
  })

  it('if scores fail to load, the map stays navigable and an alert offers retry', async () => {
    stubApi({ counties: makeMultiStateCounties(), stateScores: () => 503 })
    renderApp(['/states/01'])

    await screen.findByRole('heading', { level: 1, name: /^alabama$/i })
    await waitFor(() =>
      expect(
        screen.getByText(/county map colours could not be loaded/i),
      ).toBeInTheDocument(),
    )
    expect(screen.getByRole('group', { name: /county map/i })).toBeInTheDocument()
    expect(
      screen.getByRole('combobox', { name: /county in alabama/i }),
    ).toBeInTheDocument()
    expect(
      screen.queryByRole('combobox', { name: /colour counties by/i }),
    ).toBeNull()
  })
})
