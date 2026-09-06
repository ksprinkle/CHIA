import { fireEvent, screen, waitFor, within } from '@testing-library/react'

import { fillForScore } from '../lib/choropleth'
import {
  STUB_US_STATES_TOPOJSON,
  makeMultiStateCounties,
  renderApp,
  stubApi,
  stubCountiesFetch,
} from '../test/harness'

afterEach(() => {
  vi.unstubAllGlobals()
  vi.restoreAllMocks()
})

function jsonResponse(body: unknown, ok = true, status = 200): Response {
  return { ok, status, json: async () => body } as Response
}

async function findUsMap() {
  return screen.findByRole('group', { name: /map of the united states/i })
}

/** The US map renders its state <button>s asynchronously (TopoJSON fetch). */
async function findState(name: RegExp) {
  return within(await findUsMap()).findByRole('button', { name })
}

function enterMeasureMode() {
  fireEvent.click(screen.getByRole('button', { name: /colour states by a measure/i }))
}

describe('HomePage (CE-E14b national-map measure view)', () => {
  it('starts in navigation mode: no measure selector, legend, or state table', async () => {
    stubCountiesFetch(makeMultiStateCounties())
    renderApp(['/'])

    const alabama = await findState(/select alabama/i)
    expect(alabama.style.fill).toBe('') // neutral, no analytical fill

    expect(
      screen.getByRole('button', { name: /colour states by a measure/i }),
    ).toBeInTheDocument()
    expect(screen.queryByRole('combobox', { name: /colour states by/i })).toBeNull()
    expect(screen.queryByRole('region', { name: /map legend/i })).toBeNull()
    expect(screen.queryByText(/view state data table/i)).toBeNull()
    expect(screen.queryByText(/median of its counties/i)).toBeNull()
  })

  it('entering measure mode colours the states from the national medians and shows the legend + table + label', async () => {
    stubCountiesFetch(makeMultiStateCounties())
    renderApp(['/'])
    await findState(/select alabama/i)

    enterMeasureMode()

    const selector = await screen.findByRole('combobox', { name: /colour states by/i })
    expect((selector as HTMLSelectElement).value).toBe('primary_care')

    // Default fixture: state 01 primary_care median 25 -> ramp colour.
    await waitFor(async () => {
      expect((await findState(/select alabama/i)).style.fill).toBe(
        fillForScore(25, 'percentile'),
      )
    })

    expect(
      screen.getByRole('region', { name: /map legend: primary care access/i }),
    ).toBeInTheDocument()
    expect(screen.getByText(/each state is coloured by the/i)).toHaveTextContent(
      /median of its counties/i,
    )

    fireEvent.click(screen.getByText(/view state data table/i))
    const table = screen.getByRole('table', { name: /median of each state/i })
    expect(within(table).getByRole('row', { name: /alabama/i })).toHaveTextContent(
      '25 percentile',
    )
    expect(within(table).getByRole('row', { name: /california/i })).toHaveTextContent(
      '75 percentile',
    )
  })

  it('switching to MUA/P recolours on the coverage scale and updates the legend', async () => {
    stubCountiesFetch(makeMultiStateCounties())
    renderApp(['/'])
    await findState(/select alabama/i)
    enterMeasureMode()

    const selector = await screen.findByRole('combobox', { name: /colour states by/i })
    fireEvent.change(selector, { target: { value: 'mua_p' } })

    await waitFor(async () => {
      const alabama = await findState(/select alabama/i)
      // Default fixture: state 01 mua_p median 80, on the coverage ramp.
      expect(alabama.style.fill).toBe(fillForScore(80, 'coverage'))
      expect(alabama.style.fill).not.toBe(fillForScore(80, 'percentile'))
    })
    expect(
      screen.getByRole('region', { name: /map legend: mua\/p access/i }),
    ).toBeInTheDocument()
  })

  it('"Return to navigation" clears the analytical layer', async () => {
    stubCountiesFetch(makeMultiStateCounties())
    renderApp(['/'])
    await findState(/select alabama/i)
    enterMeasureMode()
    await screen.findByRole('combobox', { name: /colour states by/i })
    await waitFor(async () =>
      expect((await findState(/select alabama/i)).style.fill).not.toBe(''),
    )

    fireEvent.click(screen.getByRole('button', { name: /return to navigation/i }))

    expect((await findState(/select alabama/i)).style.fill).toBe('')
    expect(screen.queryByRole('combobox', { name: /colour states by/i })).toBeNull()
    expect(screen.queryByRole('region', { name: /map legend/i })).toBeNull()
    expect(
      screen.getByRole('button', { name: /colour states by a measure/i }),
    ).toBeInTheDocument()
  })

  it('shows a polite status while the national medians load and keeps the map neutral', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn((url: unknown) => {
        const u = String(url)
        if (u.includes('/geo/')) return Promise.resolve(jsonResponse(STUB_US_STATES_TOPOJSON))
        if (u.includes('/states/dimension-scores')) return new Promise<Response>(() => {})
        if (u.includes('/counties')) return Promise.resolve(jsonResponse(makeMultiStateCounties()))
        return Promise.resolve(jsonResponse({}, false, 404))
      }),
    )
    renderApp(['/'])
    await findState(/select alabama/i)
    enterMeasureMode()

    expect(await screen.findByRole('status')).toHaveTextContent(
      /loading state map colours/i,
    )
    expect((await findState(/select alabama/i)).style.fill).toBe('')
  })

  it('surfaces an error with retry when the national medians fail; navigation still works', async () => {
    stubApi({ counties: makeMultiStateCounties(), nationalScores: () => 503 })
    const { router } = renderApp(['/'])
    await findState(/select alabama/i)
    enterMeasureMode()

    const alert = await screen.findByRole('alert')
    expect(alert).toHaveTextContent(/state map colours could not be loaded/i)
    expect(within(alert).getByRole('button', { name: /try again/i })).toBeInTheDocument()

    fireEvent.click(await findState(/select alabama/i))
    await waitFor(() => expect(router.state.location.pathname).toBe('/states/01'))
  })
})
