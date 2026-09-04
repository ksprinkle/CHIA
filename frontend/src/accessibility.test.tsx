import { fireEvent, screen, within } from '@testing-library/react'

import { makeCounties, makeExplorer, renderApp, stubApi } from './test/harness'

/**
 * CE-C06 keyboard-interaction validation.
 *
 * The County Explorer uses only native interactive elements -- `<a>`,
 * `<select>`, `<button type="button">`, and `<details>/<summary>` -- with no
 * custom keyboard handling (`onKeyDown`/`onKeyUp`/`onKeyPress`) anywhere in
 * the application. Enter/Space activation of a native `<button>`, `<summary>`,
 * and `<a href>` is a browser-guaranteed behavior defined by the HTML
 * specification, not application logic: jsdom does not simulate the browser's
 * default keyboard-to-activation behavior (there is no real input/layout
 * pipeline here, and no `@testing-library/user-event` in this project to
 * approximate it), so this file does not manufacture a fake keydown-triggers-
 * click test that would not actually prove anything a real browser does.
 *
 * What IS both application-controlled and meaningfully verifiable in jsdom:
 *  - every interactive control is a genuine native focusable element
 *    (`element.focus()` + `document.activeElement`, which jsdom's real
 *    focusability rules do enforce);
 *  - controls appear in a sensible document/tab order;
 *  - each control is actually the correct native tag (which is what makes
 *    Enter/Space activation apply in a real browser in the first place);
 *  - the click-driven activation path each control relies on (already proven
 *    by the CE-C01/CE-C02/CE-C04 test suites) is wired to that same native
 *    element.
 * That combination is the honest jsdom-level proof of keyboard operability.
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
