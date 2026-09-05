import { act, fireEvent, screen, waitFor, within } from '@testing-library/react'

import {
  makeCounties,
  makeExplorer,
  makeMultiStateCounties,
  renderApp,
  stubApi,
  stubCountiesFetch,
} from './test/harness'

afterEach(() => {
  vi.unstubAllGlobals()
  vi.restoreAllMocks()
})

// CE-E13: the state route also renders a "County in <state>" control, so the
// app-level county selector is matched by its exact "County" name.
async function findSelect(): Promise<HTMLSelectElement> {
  return (await screen.findByRole('combobox', {
    name: /^county$/i,
  })) as HTMLSelectElement
}

describe('CE-C02 county selection & URL state', () => {
  it('starts with no county assumed at "/" (county selector disabled until a state is chosen)', async () => {
    stubCountiesFetch(makeCounties(['01001', '01003']))
    const { router } = renderApp(['/'])

    const select = await findSelect()
    expect(select.value).toBe('')
    expect(select).toBeDisabled()
    expect(router.state.location.pathname).toBe('/')
    expect(screen.getByText(/no county is currently selected/i)).toBeInTheDocument()
  })

  it('selecting a county from a state route updates the URL and renders that county profile', async () => {
    stubApi({
      counties: makeCounties(['01001', '01003']),
      explorer: (fips) =>
        makeExplorer(fips, { county: { county_name: `County ${fips}` } }),
    })
    const { router } = renderApp(['/states/01'])

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
    const { router } = renderApp(['/states/01'])

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
    const { router } = renderApp(['/states/01'])
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

describe('CE-E02 U.S. map landing & state navigation', () => {
  it('the map and the accessible state selector resolve the same state to the same URL', async () => {
    stubCountiesFetch(makeMultiStateCounties())

    // Map selection.
    const mapRun = renderApp(['/'])
    const map = await screen.findByRole('group', { name: /map of the united states/i })
    const california = await within(map).findByRole('button', { name: /select california/i })
    fireEvent.click(california)
    const mapDestination = mapRun.router.state.location.pathname
    mapRun.unmount()

    // Accessible-selector selection, from a fresh render.
    const selectRun = renderApp(['/'])
    const select = await screen.findByRole('combobox', { name: /^state$/i })
    fireEvent.change(select, { target: { value: '06' } })
    const selectDestination = selectRun.router.state.location.pathname

    expect(mapDestination).toBe('/states/06')
    expect(selectDestination).toBe('/states/06')
    expect(mapDestination).toBe(selectDestination)
  })

  it('the U.S. map landing page still surfaces the existing global county selector', async () => {
    stubCountiesFetch(makeMultiStateCounties())
    renderApp(['/'])

    expect(
      await screen.findByRole('combobox', { name: /county/i }),
    ).toBeInTheDocument()
    expect(await screen.findByRole('combobox', { name: /^state$/i })).toBeInTheDocument()
  })

  it('selecting a state from the map navigates to a working state placeholder route', async () => {
    stubCountiesFetch(makeMultiStateCounties())
    const { router } = renderApp(['/'])

    const map = await screen.findByRole('group', { name: /map of the united states/i })
    const alabama = await within(map).findByRole('button', { name: /select alabama/i })
    fireEvent.click(alabama)

    await waitFor(() => expect(router.state.location.pathname).toBe('/states/01'))
    expect(
      await screen.findByRole('heading', { level: 1, name: /^alabama$/i }),
    ).toBeInTheDocument()
  })
})

describe('CE-E03 state county map & county navigation', () => {
  it('the county map and the accessible county selector resolve the same county to the same URL', async () => {
    stubCountiesFetch(makeMultiStateCounties())

    // Map selection.
    const mapRun = renderApp(['/states/01'])
    const map = await screen.findByRole('group', { name: /county map/i })
    const baldwinButton = await within(map).findByRole('button', {
      name: /select baldwin county/i,
    })
    fireEvent.click(baldwinButton)
    const mapDestination = mapRun.router.state.location.pathname
    mapRun.unmount()

    // Accessible-selector selection, from a fresh render.
    const selectRun = renderApp(['/states/01'])
    const select = await screen.findByRole('combobox', { name: /county in alabama/i })
    fireEvent.change(select, { target: { value: '01003' } })
    const selectDestination = selectRun.router.state.location.pathname

    expect(mapDestination).toBe('/counties/01003')
    expect(selectDestination).toBe('/counties/01003')
    expect(mapDestination).toBe(selectDestination)
  })

  it('the state route still surfaces the existing global county selector alongside the new controls', async () => {
    stubCountiesFetch(makeMultiStateCounties())
    renderApp(['/states/01'])

    await screen.findByRole('heading', { level: 1, name: /^alabama$/i })
    expect(screen.getByRole('combobox', { name: /^county$/i })).toBeInTheDocument()
    expect(
      await screen.findByRole('combobox', { name: /county in alabama/i }),
    ).toBeInTheDocument()
    expect(screen.getByRole('group', { name: /county map/i })).toBeInTheDocument()
  })

  it('selecting a supported county from the state route reaches its existing County Profile route', async () => {
    stubApi({
      counties: makeMultiStateCounties(),
      explorer: (fips) => makeExplorer(fips, { county: { county_name: `County ${fips}` } }),
    })
    const { router } = renderApp(['/states/01'])

    const map = await screen.findByRole('group', { name: /county map/i })
    const autaugaButton = await within(map).findByRole('button', {
      name: /select autauga county/i,
    })
    fireEvent.click(autaugaButton)

    await waitFor(() => expect(router.state.location.pathname).toBe('/counties/01001'))
    expect(
      await screen.findByRole('heading', { level: 1, name: /county 01001/i }),
    ).toBeInTheDocument()
  })
})
