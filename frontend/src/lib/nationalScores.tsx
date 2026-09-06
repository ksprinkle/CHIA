/**
 * CE-E14b national dimension-scores hook.
 *
 * Fetches `GET /api/v1/states/dimension-scores` (CE-E14a) once for the
 * national map's measure view. Unlike `useStateDimensionScores` this is not
 * route-keyed -- there is one national payload -- but it is **lazy**: it only
 * requests while `enabled` is true (i.e. while a measure is selected on the
 * landing page), so a visitor who never enters measure mode never triggers
 * the request (governing v0.2 UX specification section 11.7).
 *
 * No analytical value is computed here; every `median` is rendered exactly as
 * returned by the API, which itself is a display-only summary of persisted
 * county scores (see `Documentation/NATIONAL_MAP_STATE_SUMMARY.md.txt`).
 */
import { useEffect, useMemo, useState } from 'react'

import { getNationalDimensionScores } from './apiClient'
import type { NationalDimensionScoresResponse } from './types'

export type NationalScoresStatus = 'idle' | 'loading' | 'ready' | 'error'

interface InternalState {
  status: NationalScoresStatus
  data: NationalDimensionScoresResponse | null
  error: Error | null
}

export interface NationalScores {
  status: NationalScoresStatus
  data: NationalDimensionScoresResponse | null
  error: Error | null
  /** Re-request the national dimension scores (used by the error state's retry). */
  retry: () => void
}

const IDLE: InternalState = { status: 'idle', data: null, error: null }

export function useNationalDimensionScores(enabled = true): NationalScores {
  const [state, setState] = useState<InternalState>(enabled ? { ...IDLE, status: 'loading' } : IDLE)
  const [reloadKey, setReloadKey] = useState(0)

  useEffect(() => {
    if (!enabled) {
      setState(IDLE)
      return
    }

    const controller = new AbortController()
    let active = true
    setState({ status: 'loading', data: null, error: null })

    getNationalDimensionScores(controller.signal)
      .then((data) => {
        if (!active) return
        setState({ status: 'ready', data, error: null })
      })
      .catch((cause: unknown) => {
        if (!active) return
        setState({
          status: 'error',
          data: null,
          error:
            cause instanceof Error
              ? cause
              : new Error('The national dimension scores could not be loaded.'),
        })
      })

    return () => {
      active = false
      controller.abort()
    }
  }, [enabled, reloadKey])

  return useMemo<NationalScores>(
    () => ({
      status: state.status,
      data: state.data,
      error: state.error,
      retry: () => setReloadKey((key) => key + 1),
    }),
    [state],
  )
}
