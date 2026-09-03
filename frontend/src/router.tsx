import type { ReactNode } from 'react'
import type { RouteObject } from 'react-router-dom'
import { createBrowserRouter } from 'react-router-dom'

import { Layout } from './components/Layout'
import { NotFound } from './components/NotFound'
import { CountyPage } from './pages/CountyPage'
import { HomePage } from './pages/HomePage'

function withLayout(children: ReactNode): ReactNode {
  return <Layout>{children}</Layout>
}

/**
 * Route table. `/` is the no-county initial state; `/counties/:countyFips` is
 * the county route (selection acknowledgement in CE-C02; profile in CE-C03).
 * Exported so tests can build a deterministic `createMemoryRouter`.
 */
export const routes: RouteObject[] = [
  { path: '/', element: withLayout(<HomePage />) },
  { path: '/counties/:countyFips', element: withLayout(<CountyPage />) },
  {
    path: '*',
    element: withLayout(
      <NotFound title="Page not found" message="This page could not be found." />,
    ),
  },
]

export const router = createBrowserRouter(routes)
