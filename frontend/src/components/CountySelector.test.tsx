import { fireEvent, screen, waitFor, within } from '@testing-library/react'

import { makeCounties, renderApp, stubCountiesFetch } from '../test/harness'

afterEach(() => {
  vi.unstubAllGlobals()
  vi.restoreAllMocks()
})

/** The app-level county selector lives in the "County selection" nav; the
 *  state route also renders a separate "County in <state>" control, so scope
 *  every lookup to the nav (and use the exact "County" name) to stay
 *  unambiguous. */
function countySelectorNav() {
  return screen.getByRole('navigation', { name: /county selection/i })
}

async function findCountySelect(): Promise<HTMLSelectElement> {
  return (await within(countySelectorNav()).findByRole('combobox', {
    name: /^county$/i,
  })) as HTMLSelectElement
}

describe('CountySelector (CE-C02, state-gated by CE-E13)', () => {
  it('shows a loading state before the county list resolves', () => {
    // Hold the request pending so the loading state is observed deterministically
    // and no post-assertion state update escapes act().
    stubCountiesFetch(() => new Promise<Response>(() => {}))
    renderApp(['/'])
    // CE-E02: the U.S. map landing page (HomePage) also reflects the same
    // shared directory loading state as its own separate "status" region.
    expect(screen.getAllByRole('status').length).toBeGreaterThan(0)
    expect(screen.getByText(/loading counties/i)).toBeInTheDocument()
    expect(screen.queryByRole('combobox')).toBeNull()
  })

  it('is disabled with a "Select a state first" placeholder on the landing page', async () => {
    stubCountiesFetch(makeCounties(['01001', '01003', '06075']))
    renderApp(['/'])

    const select = await findCountySelect()
    expect(select).toBeDisabled()
    const options = within(select).getAllByRole('option')
    expect(options).toHaveLength(1)
    expect(options[0]).toHaveTextContent(/select a state first/i)
  })

  it('once a state is in the route, lists only that state’s counties', async () => {
    stubCountiesFetch(makeCounties(['01001', '01003', '06075']))
    renderApp(['/states/01'])

    const select = await findCountySelect()
    expect(select).toBeEnabled()

    const options = within(select).getAllByRole('option')
    // placeholder + the two Alabama counties; the California county is excluded
    expect(options).toHaveLength(3)
    expect(options[0]).toBeDisabled()
    expect(options[1]).toHaveTextContent('0 — 01001')
    expect(options[2]).toHaveTextContent('0 — 01003')
    expect(within(select).queryByText(/06075/)).toBeNull()
  })

  it('derives the state from a county route and scopes the options to it', async () => {
    stubCountiesFetch(makeCounties(['01001', '01003', '06075']))
    renderApp(['/counties/01001'])

    const select = await findCountySelect()
    expect(select).toBeEnabled()
    expect(select.value).toBe('01001')
    expect(
      within(select)
        .getAllByRole('option')
        .filter((o) => (o as HTMLOptionElement).value !== ''),
    ).toHaveLength(2)
  })

  it('navigates to /counties/:fips when a county is chosen from a state route', async () => {
    stubCountiesFetch(makeCounties(['01001', '01003']))
    const { router } = renderApp(['/states/01'])

    const select = await findCountySelect()
    fireEvent.change(select, { target: { value: '01003' } })

    await waitFor(() =>
      expect(router.state.location.pathname).toBe('/counties/01003'),
    )
  })

  it('falls back to the disabled placeholder when the URL FIPS is not a known county', async () => {
    stubCountiesFetch(makeCounties(['01001', '01003']))
    renderApp(['/counties/99999'])

    const select = await findCountySelect()
    expect(select).toBeDisabled()
    expect(select.value).toBe('')
    expect(
      within(select).getByRole('option'),
    ).toHaveTextContent(/select a state first/i)
  })

  it('shows an alert with retry when the county list fails to load', async () => {
    stubCountiesFetch(new TypeError('network down'))
    renderApp(['/'])

    // CE-E02: HomePage also renders its own alert for the same shared
    // directory error; find the county-selector-specific one by its exact
    // wording.
    await waitFor(() => expect(screen.getAllByRole('alert').length).toBeGreaterThan(0))
    const alert = screen
      .getAllByRole('alert')
      .find((el) => /the list of counties could not be loaded/i.test(el.textContent ?? ''))
    expect(alert).toBeTruthy()
    expect(
      within(alert as HTMLElement).getByRole('button', { name: /try again/i }),
    ).toBeInTheDocument()
  })

  it('shows an explicit message (not an alert) when the county list is empty', async () => {
    stubCountiesFetch(makeCounties([]))
    renderApp(['/'])

    await waitFor(() =>
      expect(screen.getByText(/no counties are available/i)).toBeInTheDocument(),
    )
    expect(screen.queryByRole('alert')).toBeNull()
    expect(screen.queryByRole('combobox')).toBeNull()
  })
})
