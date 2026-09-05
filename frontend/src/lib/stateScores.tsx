/**
 * CE-E10 state dimension-scores hook.
 *
 * Fetches `GET /api/v1/states/{state_fips}/dimension-scores` (CE-E09) once per
 * state and exposes it to the state page's county choropleth. Keyed to the
 * `:stateFips` route parameter: when it changes, the previous state's scores
 * are dropped immediately so a stale colouring is never shown. Follows the
 * same shape as `lib/countyExplorer.tsx`.
 *
 * No analytical value is recomputed here; every score is rendered exactly as
 * returned by the API.
 */
import { useEffect, useMemo, useState } from 'react'

import { getStateDimensionScores } from './apiClient'
import type { StateDimensionScoresResponse } from './types'

export type StateScoresStatus = 'loading' | 'ready' | 'error'

interface InternalState {
  status: StateScoresStatus
  stateFips: string | null
  data: StateDimensionScoresResponse | null
  error: Error | null
}

export interface StateScores {
  status: StateScoresStatus
  data: StateDimensionScoresResponse | null
  error: Error | null
  /** Re-request the state's dimension scores (used by the error state's retry). */
  retry: () => void
}

export function useStateDimensionScores(stateFips: string): StateScores {
  const [state, setState] = useState<InternalState>({
    status: 'loading',
    stateFips: null,
    data: null,
    error: null,
  })
  const [reloadKey, setReloadKey] = useState(0)

  useEffect(() => {
    const controller = new AbortController()
    let active = true
    setState({ status: 'loading', stateFips, data: null, error: null })

    getStateDimensionScores(stateFips, controller.signal)
      .then((data) => {
        if (!active) return
        setState({ status: 'ready', stateFips, data, error: null })
      })
      .catch((cause: unknown) => {
        if (!active) return
        setState({
          status: 'error',
          stateFips,
          data: null,
          error:
            cause instanceof Error
              ? cause
              : new Error('The state dimension scores could not be loaded.'),
        })
      })

    return () => {
      active = false
      controller.abort()
    }
  }, [stateFips, reloadKey])

  // Until the internal state describes the state currently requested, expose a
  // loading view -- never the previous state's colouring.
  const synced = state.stateFips === stateFips
  return useMemo<StateScores>(
    () => ({
      status: synced ? state.status : 'loading',
      data: synced ? state.data : null,
      error: synced ? state.error : null,
      retry: () => setReloadKey((key) => key + 1),
    }),
    [synced, state],
  )
}
