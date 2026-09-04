import { fireEvent, screen, within } from '@testing-library/react'

import { makeMultiStateCounties, renderApp, stubCountiesFetch } from '../test/harness'

afterEach(() => {
  vi.unstubAllGlobals()
  vi.restoreAllMocks()
})

describe('StateSelect (CE-E02)', () => {
  it('populates a labelled native select with one option per supported state', async () => {
    stubCountiesFetch(makeMultiStateCounties())
    renderApp(['/'])

    const select = await screen.findByRole('combobox', { name: /^state$/i })
    const options = within(select).getAllByRole('option')

    // placeholder + 2 states
    expect(options).toHaveLength(3)
    expect(options[0]).toBeDisabled()
    expect(options[1]).toHaveTextContent('Alabama')
    expect(options[2]).toHaveTextContent('California')
  })

  it('navigates to /states/:stateFips when a state is chosen', async () => {
    stubCountiesFetch(makeMultiStateCounties())
    const { router } = renderApp(['/'])

    const select = await screen.findByRole('combobox', { name: /^state$/i })
    fireEvent.change(select, { target: { value: '06' } })

    expect(router.state.location.pathname).toBe('/states/06')
  })

  it('always renders unselected (no persistent selection on the landing page)', async () => {
    stubCountiesFetch(makeMultiStateCounties())
    renderApp(['/'])

    const select = (await screen.findByRole('combobox', {
      name: /^state$/i,
    })) as HTMLSelectElement
    expect(select.value).toBe('')
  })

  it('does not render while the county directory is loading', () => {
    stubCountiesFetch(() => new Promise<Response>(() => {}))
    renderApp(['/'])

    expect(screen.queryByRole('combobox', { name: /^state$/i })).toBeNull()
  })
})
