import { act, fireEvent, screen, waitFor, within } from '@testing-library/react'

import {
  makeExplorer,
  makeMultiStateCounties,
  renderApp,
  stubApi,
} from './test/harness'

/**
 * CE-E08 — End-to-End Acceptance (governing v0.2 UX specification §14
 * "CE-E08", journey defined in §3.1).
 *
 * A single continuous flow through the whole redesigned County Explorer:
 *
 *   U.S. map -> select a state ON THE MAP
 *            -> select a county ON THE MAP
 *            -> Visual County Profile
 *            -> a Dimension
 *            -> its Evidence, Underlying Data, Methodology, Provenance
 *
 * with the geographic context (breadcrumb + CE-E07 route announcement)
 * asserted at the destination and on the way back (§3.5, §3.8).
 *
 * The individual stages already have dedicated unit coverage in
 * `routing.test.tsx` (CE-E02/E03), `CountyPage.test.tsx` (CE-C03..CE-E06),
 * and `accessibility.test.tsx` (CE-E07). This file's contribution is proving
 * they connect as one uninterrupted journey. It adds no product behaviour.
 *
 * The CE-D01 analytical foundation is verified separately and out-of-band
 * (backend suite + the v0.1 analytical validators + a git/md5 immutability
 * check); see `Documentation/CE_E08_EndToEnd_Acceptance.md.txt`.
 */

afterEach(() => {
  vi.unstubAllGlobals()
  vi.restoreAllMocks()
})

/**
 * Autauga County, Alabama (01001) reached from the two-state fixture; the
 * Explorer payload carries the same identity so the profile header,
 * breadcrumb, and route announcement all agree.
 */
function stubJourney() {
  return stubApi({
    counties: makeMultiStateCounties(),
    explorer: (fips) =>
      makeExplorer(fips, {
        county: {
          county_name: 'Autauga County',
          state_name: 'Alabama',
          state_abbr: 'AL',
        },
      }),
  })
}

async function driveUsMapToCountyProfile() {
  renderApp(['/'])

  const usMap = await screen.findByRole('group', {
    name: /map of the united states/i,
  })
  fireEvent.click(
    await within(usMap).findByRole('button', { name: /select alabama/i }),
  )

  const stateMap = await screen.findByRole('group', { name: /county map/i })
  await screen.findByRole('heading', { level: 1, name: /^alabama$/i })
  fireEvent.click(
    await within(stateMap).findByRole('button', {
      name: /select autauga county/i,
    }),
  )

  return screen.findByRole('heading', { level: 1, name: /autauga county/i })
}

describe('CE-E08 end-to-end acceptance', () => {
  it('completes the geography-first journey from the U.S. map to the County Profile, entirely by map selection', async () => {
    const fetchMock = stubJourney()
    const { container, router } = renderApp(['/'])

    // U.S. map -> state.
    const usMap = await screen.findByRole('group', {
      name: /map of the united states/i,
    })
    fireEvent.click(
      await within(usMap).findByRole('button', { name: /select alabama/i }),
    )
    await waitFor(() =>
      expect(router.state.location.pathname).toBe('/states/01'),
    )
    await screen.findByRole('heading', { level: 1, name: /^alabama$/i })

    // State map -> county.
    const stateMap = await screen.findByRole('group', { name: /county map/i })
    fireEvent.click(
      await within(stateMap).findByRole('button', {
        name: /select autauga county/i,
      }),
    )
    await waitFor(() =>
      expect(router.state.location.pathname).toBe('/counties/01001'),
    )
    await screen.findByRole('heading', { level: 1, name: /autauga county/i })

    // Geographic context is visible (breadcrumb) and announced (CE-E07).
    const breadcrumb = screen.getByRole('navigation', { name: /breadcrumb/i })
    expect(
      within(breadcrumb).getByRole('link', { name: /^united states$/i }),
    ).toHaveAttribute('href', '/')
    expect(
      within(breadcrumb).getByRole('link', { name: /^alabama$/i }),
    ).toHaveAttribute('href', '/states/01')
    expect(
      within(breadcrumb).getByText('Autauga County', {
        selector: '[aria-current="page"]',
      }),
    ).toBeInTheDocument()
    await waitFor(() =>
      expect(container.querySelector('[aria-live="polite"]')).toHaveTextContent(
        'Viewing Autauga County, Alabama',
      ),
    )

    // The Explorer read model was fetched exactly once, for this county.
    expect(
      fetchMock.mock.calls
        .map((call) => String(call[0]))
        .filter((url) => url.includes('/explorer')),
    ).toEqual(['/api/v1/counties/01001/explorer'])

    // Visual Profile: the four-dimension snapshot is present.
    const snapshot = screen.getByRole('region', {
      name: /healthcare access snapshot/i,
    })
    for (const name of [
      'Primary Care Access',
      'Dental Access',
      'Mental Health Access',
      'MUA/P Access',
    ]) {
      expect(within(snapshot).getByText(name)).toBeInTheDocument()
    }
    expect(within(snapshot).getAllByText('percentile')).toHaveLength(3)
    expect(within(snapshot).getByText('% coverage')).toBeInTheDocument()
  })

  it('reaches a dimension and its full analytical trail (result -> underlying data -> evidence -> methodology -> provenance) from the map-driven arrival', async () => {
    stubJourney()
    await driveUsMapToCountyProfile()

    // Dimension result is visible without any interaction.
    const dimensions = screen.getByRole('region', { name: /access dimensions/i })
    const primaryCareHeading = within(dimensions).getByRole('heading', {
      level: 3,
      name: 'Primary Care Access',
    })
    const card = primaryCareHeading.closest('li') as HTMLElement
    expect(
      within(card).getByText('88', { selector: '.dimension__score-value' }),
    ).toBeInTheDocument()

    // Drill down: one native disclosure, opened by the user.
    const disclosure = within(card).getByText('Investigate Primary Care Access')
    const details = disclosure.closest('details') as HTMLDetailsElement
    expect(details.open).toBe(false)
    fireEvent.click(disclosure)
    expect(details.open).toBe(true)

    // Underlying data.
    expect(
      within(details).getByText('Primary Care Access primary measure'),
    ).toBeInTheDocument()
    // Evidence.
    expect(within(details).getByText('Supporting evidence')).toBeInTheDocument()
    // Methodology, scoped to this dimension.
    expect(
      within(details).getByText('Primary Care Access calculation method.'),
    ).toBeInTheDocument()
    expect(
      within(details).queryByText('Dental Access calculation method.'),
    ).toBeNull()
    // Provenance, scoped to this dimension's source.
    expect(within(details).getByText('Primary Care HPSA')).toBeInTheDocument()
    expect(within(details).queryByText('Dental HPSA')).toBeNull()

    // The comprehensive page-level Methodology and Sources panels remain.
    expect(
      screen.getByRole('region', { name: /methodology/i }),
    ).toBeInTheDocument()
    expect(screen.getByRole('region', { name: /sources/i })).toBeInTheDocument()
  })

  it('preserves and re-announces the geographic context on backward navigation', async () => {
    stubJourney()
    const { container, router } = renderApp(['/'])

    const usMap = await screen.findByRole('group', {
      name: /map of the united states/i,
    })
    fireEvent.click(
      await within(usMap).findByRole('button', { name: /select alabama/i }),
    )
    const stateMap = await screen.findByRole('group', { name: /county map/i })
    fireEvent.click(
      await within(stateMap).findByRole('button', {
        name: /select autauga county/i,
      }),
    )
    await screen.findByRole('heading', { level: 1, name: /autauga county/i })
    await waitFor(() =>
      expect(container.querySelector('[aria-live="polite"]')).toHaveTextContent(
        'Viewing Autauga County, Alabama',
      ),
    )

    // County -> State.
    await act(async () => {
      await router.navigate(-1)
    })
    await waitFor(() =>
      expect(router.state.location.pathname).toBe('/states/01'),
    )
    expect(
      await screen.findByRole('heading', { level: 1, name: /^alabama$/i }),
    ).toBeInTheDocument()
    await waitFor(() =>
      expect(container.querySelector('[aria-live="polite"]')).toHaveTextContent(
        'Viewing Alabama',
      ),
    )

    // State -> U.S. map.
    await act(async () => {
      await router.navigate(-1)
    })
    await waitFor(() => expect(router.state.location.pathname).toBe('/'))
    expect(
      await screen.findByRole('heading', { level: 1, name: /chia county explorer/i }),
    ).toBeInTheDocument()
    expect(
      screen.getByRole('group', { name: /map of the united states/i }),
    ).toBeInTheDocument()
  })
})
