import { act, fireEvent, screen, waitFor } from '@testing-library/react'

import {
  makeCounties,
  makeExplorer,
  renderApp,
  stubApi,
  stubCountiesFetch,
} from './test/harness'

afterEach(() => {
  vi.unstubAllGlobals()
  vi.restoreAllMocks()
})

async function findSelect(): Promise<HTMLSelectElement> {
  return (await screen.findByRole('combobox', {
    name: /county/i,
  })) as HTMLSelectElement
}

describe('CE-C02 county selection & URL state', () => {
  it('starts with no county assumed at "/"', async () => {
    stubCountiesFetch(makeCounties(['01001', '01003']))
    const { router } = renderApp(['/'])

    const select = await findSelect()
    expect(select.value).toBe('')
    expect(router.state.location.pathname).toBe('/')
    expect(screen.getByText(/no county is currently selected/i)).toBeInTheDocument()
  })

  it('selecting a county updates the URL and renders that county profile', async () => {
    stubApi({
      counties: makeCounties(['01001', '01003']),
      explorer: (fips) =>
        makeExplorer(fips, { county: { county_name: `County ${fips}` } }),
    })
    const { router } = renderApp(['/'])

    fireEvent.change(await findSelect(), { target: { value: '01001' } })

    await waitFor(() =>
      expect(router.state.location.pathname).toBe('/counties/01001'),
    )
    expect(
      await screen.findByRole('heading', { level: 1, name: /county 01001/i }),
    ).toBeInTheDocument()
    expect((await findSelect()).value).toBe('01001')
  })

  it('supports direct navigation to a county URL', async () => {
    stubApi({
      counties: makeCounties(['01001', '01003']),
      explorer: (fips) =>
        makeExplorer(fips, { county: { county_name: `County ${fips}` } }),
    })
    renderApp(['/counties/01003'])

    expect(
      await screen.findByRole('heading', { level: 1, name: /county 01003/i }),
    ).toBeInTheDocument()
    expect((await findSelect()).value).toBe('01003')
  })

  it('honours browser back and forward navigation', async () => {
    stubCountiesFetch(makeCounties(['01001', '01003']))
    const { router } = renderApp(['/'])

    fireEvent.change(await findSelect(), { target: { value: '01001' } })
    await waitFor(() =>
      expect(router.state.location.pathname).toBe('/counties/01001'),
    )
    fireEvent.change(await findSelect(), { target: { value: '01003' } })
    await waitFor(() =>
      expect(router.state.location.pathname).toBe('/counties/01003'),
    )

    await act(async () => {
      await router.navigate(-1)
    })
    await waitFor(() =>
      expect(router.state.location.pathname).toBe('/counties/01001'),
    )
    expect((await findSelect()).value).toBe('01001')

    await act(async () => {
      await router.navigate(1)
    })
    await waitFor(() =>
      expect(router.state.location.pathname).toBe('/counties/01003'),
    )
    expect((await findSelect()).value).toBe('01003')
  })

  it('renders NotFound (URL kept) for an unknown county reached via the URL', async () => {
    stubCountiesFetch(makeCounties(['01001', '01003']))
    const { router } = renderApp(['/counties/55555'])

    expect(
      await screen.findByText(/no county with fips 55555/i),
    ).toBeInTheDocument()
    expect(router.state.location.pathname).toBe('/counties/55555')
  })

  it('requests the Explorer endpoint only once a county is selected', async () => {
    const fetchMock = stubApi({
      counties: makeCounties(['01001', '01003']),
      explorer: (fips) => makeExplorer(fips),
    })
    const { router } = renderApp(['/'])
    await findSelect()

    expect(
      fetchMock.mock.calls
        .map((call) => String(call[0]))
        .some((url) => url.includes('/explorer')),
    ).toBe(false)

    fireEvent.change(await findSelect(), { target: { value: '01001' } })
    await waitFor(() =>
      expect(router.state.location.pathname).toBe('/counties/01001'),
    )
    await screen.findByRole('heading', { level: 1 })

    const explorerCalls = fetchMock.mock.calls
      .map((call) => String(call[0]))
      .filter((url) => url.includes('/explorer'))
    expect(explorerCalls).toEqual(['/api/v1/counties/01001/explorer'])
  })
})
