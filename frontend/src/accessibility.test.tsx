import { act, fireEvent, screen, waitFor, within } from '@testing-library/react'

import {
  makeCounties,
  makeExplorer,
  makeMultiStateCounties,
  renderApp,
  stubApi,
  stubCountiesFetch,
} from './test/harness'

/**
 * Accessibility validation: CE-C06 keyboard interaction, plus the
 * consolidated CE-E07 accessibility & responsive checks.
 *
 * Most County Explorer controls are native interactive elements -- `<a>`,
 * `<select>`, `<button type="button">`, and `<details>/<summary>` -- whose
 * Enter/Space activation is a browser-guaranteed behavior defined by the HTML
 * specification, not application logic. The two exceptions are the CE-E02 /
 * CE-E03 map features: an SVG `<path role="button">` receives no default
 * keyboard activation, so `UsStateMap` and `StateCountyMap` each attach an
 * explicit `onKeyDown` that activates on Enter/Space (covered by their own
 * component tests). No other component has custom key handling.
 *
 * jsdom has no real input/layout/paint pipeline and no
 * `@testing-library/user-event` here, so these tests do not manufacture fake
 * keydown-triggers-click assertions for native elements. What they verify is
 * application-controlled and real in jsdom:
 *  - every interactive control is a genuine native focusable element
 *    (`element.focus()` + `document.activeElement`);
 *  - controls appear in a sensible document/tab order;
 *  - each control is the correct native tag;
 *  - the click-driven activation path each control relies on is wired to that
 *    same native element;
 *  - (CE-E07) map <-> accessible-selector parity, the route-change live
 *    region, colour-independent values, and landmark/heading structure.
 * Reduced motion is a media-query behavior jsdom cannot execute (the test
 * runner also loads no CSS); it, plus real-browser / screen-reader / viewport
 * checks, is recorded in
 * `Documentation/CE_E07_Accessibility_Responsive_Validation.md.txt`.
 */

afterEach(() => {
  vi.unstubAllGlobals()
  vi.restoreAllMocks()
})

function stubValidCounty() {
  return stubApi({
    counties: makeCounties(['01001', '01003']),
    explorer: (fips) => makeExplorer(fips),
  })
}

describe('CE-C06 keyboard interaction', () => {
  it('places the skip link before the county-selection nav in document order', async () => {
    stubValidCounty()
    renderApp(['/counties/01001'])
    // Let the county-directory fetch settle inside act() before asserting.
    await screen.findByRole('combobox', { name: /county/i })

    const skipLink = screen.getByRole('link', { name: /skip to main content/i })
    const nav = screen.getByRole('navigation', { name: /county selection/i })

    expect(
      skipLink.compareDocumentPosition(nav) & Node.DOCUMENT_POSITION_FOLLOWING,
    ).toBeTruthy()
  })

  it('the skip link, county selector, and main content region are all keyboard-focusable', async () => {
    stubValidCounty()
    renderApp(['/counties/01001'])

    const skipLink = screen.getByRole('link', { name: /skip to main content/i })
    const select = await screen.findByRole('combobox', { name: /county/i })
    const main = screen.getByRole('main')

    // A non-focusable element (e.g. a <div> without a role/tabindex) would
    // not become document.activeElement in jsdom -- this is real
    // focusability, not a stub.
    skipLink.focus()
    expect(document.activeElement).toBe(skipLink)

    select.focus()
    expect(document.activeElement).toBe(select)

    // <main tabIndex={-1}> is deliberately not Tab-reachable but must remain
    // a valid script/fragment-navigation focus target (the skip link's
    // destination).
    main.focus()
    expect(document.activeElement).toBe(main)
  })

  it('every interactive control is a real native element, which is what guarantees Enter/Space activation', async () => {
    stubValidCounty()
    renderApp(['/counties/01001'])

    const select = await screen.findByRole('combobox', { name: /county/i })
    await screen.findByRole('heading', { level: 1 })

    const skipLink = screen.getByRole('link', { name: /skip to main content/i })
    expect(skipLink.tagName).toBe('A')
    expect(skipLink).toHaveAttribute('href', '#main-content')

    expect(select.tagName).toBe('SELECT')

    const summary = screen.getAllByText('Supporting evidence')[0]
    expect(summary.tagName).toBe('SUMMARY')
    expect(summary.closest('details')?.tagName).toBe('DETAILS')
  })

  it('the supporting-evidence disclosure is keyboard-focusable and its native toggle still works', async () => {
    stubValidCounty()
    renderApp(['/counties/01001'])
    await screen.findByRole('heading', { level: 1 })

    const summary = screen.getAllByText('Supporting evidence')[0]
    summary.focus()
    expect(document.activeElement).toBe(summary)

    const details = summary.closest('details') as HTMLDetailsElement
    expect(details.open).toBe(false)
    // Proves the activation path a real Enter/Space press resolves to.
    fireEvent.click(summary)
    expect(details.open).toBe(true)
  })

  it('the retry control is a real native <button>, focusable, and follows the error heading', async () => {
    stubApi({ counties: makeCounties(['01001']), explorer: () => 503 })
    renderApp(['/counties/01001'])

    const alert = await screen.findByRole('alert')
    const heading = within(alert).getByRole('heading', { level: 2 })
    const button = within(alert).getByRole('button', { name: /try again/i })

    expect(button.tagName).toBe('BUTTON')
    expect(button).toHaveAttribute('type', 'button')
    expect(
      heading.compareDocumentPosition(button) & Node.DOCUMENT_POSITION_FOLLOWING,
    ).toBeTruthy()

    button.focus()
    expect(document.activeElement).toBe(button)
  })

  it('the "Return to the start" link is a real, focusable native <a>', async () => {
    stubApi({ counties: makeCounties(['01001']) })
    renderApp(['/counties/99999'])

    const link = await screen.findByRole('link', { name: /return to the start/i })
    expect(link.tagName).toBe('A')
    expect(link).toHaveAttribute('href', '/')

    link.focus()
    expect(document.activeElement).toBe(link)
  })
})

describe('CE-E07 accessibility & responsive validation', () => {
  describe('map <-> accessible-selector parity (spec 9.2; CE-E07 gate)', () => {
    it('the U.S. map and the State selector offer the identical set of states', async () => {
      stubCountiesFetch(makeMultiStateCounties())
      renderApp(['/'])

      const map = await screen.findByRole('group', {
        name: /map of the united states/i,
      })
      await within(map).findAllByRole('button', { name: /^Select / })
      const mapStates = within(map)
        .getAllByRole('button')
        .map((feature) => feature.getAttribute('aria-label')?.replace(/^Select /, ''))
        .sort()

      const select = screen.getByRole('combobox', { name: /^state$/i })
      const optionStates = within(select)
        .getAllByRole('option')
        .filter((option) => (option as HTMLOptionElement).value !== '')
        .map((option) => option.textContent)
        .sort()

      expect(mapStates).toEqual(optionStates)
      expect(mapStates).toEqual(['Alabama', 'California'])
    })

    it('the state county map and the state-scoped county selector offer the identical set of counties', async () => {
      stubCountiesFetch(makeMultiStateCounties())
      renderApp(['/states/01'])

      const map = await screen.findByRole('group', { name: /county map/i })
      await within(map).findAllByRole('button', { name: /^Select / })
      const mapCounties = within(map)
        .getAllByRole('button')
        .map((feature) => feature.getAttribute('aria-label')?.replace(/^Select /, ''))
        .sort()

      const select = await screen.findByRole('combobox', {
        name: /county in alabama/i,
      })
      const optionCounties = within(select)
        .getAllByRole('option')
        .filter((option) => (option as HTMLOptionElement).value !== '')
        .map((option) => option.textContent)
        .sort()

      expect(mapCounties).toEqual(optionCounties)
      expect(mapCounties).toEqual(['Autauga County', 'Baldwin County'])
    })
  })

  describe('route-change announcement (spec 9.4)', () => {
    it('renders a polite live region that is empty on initial load and is not a status landmark', async () => {
      stubCountiesFetch(makeMultiStateCounties())
      const { container } = renderApp(['/'])
      await screen.findByRole('combobox', { name: /^state$/i })

      const liveRegion = container.querySelector('[aria-live="polite"]')
      expect(liveRegion).not.toBeNull()
      expect(liveRegion).toHaveAttribute('aria-atomic', 'true')
      expect(liveRegion).not.toHaveAttribute('role')
      expect(liveRegion?.textContent).toBe('')
    })

    it('announces the state after navigating from the U.S. map', async () => {
      stubCountiesFetch(makeMultiStateCounties())
      const { container } = renderApp(['/'])

      const map = await screen.findByRole('group', {
        name: /map of the united states/i,
      })
      fireEvent.click(
        await within(map).findByRole('button', { name: /select alabama/i }),
      )

      await waitFor(() =>
        expect(
          container.querySelector('[aria-live="polite"]'),
        ).toHaveTextContent('Viewing Alabama'),
      )
    })

    it('announces "county, state" after navigating from the state county map', async () => {
      stubApi({
        counties: makeMultiStateCounties(),
        explorer: (fips) =>
          makeExplorer(fips, { county: { county_name: `County ${fips}` } }),
      })
      const { container } = renderApp(['/states/01'])

      const map = await screen.findByRole('group', { name: /county map/i })
      fireEvent.click(
        await within(map).findByRole('button', { name: /select autauga county/i }),
      )

      await waitFor(() =>
        expect(
          container.querySelector('[aria-live="polite"]'),
        ).toHaveTextContent('Viewing Autauga County, Alabama'),
      )
    })

    it('re-announces the prior geographic context on back navigation', async () => {
      stubApi({
        counties: makeMultiStateCounties(),
        explorer: (fips) =>
          makeExplorer(fips, { county: { county_name: `County ${fips}` } }),
      })
      const { container, router } = renderApp(['/states/01'])

      const map = await screen.findByRole('group', { name: /county map/i })
      fireEvent.click(
        await within(map).findByRole('button', { name: /select autauga county/i }),
      )
      await waitFor(() =>
        expect(
          container.querySelector('[aria-live="polite"]'),
        ).toHaveTextContent('Viewing Autauga County, Alabama'),
      )

      await act(async () => {
        await router.navigate(-1)
      })
      await waitFor(() =>
        expect(
          container.querySelector('[aria-live="polite"]'),
        ).toHaveTextContent('Viewing Alabama'),
      )
    })
  })

  describe('keyboard operability of the CE-E06 drill-down (spec 9.3)', () => {
    it('each "Investigate" disclosure is a real, focusable native <summary>/<details> that toggles on activation', async () => {
      stubApi({
        counties: makeCounties(['01001', '01003']),
        explorer: (fips) => makeExplorer(fips),
      })
      renderApp(['/counties/01001'])
      await screen.findByRole('heading', { level: 1 })

      const summary = screen.getByText('Investigate Primary Care Access')
      expect(summary.tagName).toBe('SUMMARY')
      const details = summary.closest('details') as HTMLDetailsElement
      expect(details.tagName).toBe('DETAILS')

      summary.focus()
      expect(document.activeElement).toBe(summary)

      expect(details.open).toBe(false)
      fireEvent.click(summary)
      expect(details.open).toBe(true)
    })

    it('the breadcrumb trail is built from real native links', async () => {
      stubApi({
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
      renderApp(['/counties/01001'])
      const breadcrumb = await screen.findByRole('navigation', {
        name: /breadcrumb/i,
      })

      const links = within(breadcrumb).getAllByRole('link')
      expect(links.map((link) => link.tagName)).toEqual(['A', 'A'])
      expect(links[0]).toHaveAttribute('href', '/')
      expect(links[1]).toHaveAttribute('href', '/states/01')
    })
  })

  describe('information available without colour or graphics (spec 9.5, 12.12)', () => {
    it('every dimension value and unit is plain text; the CE-E05 indicators are aria-hidden decoration', async () => {
      stubApi({
        counties: makeCounties(['01001', '01003']),
        explorer: (fips) => makeExplorer(fips),
      })
      renderApp(['/counties/01001'])
      const snapshot = await screen.findByRole('region', {
        name: /healthcare access snapshot/i,
      })

      expect(within(snapshot).getAllByText('percentile')).toHaveLength(3)
      expect(within(snapshot).getByText('% coverage')).toBeInTheDocument()
      expect(within(snapshot).getByText('88')).toBeInTheDocument()

      const indicators = [
        ...snapshot.querySelectorAll('.percentile-indicator'),
        ...snapshot.querySelectorAll('.coverage-indicator'),
      ]
      expect(indicators.length).toBeGreaterThan(0)
      for (const indicator of indicators) {
        expect(indicator).toHaveAttribute('aria-hidden', 'true')
      }
    })

    it('an unavailable dimension is distinguished from a genuine zero by text', async () => {
      stubApi({
        counties: makeCounties(['01001', '01003']),
        explorer: (fips) =>
          makeExplorer(fips, {
            dimensions: {
              primary_care: {
                available: true,
                score: 0,
                primary_measure: { normalized_value: 0 },
              },
              dental: { available: false, score: null, score_status: null },
            },
          }),
      })
      renderApp(['/counties/01001'])
      const snapshot = await screen.findByRole('region', {
        name: /healthcare access snapshot/i,
      })

      expect(within(snapshot).getByText('0')).toBeInTheDocument()
      expect(within(snapshot).getByText('Not available')).toBeInTheDocument()
    })
  })

  describe('landmark and heading structure (spec 9.4)', () => {
    it.each([
      ['/', /chia county explorer/i],
      ['/states/01', /^alabama$/i],
      ['/counties/01001', /autauga county/i],
    ])('%s exposes a single h1, the main landmark, and named regions', async (path, h1) => {
      stubApi({
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
      renderApp([path])

      expect(
        await screen.findByRole('heading', { level: 1, name: h1 }),
      ).toBeInTheDocument()
      expect(screen.getAllByRole('heading', { level: 1 })).toHaveLength(1)
      expect(screen.getByRole('main')).toHaveAttribute('id', 'main-content')
      expect(screen.getAllByRole('region').length).toBeGreaterThan(0)
    })
  })

  describe('no essential information depends on hover (spec 9.10)', () => {
    it('map features expose their name through an accessible name, not a hover-only title', async () => {
      stubCountiesFetch(makeMultiStateCounties())
      renderApp(['/'])

      const map = await screen.findByRole('group', {
        name: /map of the united states/i,
      })
      const features = within(map).getAllByRole('button')
      expect(features.length).toBeGreaterThan(0)
      for (const feature of features) {
        expect(feature.getAttribute('aria-label')).toMatch(/^Select /)
        expect(feature).not.toHaveAttribute('title')
      }
    })
  })
})
