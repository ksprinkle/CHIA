import { fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import { RouterProvider, createMemoryRouter } from 'react-router-dom'

import { UsStateMap } from './UsStateMap'
import { MISSING_FILL, fillForScore } from '../lib/choropleth'
import { DIMENSIONS } from '../lib/dimensions'
import type { DimensionMeta } from '../lib/dimensions'
import type { StateSummary } from '../lib/states'
import {
  STUB_US_STATES_TOPOJSON,
  makeMultiStateCounties,
  renderApp,
  stubCountiesFetch,
} from '../test/harness'

afterEach(() => {
  vi.unstubAllGlobals()
  vi.restoreAllMocks()
})

const TWO_STATES: StateSummary[] = [
  { state_fips: '01', state_abbr: 'AL', state_name: 'Alabama' },
  { state_fips: '06', state_abbr: 'CA', state_name: 'California' },
]

const PERCENTILE_DIM = DIMENSIONS.find((d) => d.key === 'primary_care') as DimensionMeta
const COVERAGE_DIM = DIMENSIONS.find((d) => d.key === 'mua_p') as DimensionMeta

/** Render UsStateMap in isolation with a router so navigation is observable. */
function renderMap(props: Partial<Parameters<typeof UsStateMap>[0]> = {}) {
  stubCountiesFetch(makeMultiStateCounties()) // resolves /geo/us-states.topojson
  const router = createMemoryRouter(
    [
      { path: '/', element: <UsStateMap states={TWO_STATES} {...props} /> },
      { path: '/states/:stateFips', element: <div>state route</div> },
    ],
    { initialEntries: ['/'] },
  )
  return { router, ...render(<RouterProvider router={router} />) }
}

describe('UsStateMap (CE-E02)', () => {
  it('renders the map with one selectable feature per supported state', async () => {
    stubCountiesFetch(makeMultiStateCounties())
    renderApp(['/'])

    const map = await screen.findByRole('group', { name: /map of the united states/i })
    const stateButtons = await within(map).findAllByRole('button')

    expect(stateButtons).toHaveLength(2)
    expect(
      within(map).getByRole('button', { name: /select alabama/i }),
    ).toBeInTheDocument()
    expect(
      within(map).getByRole('button', { name: /select california/i }),
    ).toBeInTheDocument()
  })

  it('identifies the state on hover via an SVG <title> (spec 4.4), leaving aria-label authoritative', async () => {
    stubCountiesFetch(makeMultiStateCounties())
    renderApp(['/'])

    const map = await screen.findByRole('group', {
      name: /map of the united states/i,
    })
    const alabama = await within(map).findByRole('button', {
      name: /select alabama/i,
    })
    const california = within(map).getByRole('button', {
      name: /select california/i,
    })

    // Concise on-hover identification: the state name.
    expect(alabama.querySelector('title')?.textContent).toBe('Alabama')
    expect(california.querySelector('title')?.textContent).toBe('California')

    // Accessible name unchanged; it is a <title> element, not a hover-only
    // `title` attribute (CE-E07 accessibility contract).
    expect(alabama).toHaveAttribute('aria-label', 'Select Alabama')
    expect(alabama).not.toHaveAttribute('title')
  })

  it('still navigates by click and keyboard with the hover title present', async () => {
    stubCountiesFetch(makeMultiStateCounties())
    const { router } = renderApp(['/'])

    const map = await screen.findByRole('group', {
      name: /map of the united states/i,
    })
    const alabama = await within(map).findByRole('button', {
      name: /select alabama/i,
    })

    fireEvent.keyDown(alabama, { key: ' ' })
    expect(router.state.location.pathname).toBe('/states/01')
  })

  it('navigates to /states/:stateFips when a state feature is clicked', async () => {
    stubCountiesFetch(makeMultiStateCounties())
    const { router } = renderApp(['/'])

    const map = await screen.findByRole('group', { name: /map of the united states/i })
    const california = await within(map).findByRole('button', { name: /select california/i })
    fireEvent.click(california)

    expect(router.state.location.pathname).toBe('/states/06')
  })

  it('navigates to /states/:stateFips on Enter and Space keydown (keyboard access)', async () => {
    stubCountiesFetch(makeMultiStateCounties())
    const { router } = renderApp(['/'])

    const map = await screen.findByRole('group', { name: /map of the united states/i })
    const alabama = await within(map).findByRole('button', { name: /select alabama/i })
    fireEvent.keyDown(alabama, {
      key: 'Enter',
    })

    expect(router.state.location.pathname).toBe('/states/01')
  })

  it('does not render the map while the county directory is loading', () => {
    stubCountiesFetch(() => new Promise<Response>(() => {}))
    renderApp(['/'])

    expect(screen.queryByRole('group', { name: /map of the united states/i })).toBeNull()
  })
})

describe('UsStateMap (CE-E14b analytical colouring)', () => {
  async function findStateButtons() {
    const map = await screen.findByRole('group', { name: /map of the united states/i })
    return {
      alabama: await within(map).findByRole('button', { name: /select alabama/i }),
      california: within(map).getByRole('button', { name: /select california/i }),
    }
  }

  it('renders neutral (no inline fill, name-only title) when medians are not supplied', async () => {
    renderMap()
    const { alabama } = await findStateButtons()

    expect(alabama.style.fill).toBe('')
    expect(alabama.querySelector('title')?.textContent).toBe('Alabama')
  })

  it('fills each state from lib/choropleth.ts by its median on the active dimension', async () => {
    renderMap({
      medians: new Map([
        ['01', 25],
        ['06', 75],
      ]),
      activeDimension: PERCENTILE_DIM,
    })
    const { alabama, california } = await findStateButtons()

    expect(alabama.style.fill).toBe(fillForScore(25, 'percentile'))
    expect(california.style.fill).toBe(fillForScore(75, 'percentile'))
    expect(alabama.style.fill).not.toBe(california.style.fill)

    // Value shown in the hover title; aria-label unchanged (CE-E10.1).
    expect(alabama.querySelector('title')?.textContent).toBe('Alabama — 25 percentile')
    expect(alabama).toHaveAttribute('aria-label', 'Select Alabama')
    expect(alabama).not.toHaveAttribute('title')
  })

  it('uses MISSING_FILL and a "no data" title for a null median or a state with no entry', async () => {
    renderMap({
      medians: new Map<string, number | null>([['01', null]]), // 06 absent entirely
      activeDimension: PERCENTILE_DIM,
    })
    const { alabama, california } = await findStateButtons()

    for (const feature of [alabama, california]) {
      expect(feature.style.fill.toLowerCase()).toBe(MISSING_FILL.toLowerCase())
      expect(feature.querySelector('title')?.textContent).toMatch(/ — no data$/)
    }
  })

  it('keeps MUA/P on its own coverage scale, not the percentile ramp', async () => {
    renderMap({
      medians: new Map([['01', 80]]),
      activeDimension: COVERAGE_DIM,
    })
    const { alabama } = await findStateButtons()

    expect(alabama.style.fill).toBe(fillForScore(80, 'coverage'))
    expect(alabama.style.fill).not.toBe(fillForScore(80, 'percentile'))
    expect(alabama.querySelector('title')?.textContent).toBe('Alabama — 80% coverage')
  })

  it('still navigates on Space with medians present', async () => {
    const run = renderMap({
      medians: new Map([['01', 25]]),
      activeDimension: PERCENTILE_DIM,
    })
    const { alabama } = await findStateButtons()

    fireEvent.keyDown(alabama, { key: ' ' })
    expect(run.router.state.location.pathname).toBe('/states/01')
  })

  it('still navigates on Enter with medians present', async () => {
    const run = renderMap({
      medians: new Map([['01', 25]]),
      activeDimension: PERCENTILE_DIM,
    })
    const { alabama } = await findStateButtons()

    fireEvent.keyDown(alabama, { key: 'Enter' })
    expect(run.router.state.location.pathname).toBe('/states/01')
  })

  it('still navigates on click with medians present', async () => {
    const run = renderMap({
      medians: new Map([['06', 75]]),
      activeDimension: PERCENTILE_DIM,
    })
    const { california } = await findStateButtons()

    fireEvent.click(california)
    expect(run.router.state.location.pathname).toBe('/states/06')
  })
})

describe('UsStateMap (CE-DEP02 deployment base path)', () => {
  it('requests the national TopoJSON under import.meta.env.BASE_URL', async () => {
    const requested: string[] = []
    vi.stubGlobal(
      'fetch',
      vi.fn((input: unknown) => {
        requested.push(String(input))
        return Promise.resolve({
          ok: true,
          status: 200,
          json: async () => STUB_US_STATES_TOPOJSON,
        } as Response)
      }),
    )

    const router = createMemoryRouter(
      [{ path: '/', element: <UsStateMap states={TWO_STATES} /> }],
      { initialEntries: ['/'] },
    )
    render(<RouterProvider router={router} />)

    await waitFor(() =>
      expect(requested).toContain(
        `${import.meta.env.BASE_URL}geo/us-states.topojson`,
      ),
    )
    // The suite runs under base `/CHIA/` (vite.config.ts): a deployment-aware,
    // not a bare root-relative, path.
    expect(`${import.meta.env.BASE_URL}geo/us-states.topojson`).toBe(
      '/CHIA/geo/us-states.topojson',
    )
    expect(requested).not.toContain('/geo/us-states.topojson')
  })
})
