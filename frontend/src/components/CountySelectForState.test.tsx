import { fireEvent, screen, within } from '@testing-library/react'

import { makeMultiStateCounties, renderApp, stubCountiesFetch } from '../test/harness'

afterEach(() => {
  vi.unstubAllGlobals()
  vi.restoreAllMocks()
})

describe('CountySelectForState (CE-E03)', () => {
  it('contains only counties belonging to the selected state', async () => {
    stubCountiesFetch(makeMultiStateCounties())
    renderApp(['/states/01'])

    const select = await screen.findByRole('combobox', { name: /county in alabama/i })
    const options = within(select).getAllByRole('option')

    // placeholder + 2 Alabama counties (California's 06075 excluded)
    expect(options).toHaveLength(3)
    expect(options[0]).toBeDisabled()
    expect(options[1]).toHaveTextContent('Autauga County')
    expect(options[2]).toHaveTextContent('Baldwin County')
  })

  it('presents county names with state context in its label', async () => {
    stubCountiesFetch(makeMultiStateCounties())
    renderApp(['/states/01'])

    expect(
      await screen.findByRole('combobox', { name: /county in alabama/i }),
    ).toBeInTheDocument()
  })

  it('navigates to /counties/:countyFips when a county is chosen', async () => {
    stubCountiesFetch(makeMultiStateCounties())
    const { router } = renderApp(['/states/01'])

    const select = await screen.findByRole('combobox', { name: /county in alabama/i })
    fireEvent.change(select, { target: { value: '01003' } })

    expect(router.state.location.pathname).toBe('/counties/01003')
  })

  it('uses the same authoritative derived county collection as the map (same destination)', async () => {
    stubCountiesFetch(makeMultiStateCounties())
    const mapRun = renderApp(['/states/01'])
    const map = await screen.findByRole('group', { name: /county map/i })
    const autaugaButton = await within(map).findByRole('button', {
      name: /select autauga county/i,
    })
    fireEvent.click(autaugaButton)
    const mapDestination = mapRun.router.state.location.pathname
    mapRun.unmount()

    const selectRun = renderApp(['/states/01'])
    const select = await screen.findByRole('combobox', { name: /county in alabama/i })
    fireEvent.change(select, { target: { value: '01001' } })
    const selectDestination = selectRun.router.state.location.pathname

    expect(mapDestination).toBe('/counties/01001')
    expect(selectDestination).toBe('/counties/01001')
    expect(mapDestination).toBe(selectDestination)
  })

  it('always renders unselected (no persistent selection on the state page)', async () => {
    stubCountiesFetch(makeMultiStateCounties())
    renderApp(['/states/01'])

    const select = (await screen.findByRole('combobox', {
      name: /county in alabama/i,
    })) as HTMLSelectElement
    expect(select.value).toBe('')
  })

  it('is a distinct control from the existing global county selector', async () => {
    stubCountiesFetch(makeMultiStateCounties())
    renderApp(['/states/01'])

    expect(await screen.findByRole('combobox', { name: /^county$/i })).toBeInTheDocument()
    expect(
      await screen.findByRole('combobox', { name: /county in alabama/i }),
    ).toBeInTheDocument()
  })
})
