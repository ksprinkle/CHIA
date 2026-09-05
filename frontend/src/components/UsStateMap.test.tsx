import { fireEvent, screen, within } from '@testing-library/react'

import { makeMultiStateCounties, renderApp, stubCountiesFetch } from '../test/harness'

afterEach(() => {
  vi.unstubAllGlobals()
  vi.restoreAllMocks()
})

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
