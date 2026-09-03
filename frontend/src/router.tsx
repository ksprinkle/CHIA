import type { ReactNode } from 'react'
import { createBrowserRouter } from 'react-router-dom'

import { NotFound } from './components/NotFound'
import { Layout } from './components/Layout'
import { CountyRoutePlaceholder } from './pages/CountyRoutePlaceholder'
import { HomePage } from './pages/HomePage'

function withLayout(children: ReactNode): ReactNode {
  return <Layout>{children}</Layout>
}

/**
 * CE-C01 base route table. `/` is the no-county initial state; the county route
 * exists so a county is addressable by FIPS in the URL. Route *behaviour*
 * (selection, URL-state sync, profile rendering) is CE-C02 / CE-C03.
 */
export const router = createBrowserRouter([
  { path: '/', element: withLayout(<HomePage />) },
  { path: '/counties/:countyFips', element: withLayout(<CountyRoutePlaceholder />) },
  {
    path: '*',
    element: withLayout(<NotFound title="Page not found" message="This page could not be found." />),
  },
])
