import { fireEvent, screen, waitFor, within } from '@testing-library/react'

import { makeMultiStateCounties, renderApp, stubCountiesFetch } from '../test/harness'

afterEach(() => {
  vi.unstubAllGlobals()
  vi.restoreAllMocks()
})

/**
 * CE-E13 -- State/County selector reordering & state-gated county selection.
 *
 * State selection comes first: `StateSelect` sits in the app header (right of
 * the title), the county-selection nav follows it, and the county selector is
 * disabled until a state is in context and then scoped to that state.
 */
describe('Layout (CE-E13 selector order & state gating)', () => {
  it('places the State selector in the header, and the county-selection nav after it', async () => {
    stubCountiesFetch(makeMultiStateCounties())
    renderApp(['/'])

    const banner = screen.getByRole('banner')
    const stateSelect = await within(banner).findByRole('combobox', {
      name: /^state$/i,
    })
    expect(stateSelect).toBeInTheDocument()

    // The title precedes the State selector within the header.
    const title = within(banner).getByText('CHIA County Explorer')
    expect(
      title.compareDocumentPosition(stateSelect) &
        Node.DOCUMENT_POSITION_FOLLOWING,
    ).toBeTruthy()

    // State (header) precedes County (nav) in the selection flow.
    const countyNav = screen.getByRole('navigation', { name: /county selection/i })
    expect(
      banner.compareDocumentPosition(countyNav) &
        Node.DOCUMENT_POSITION_FOLLOWING,
    ).toBeTruthy()
    const countySelect = within(countyNav).getByRole('combobox', {
      name: /^county$/i,
    })
    expect(
      stateSelect.compareDocumentPosition(countySelect) &
        Node.DOCUMENT_POSITION_FOLLOWING,
    ).toBeTruthy()
  })

  it('on "/", the State selector is unset and the County selector is disabled', async () => {
    stubCountiesFetch(makeMultiStateCounties())
    renderApp(['/'])

    const stateSelect = (await screen.findByRole('combobox', {
      name: /^state$/i,
    })) as HTMLSelectElement
    expect(stateSelect.value).toBe('')

    const countySelect = within(
      screen.getByRole('navigation', { name: /county selection/i }),
    ).getByRole('combobox', { name: /^county$/i })
    expect(countySelect).toBeDisabled()
    expect(within(countySelect).getByRole('option')).toHaveTextContent(
      /select a state first/i,
    )
  })

  it('choosing a state in the header enables the County selector and scopes it to that state', async () => {
    stubCountiesFetch(makeMultiStateCounties())
    const { router } = renderApp(['/'])

    const stateSelect = await screen.findByRole('combobox', { name: /^state$/i })
    fireEvent.change(stateSelect, { target: { value: '01' } })

    await waitFor(() =>
      expect(router.state.location.pathname).toBe('/states/01'),
    )

    const countySelect = within(
      screen.getByRole('navigation', { name: /county selection/i }),
    ).getByRole('combobox', { name: /^county$/i })
    expect(countySelect).toBeEnabled()

    const options = within(countySelect)
      .getAllByRole('option')
      .filter((o) => (o as HTMLOptionElement).value !== '')
    // Alabama's two counties only (California's 06075 is excluded).
    expect(options.map((o) => (o as HTMLOptionElement).value)).toEqual([
      '01001',
      '01003',
    ])
  })

  it('on a state route, the header State selector reflects the state in context', async () => {
    stubCountiesFetch(makeMultiStateCounties())
    renderApp(['/states/06'])

    const stateSelect = (await screen.findByRole('combobox', {
      name: /^state$/i,
    })) as HTMLSelectElement
    expect(stateSelect.value).toBe('06')
  })

  it('on a county route, both selectors reflect the county and its state', async () => {
    stubCountiesFetch(makeMultiStateCounties())
    renderApp(['/counties/06075'])

    const stateSelect = (await screen.findByRole('combobox', {
      name: /^state$/i,
    })) as HTMLSelectElement
    expect(stateSelect.value).toBe('06')

    const countySelect = (await within(
      screen.getByRole('navigation', { name: /county selection/i }),
    ).findByRole('combobox', { name: /^county$/i })) as HTMLSelectElement
    expect(countySelect).toBeEnabled()
    expect(countySelect.value).toBe('06075')
    expect(
      within(countySelect)
        .getAllByRole('option')
        .filter((o) => (o as HTMLOptionElement).value !== ''),
    ).toHaveLength(1)
  })

  it('keeps visible <label>s on both selectors', async () => {
    stubCountiesFetch(makeMultiStateCounties())
    renderApp(['/states/01'])

    // getByRole name comes from the associated <label>, so a match proves the
    // label element exists and is wired via htmlFor/id.
    expect(await screen.findByRole('combobox', { name: /^state$/i })).toHaveAttribute(
      'id',
      'state-select',
    )
    expect(
      within(screen.getByRole('navigation', { name: /county selection/i })).getByRole(
        'combobox',
        { name: /^county$/i },
      ),
    ).toHaveAttribute('id', 'county-select')
  })
})
