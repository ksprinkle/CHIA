import type { ReactNode } from 'react'
import type { RouteObject } from 'react-router-dom'
import { createBrowserRouter } from 'react-router-dom'

import { Layout } from './components/Layout'
import { NotFound } from './components/NotFound'
import { CountyPage } from './pages/CountyPage'
import { HomePage } from './pages/HomePage'
import { StatePage } from './pages/StatePage'

function withLayout(children: ReactNode): ReactNode {
  return <Layout>{children}</Layout>
}

/**
 * Route table. `/` is the U.S. map landing page (CE-E02); `/states/:stateFips`
 * is the state route (CE-E02 placeholder; the county-level map is CE-E03);
 * `/counties/:countyFips` is the county route (selection acknowledgement in
 * CE-C02; profile in CE-C03). Exported so tests can build a deterministic
 * `createMemoryRouter`.
 */
export const routes: RouteObject[] = [
  { path: '/', element: withLayout(<HomePage />) },
  { path: '/states/:stateFips', element: withLayout(<StatePage />) },
  { path: '/counties/:countyFips', element: withLayout(<CountyPage />) },
  {
    path: '*',
    element: withLayout(
      <NotFound title="Page not found" message="This page could not be found." />,
    ),
  },
]

export const router = createBrowserRouter(routes)
