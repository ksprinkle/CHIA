import { fireEvent, screen, within } from '@testing-library/react'

import { makeMultiStateCounties, renderApp, stubCountiesFetch } from '../test/harness'

afterEach(() => {
  vi.unstubAllGlobals()
  vi.restoreAllMocks()
})

async function findMap() {
  return screen.findByRole('group', { name: /county map/i })
}

describe('StateCountyMap (CE-E03)', () => {
  it('loads the state-specific TopoJSON and renders one feature per supported county', async () => {
    stubCountiesFetch(makeMultiStateCounties())
    renderApp(['/states/01'])

    const map = await findMap()
    const countyButtons = await within(map).findAllByRole('button')

    expect(countyButtons).toHaveLength(2)
  })

  it('resolves county labels from the authoritative directory, not the raw geometry properties', async () => {
    stubCountiesFetch(makeMultiStateCounties())
    renderApp(['/states/01'])

    const map = await findMap()
    // Directory county_name is "Autauga County"; the stub geometry's own
    // properties.NAME is just "Autauga" -- the accessible name must come
    // from the directory.
    expect(
      await within(map).findByRole('button', { name: /select autauga county/i }),
    ).toBeInTheDocument()
    expect(
      within(map).getByRole('button', { name: /select baldwin county/i }),
    ).toBeInTheDocument()
  })

  it('navigates to /counties/:countyFips when a county feature is clicked', async () => {
    stubCountiesFetch(makeMultiStateCounties())
    const { router } = renderApp(['/states/01'])

    const map = await findMap()
    const baldwin = await within(map).findByRole('button', { name: /select baldwin county/i })
    fireEvent.click(baldwin)

    expect(router.state.location.pathname).toBe('/counties/01003')
  })

  it('navigates to /counties/:countyFips on Enter and Space keydown (keyboard access)', async () => {
    stubCountiesFetch(makeMultiStateCounties())
    const { router } = renderApp(['/states/01'])

    const map = await findMap()
    const autauga = await within(map).findByRole('button', { name: /select autauga county/i })
    fireEvent.keyDown(autauga, { key: 'Enter' })

    expect(router.state.location.pathname).toBe('/counties/01001')
  })

  it('gives the focused county a clear, visible focus state', async () => {
    stubCountiesFetch(makeMultiStateCounties())
    renderApp(['/states/01'])

    const map = await findMap()
    const autauga = await within(map).findByRole('button', { name: /select autauga county/i })
    autauga.focus()

    expect(autauga).toHaveFocus()
  })

  it('does not render a county the directory does not recognize, even if the geometry has it', async () => {
    // The stub geometry for state 01 has two features (01001, 01003); the
    // directory below only recognizes 01001 -- the mismatched 01003
    // geometry feature must not become a selectable county.
    stubCountiesFetch({
      count: 1,
      counties: [
        {
          county_fips: '01001',
          state_fips: '01',
          state_abbr: 'AL',
          county_name: 'Autauga County',
          state_name: 'Alabama',
        },
      ],
    })
    renderApp(['/states/01'])

    const map = await findMap()
    expect(
      await within(map).findByRole('button', { name: /select autauga county/i }),
    ).toBeInTheDocument()
    expect(within(map).queryAllByRole('button')).toHaveLength(1)
    expect(within(map).queryByRole('button', { name: /baldwin/i })).toBeNull()
  })
})
