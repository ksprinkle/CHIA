import type { ReactNode } from 'react'

export interface LayoutProps {
  /**
   * Optional header content. CE-C01 leaves this empty; CE-C03 populates it with
   * the county header (county, state, FIPS, period, completeness).
   */
  header?: ReactNode
  children: ReactNode
}

/**
 * Application shell: skip link, header region (with an empty slot for CE-C03),
 * and the main content landmark. No county or analytical data is rendered here.
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
      <main id="main-content" className="app-main" tabIndex={-1}>
        {children}
      </main>
    </div>
  )
}
