import { screen, waitFor } from '@testing-library/react'

import { makeCounties, makeMultiStateCounties, renderApp, stubCountiesFetch } from '../test/harness'

afterEach(() => {
  vi.unstubAllGlobals()
  vi.restoreAllMocks()
})

describe('StatePage (CE-E02)', () => {
  it('shows a loading state before the county/state directory resolves', () => {
    stubCountiesFetch(() => new Promise<Response>(() => {}))
    renderApp(['/states/01'])

    // The global county-selector nav also reflects the same (shared)
    // directory loading state -- see CountyPage.test.tsx's identical
    // "getAllByRole" pattern for this dual-render.
    expect(screen.getAllByRole('status').length).toBeGreaterThan(0)
    expect(screen.getByText(/loading states/i)).toBeInTheDocument()
  })

  it('identifies the selected state and defers the county map to CE-E03', async () => {
    stubCountiesFetch(makeMultiStateCounties())
    renderApp(['/states/01'])

    expect(
      await screen.findByRole('heading', { level: 1, name: /^alabama$/i }),
    ).toBeInTheDocument()
    expect(screen.getByText(/fips 01/i)).toBeInTheDocument()
    expect(screen.getByText(/not yet available in this view/i)).toBeInTheDocument()
  })

  it('leaves the existing global county selector available on the state route', async () => {
    stubCountiesFetch(makeMultiStateCounties())
    renderApp(['/states/01'])

    await screen.findByRole('heading', { level: 1, name: /^alabama$/i })
    expect(screen.getByRole('combobox', { name: /county/i })).toBeInTheDocument()
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
