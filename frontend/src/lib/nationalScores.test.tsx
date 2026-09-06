import { render, screen, waitFor } from '@testing-library/react'

import { useNationalDimensionScores } from './nationalScores'
import { makeNationalScores } from '../test/harness'

afterEach(() => {
  vi.restoreAllMocks()
  vi.unstubAllGlobals()
})

function okScores() {
  return {
    ok: true,
    status: 200,
    json: async () => makeNationalScores(),
  } as Response
}

function Probe({ enabled }: { enabled: boolean }) {
  const scores = useNationalDimensionScores(enabled)
  return (
    <div>
      <span data-testid="status">{scores.status}</span>
      <span data-testid="count">{scores.data ? String(scores.data.count) : '-'}</span>
      <span data-testid="first">
        {scores.data ? scores.data.states[0].primary_care.median : '-'}
      </span>
    </div>
  )
}

describe('useNationalDimensionScores (CE-E14b)', () => {
  it('is idle and issues no request while disabled', () => {
    const fetchMock = vi.fn(() => Promise.resolve(okScores()))
    vi.stubGlobal('fetch', fetchMock)

    render(<Probe enabled={false} />)

    expect(screen.getByTestId('status')).toHaveTextContent('idle')
    expect(fetchMock).not.toHaveBeenCalled()
  })

  it('loads the national payload once enabled', async () => {
    const fetchMock = vi.fn(() => Promise.resolve(okScores()))
    vi.stubGlobal('fetch', fetchMock)

    render(<Probe enabled />)

    await waitFor(() => expect(screen.getByTestId('status')).toHaveTextContent('ready'))
    expect(screen.getByTestId('count')).toHaveTextContent('2')
    expect(screen.getByTestId('first')).toHaveTextContent('25')
    expect(fetchMock).toHaveBeenCalledTimes(1)
    expect(fetchMock).toHaveBeenCalledWith(
      expect.stringContaining('/states/dimension-scores'),
      expect.anything(),
    )
  })

  it('surfaces an error status when the request fails', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn(() =>
        Promise.resolve({ ok: false, status: 503, json: async () => ({}) } as Response),
      ),
    )

    render(<Probe enabled />)

    await waitFor(() => expect(screen.getByTestId('status')).toHaveTextContent('error'))
  })

  it('fetches only after it is enabled, not before', async () => {
    const fetchMock = vi.fn(() => Promise.resolve(okScores()))
    vi.stubGlobal('fetch', fetchMock)

    const { rerender } = render(<Probe enabled={false} />)
    expect(fetchMock).not.toHaveBeenCalled()

    rerender(<Probe enabled />)
    await waitFor(() => expect(screen.getByTestId('status')).toHaveTextContent('ready'))
    expect(fetchMock).toHaveBeenCalledTimes(1)
  })

  it('aborts the in-flight request on unmount', async () => {
    const seenSignals: Array<AbortSignal | undefined> = []
    vi.stubGlobal(
      'fetch',
      vi.fn((_url: unknown, init?: RequestInit) => {
        seenSignals.push(init?.signal ?? undefined)
        return new Promise<Response>(() => {}) // never resolves
      }),
    )

    const { unmount } = render(<Probe enabled />)
    await waitFor(() => expect(seenSignals.length).toBe(1))
    unmount()
    expect(seenSignals[0]?.aborted).toBe(true)
  })
})
