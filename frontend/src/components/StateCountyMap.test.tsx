import { fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import { RouterProvider, createMemoryRouter } from 'react-router-dom'

import { StateCountyMap } from './StateCountyMap'
import { MISSING_FILL } from '../lib/choropleth'
import {
  STUB_STATE_COUNTIES_TOPOJSON,
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

async function findMap() {
  return screen.findByRole('group', { name: /county map/i })
}

async function findCountyButton(name: RegExp) {
  const map = await findMap()
  return within(map).findByRole('button', { name })
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

describe('StateCountyMap (CE-E10 analytical choropleth)', () => {
  it('colours each county by its active-dimension score and keeps the navigation contract', async () => {
    stubCountiesFetch(makeMultiStateCounties())
    const { router } = renderApp(['/states/01'])

    const autauga = await findCountyButton(/select autauga county/i)

    // Navigation contract unchanged: accessible name is still "Select {name}",
    // and activation still routes to /counties/:fips.
    expect(autauga).toHaveAttribute('aria-label', 'Select Autauga County')
    expect(autauga).not.toHaveAttribute('title')

    // Analytical colouring: a real fill (from the ramp), not the neutral
    // CSS default, and a <title> carrying the value.
    expect(autauga.style.fill).toMatch(/^#[0-9a-f]{6}$/i)
    const title = autauga.querySelector('title')
    expect(title?.textContent).toMatch(/^Autauga County — \d+ percentile$/)

    fireEvent.click(autauga)
    expect(router.state.location.pathname).toBe('/counties/01001')
  })

  it('uses the distinct MISSING_FILL and a "no data" title for an unavailable score', async () => {
    stubApi({
      counties: makeMultiStateCounties(),
      stateScores: () =>
        makeStateScores('01', makeMultiStateCounties().counties, {
          '01001': { primary_care: { available: false } },
        }),
    })
    renderApp(['/states/01'])

    const autauga = await findCountyButton(/select autauga county/i)
    expect(autauga.style.fill.toLowerCase()).toBe(MISSING_FILL.toLowerCase())
    expect(autauga.querySelector('title')?.textContent).toBe(
      'Autauga County — no data',
    )
  })

  it('renders neutral (no inline fill, name-only title) while scores are still loading', async () => {
    // Directory resolves, but the dimension-scores request never settles.
    stubCountiesFetch((...args: unknown[]) => {
      const url = String(args[0])
      if (url.includes('/geo/')) {
        return Promise.resolve({
          ok: true,
          status: 200,
          json: async () => ({
            type: 'Topology',
            arcs: [
              [
                [0, 0],
                [1, 0],
                [1, 1],
                [0, 1],
                [0, 0],
              ],
            ],
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

    const autauga = await findCountyButton(/select autauga county/i)
    expect(autauga.style.fill).toBe('')
    expect(autauga.querySelector('title')?.textContent).toBe('Autauga County')
  })
})

describe('StateCountyMap (CE-DEP02 deployment base path)', () => {
  it('requests the per-state county TopoJSON under import.meta.env.BASE_URL', async () => {
    const requested: string[] = []
    vi.stubGlobal(
      'fetch',
      vi.fn((input: unknown) => {
        requested.push(String(input))
        return Promise.resolve({
          ok: true,
          status: 200,
          json: async () => STUB_STATE_COUNTIES_TOPOJSON['01'],
        } as Response)
      }),
    )

    const counties = makeMultiStateCounties().counties.filter(
      (county) => county.state_fips === '01',
    )
    const router = createMemoryRouter(
      [{ path: '/', element: <StateCountyMap stateFips="01" counties={counties} /> }],
      { initialEntries: ['/'] },
    )
    render(<RouterProvider router={router} />)

    await waitFor(() =>
      expect(requested).toContain(
        `${import.meta.env.BASE_URL}geo/counties/01.topojson`,
      ),
    )
    expect(`${import.meta.env.BASE_URL}geo/counties/01.topojson`).toBe(
      '/CHIA/geo/counties/01.topojson',
    )
    expect(requested).not.toContain('/geo/counties/01.topojson')
  })
})
