/**
 * CE-C02 county-directory context.
 *
 * Acquires the canonical county universe **once** from `GET /api/v1/counties`
 * (via the CE-C01 API client) and shares it with the county selector and the
 * county-route FIPS validation. No hard-coded list, no `/explorer` call, no
 * county/state name enrichment.
 */
import { createContext, useContext, useEffect, useMemo, useState } from 'react'
import type { ReactNode } from 'react'

import { listCounties } from './apiClient'
import type { County } from './types'

export type CountyDirectoryStatus = 'loading' | 'ready' | 'empty' | 'error'

interface CountyDirectoryState {
  status: CountyDirectoryStatus
  counties: County[]
  error: Error | null
}

export interface CountyDirectory extends CountyDirectoryState {
  /** Re-request the county list (used by the error state's retry control). */
  retry: () => void
}

const CountyDirectoryContext = createContext<CountyDirectory | null>(null)

const LOADING_STATE: CountyDirectoryState = {
  status: 'loading',
  counties: [],
  error: null,
}

export function CountyDirectoryProvider({ children }: { children: ReactNode }) {
  const [state, setState] = useState<CountyDirectoryState>(LOADING_STATE)
  const [reloadKey, setReloadKey] = useState(0)

  useEffect(() => {
    const controller = new AbortController()
    let active = true
    setState(LOADING_STATE)

    listCounties(controller.signal)
      .then((response) => {
        if (!active) return
        setState(
          response.counties.length === 0
            ? { status: 'empty', counties: [], error: null }
            : { status: 'ready', counties: response.counties, error: null },
        )
      })
      .catch((cause: unknown) => {
        if (!active) return
        setState({
          status: 'error',
          counties: [],
          error:
            cause instanceof Error
              ? cause
              : new Error('The county list could not be loaded.'),
        })
      })

    return () => {
      active = false
      controller.abort()
    }
  }, [reloadKey])

  const value = useMemo<CountyDirectory>(
    () => ({ ...state, retry: () => setReloadKey((key) => key + 1) }),
    [state],
  )

  return (
    <CountyDirectoryContext.Provider value={value}>
      {children}
    </CountyDirectoryContext.Provider>
  )
}

export function useCountyDirectory(): CountyDirectory {
  const context = useContext(CountyDirectoryContext)
  if (!context) {
    throw new Error(
      'useCountyDirectory must be used within a CountyDirectoryProvider.',
    )
  }
  return context
}
