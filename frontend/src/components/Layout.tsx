import { useEffect, useRef, useState } from 'react'
import type { ReactNode } from 'react'
import { useLocation, useParams } from 'react-router-dom'

import { useCountyDirectory } from '../lib/countyDirectory'
import { deriveStates, stateFipsFromRoute } from '../lib/states'
import { CountySelector } from './CountySelector'
import { StateSelect } from './StateSelect'

export interface LayoutProps {
  /**
   * Optional header content. CE-C01/CE-C02 leave this empty; CE-C03 populates it
   * with the county header (county, state, FIPS, period, completeness).
   */
  header?: ReactNode
  children: ReactNode
}

/**
 * CE-E07 route-change announcement (governing v0.2 UX specification, section
 * 9.4: "a screen-reader user should be able to determine current geographic
 * location").
 *
 * Client-side navigation swaps the page's `<h1>` without moving focus or
 * reloading, so assistive technology is otherwise silent on a state/county
 * transition. This polite live region names the geographic context of the
 * view the user just navigated to.
 *
 * It is a bare `aria-live` region (no `role="status"`) so it never becomes a
 * discoverable landmark and never collides with the genuine `role="status"`
 * loading/not-found messages. The geographic label is derived read-only from
 * the URL plus the already-loaded county directory -- no new state, no page
 * changes, and it degrades to silence for any unrecognized path or before
 * the directory resolves. The first render is intentionally not announced:
 * this reports transitions, not initial page load (which the page's own
 * heading already conveys).
 */
function useGeographicLabel(): string {
  const { pathname } = useLocation()
  const directory = useCountyDirectory()

  if (pathname === '/') return 'United States'

  const stateMatch = pathname.match(/^\/states\/(\d{2})$/)
  if (stateMatch) {
    const inState = directory.counties.find(
      (county) => county.state_fips === stateMatch[1],
    )
    return inState ? inState.state_name : ''
  }

  const countyMatch = pathname.match(/^\/counties\/(\d{5})$/)
  if (countyMatch) {
    const county = directory.counties.find(
      (candidate) => candidate.county_fips === countyMatch[1],
    )
    return county ? `${county.county_name}, ${county.state_name}` : ''
  }

  return ''
}

function RouteAnnouncer() {
  const label = useGeographicLabel()
  const [announcement, setAnnouncement] = useState('')
  const isFirstRun = useRef(true)

  useEffect(() => {
    if (isFirstRun.current) {
      isFirstRun.current = false
      return
    }
    setAnnouncement(label ? `Viewing ${label}` : '')
  }, [label])

  return (
    <div className="visually-hidden" aria-live="polite" aria-atomic="true">
      {announcement}
    </div>
  )
}

/**
 * Application shell: skip link, a polite route-change announcer (CE-E07),
 * the header (title + the CE-E13 `StateSelect`, to the right of the title),
 * the app-level county-selection navigation region (CE-C02, state-gated by
 * CE-E13), and the main content landmark. No Explorer / analytical data is
 * rendered here.
 *
 * CE-E13 puts state selection first: `StateSelect` lives in the header on
 * every route and reflects the state in context (`stateFipsFromRoute`); the
 * county-selection nav that follows it holds the state-gated `CountySelector`.
 * Both derive from the one shared county directory -- no second state or
 * county list.
 */
export function Layout({ header, children }: LayoutProps) {
  const directory = useCountyDirectory()
  const params = useParams<{ stateFips?: string; countyFips?: string }>()
  const ready = directory.status === 'ready'
  const states = ready ? deriveStates(directory.counties) : []
  const currentStateFips = ready
    ? stateFipsFromRoute(directory.counties, params) ?? ''
    : ''

  return (
    <div className="app-shell">
      <a className="skip-link" href="#main-content">
        Skip to main content
      </a>
      <RouteAnnouncer />
      <header className="app-header">
        <div className="app-header__bar">
          <p className="app-title">CHIA County Explorer</p>
          {ready ? <StateSelect states={states} value={currentStateFips} /> : null}
        </div>
        {header ? <div className="app-header__slot">{header}</div> : null}
      </header>
      <nav className="app-county-nav" aria-label="County selection">
        <CountySelector />
      </nav>
      <main id="main-content" className="app-main" tabIndex={-1}>
        {children}
      </main>
    </div>
  )
}
