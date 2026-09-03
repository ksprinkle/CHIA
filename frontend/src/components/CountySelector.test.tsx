import { fireEvent, screen, waitFor, within } from '@testing-library/react'

import { makeCounties, renderApp, stubCountiesFetch } from '../test/harness'

afterEach(() => {
  vi.unstubAllGlobals()
  vi.restoreAllMocks()
})

describe('CountySelector (CE-C02)', () => {
  it('shows a loading state before the county list resolves', () => {
    // Hold the request pending so the loading state is observed deterministically
    // and no post-assertion state update escapes act().
    stubCountiesFetch(() => new Promise<Response>(() => {}))
    renderApp(['/'])
    expect(screen.getByRole('status')).toHaveTextContent(/loading counties/i)
    expect(screen.queryByRole('combobox')).toBeNull()
  })

  it('populates a labelled native select with one option per county', async () => {
    stubCountiesFetch(makeCounties(['01001', '01003', '06075']))
    renderApp(['/'])

    const select = await screen.findByRole('combobox', { name: /county/i })
    const options = within(select).getAllByRole('option')
    // placeholder + 3 counties
    expect(options).toHaveLength(4)
    expect(options[0]).toBeDisabled()
    expect(options[1]).toHaveTextContent('0 — 01001')
    expect(options[3]).toHaveTextContent('0 — 06075')
  })

  it('navigates to /counties/:fips when a county is chosen', async () => {
    stubCountiesFetch(makeCounties(['01001', '01003']))
    const { router } = renderApp(['/'])

    const select = await screen.findByRole('combobox', { name: /county/i })
    fireEvent.change(select, { target: { value: '01003' } })

    await waitFor(() =>
      expect(router.state.location.pathname).toBe('/counties/01003'),
    )
  })

  it('reflects the URL FIPS as the selected value on direct navigation', async () => {
    stubCountiesFetch(makeCounties(['01001', '01003']))
    renderApp(['/counties/01003'])

    const select = (await screen.findByRole('combobox', {
      name: /county/i,
    })) as HTMLSelectElement
    expect(select.value).toBe('01003')
  })

  it('falls back to the placeholder when the URL FIPS is not a known county', async () => {
    stubCountiesFetch(makeCounties(['01001', '01003']))
    renderApp(['/counties/99999'])

    const select = (await screen.findByRole('combobox', {
      name: /county/i,
    })) as HTMLSelectElement
    expect(select.value).toBe('')
  })

  it('shows an alert with retry when the county list fails to load', async () => {
    stubCountiesFetch(new TypeError('network down'))
    renderApp(['/'])

    const alert = await screen.findByRole('alert')
    expect(alert).toHaveTextContent(/could not be loaded/i)
    expect(
      within(alert).getByRole('button', { name: /try again/i }),
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
