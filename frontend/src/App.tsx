import { RouterProvider } from 'react-router-dom'

import { CountyDirectoryProvider } from './lib/countyDirectory'
import { router } from './router'

export function App() {
  return (
    <CountyDirectoryProvider>
      <RouterProvider router={router} />
    </CountyDirectoryProvider>
  )
}
