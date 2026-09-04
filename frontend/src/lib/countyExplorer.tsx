/**
 * CE-C03 county Explorer read-model context.
 *
 * Fetches `GET /api/v1/counties/{county_fips}/explorer` once per county via the
 * CE-C01 API client and shares the assembled read model with the county
 * profile. It is keyed to the `:countyFips` route parameter (passed in as a
 * prop): whenever it changes, the previous county's data is dropped
 * immediately so a stale profile is never shown while the new request is in
 * flight.
 *
 * No analytical value is recomputed here; every score / status / composite
 * figure is rendered exactly as returned. CE-C04 will consume this same
 * provider for supporting evidence, methodology, provenance, and the
 * experimental composite.
 */
import { createContext, useContext, useEffect, useMemo, useState } from 'react'
import type { ReactNode } from 'react'

import { NotFoundError, getCountyExplorer } from './apiClient'
import type { ExplorerResponse } from './types'

export type CountyExplorerStatus = 'loading' | 'ready' | 'notfound' | 'error'

interface CountyExplorerState {
  status: CountyExplorerStatus
  /** The FIPS the current state describes; null before the first request. */
  countyFips: string | null
  data: ExplorerResponse | null
  error: Error | null
}

export interface CountyExplorer {
  status: CountyExplorerStatus
  data: ExplorerResponse | null
  error: Error | null
  /** Re-request the Explorer read model (used by the error state's retry). */
  retry: () => void
}

const CountyExplorerContext = createContext<CountyExplorer | null>(null)

export function CountyExplorerProvider({
  countyFips,
  children,
}: {
  countyFips: string
  children: ReactNode
}) {
  const [state, setState] = useState<CountyExplorerState>({
    status: 'loading',
    countyFips: null,
    data: null,
    error: null,
  })
  const [reloadKey, setReloadKey] = useState(0)

  useEffect(() => {
    const controller = new AbortController()
    let active = true
    setState({ status: 'loading', countyFips, data: null, error: null })

    getCountyExplorer(countyFips, controller.signal)
      .then((data) => {
        if (!active) return
        setState({ status: 'ready', countyFips, data, error: null })
      })
      .catch((cause: unknown) => {
        if (!active) return
        if (cause instanceof NotFoundError) {
          setState({ status: 'notfound', countyFips, data: null, error: null })
          return
        }
        setState({
          status: 'error',
          countyFips,
          data: null,
          error:
            cause instanceof Error
              ? cause
              : new Error('The county profile could not be loaded.'),
        })
      })

    return () => {
      active = false
      controller.abort()
    }
  }, [countyFips, reloadKey])

  // Until the state describes the county currently requested, expose a loading
  // view -- never the previous county's data.
  const synced = state.countyFips === countyFips
  const value = useMemo<CountyExplorer>(
    () => ({
      status: synced ? state.status : 'loading',
      data: synced ? state.data : null,
      error: synced ? state.error : null,
      retry: () => setReloadKey((key) => key + 1),
    }),
    [synced, state],
  )

  return (
    <CountyExplorerContext.Provider value={value}>
      {children}
    </CountyExplorerContext.Provider>
  )
}

export function useCountyExplorer(): CountyExplorer {
  const context = useContext(CountyExplorerContext)
  if (!context) {
    throw new Error(
      'useCountyExplorer must be used within a CountyExplorerProvider.',
    )
  }
  return context
}
