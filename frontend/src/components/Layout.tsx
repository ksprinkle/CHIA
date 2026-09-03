import type { ReactNode } from 'react'

import { CountySelector } from './CountySelector'

export interface LayoutProps {
  /**
   * Optional header content. CE-C01/CE-C02 leave this empty; CE-C03 populates it
   * with the county header (county, state, FIPS, period, completeness).
   */
  header?: ReactNode
  children: ReactNode
}

/**
 * Application shell: skip link, header region (with an empty slot for CE-C03),
 * an app-level county-selection navigation region (CE-C02), and the main content
 * landmark. No Explorer / analytical data is rendered here.
 */
export function Layout({ header, children }: LayoutProps) {
  return (
    <div className="app-shell">
      <a className="skip-link" href="#main-content">
        Skip to main content
      </a>
      <header className="app-header">
        <p className="app-title">CHIA County Explorer</p>
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
