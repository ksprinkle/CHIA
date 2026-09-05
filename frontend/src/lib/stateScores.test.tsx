import { fireEvent, render, screen, waitFor } from '@testing-library/react'

import { useStateDimensionScores } from './stateScores'
import { makeMultiStateCounties, makeStateScores, stubApi } from '../test/harness'

function Probe({ stateFips }: { stateFips: string }) {
  const scores = useStateDimensionScores(stateFips)
  return (
    <div>
      <span data-testid="status">{scores.status}</span>
      <span data-testid="count">{scores.data?.count ?? '—'}</span>
      <button type="button" onClick={scores.retry}>
        retry
      </button>
    </div>
  )
}

afterEach(() => {
  vi.unstubAllGlobals()
  vi.restoreAllMocks()
})

describe('useStateDimensionScores (CE-E10)', () => {
  it('requests /states/{fips}/dimension-scores and transitions loading -> ready', async () => {
    const fetchMock = stubApi({ counties: makeMultiStateCounties() })
    render(<Probe stateFips="01" />)

    expect(screen.getByTestId('status')).toHaveTextContent('loading')
    await waitFor(() =>
      expect(screen.getByTestId('status')).toHaveTextContent('ready'),
    )
    expect(fetchMock.mock.calls.map((call) => String(call[0]))).toContain(
      '/api/v1/states/01/dimension-scores',
    )
    expect(screen.getByTestId('count')).toHaveTextContent('2')
  })

  it('maps an HTTP failure to the error status', async () => {
    stubApi({ counties: makeMultiStateCounties(), stateScores: () => 503 })
    render(<Probe stateFips="01" />)

    await waitFor(() =>
      expect(screen.getByTestId('status')).toHaveTextContent('error'),
    )
  })

  it('maps a network failure to the error status', async () => {
    stubApi({
      counties: makeMultiStateCounties(),
      stateScores: () => new TypeError('network down'),
    })
    render(<Probe stateFips="01" />)

    await waitFor(() =>
      expect(screen.getByTestId('status')).toHaveTextContent('error'),
    )
  })

  it('retry re-requests the scores', async () => {
    let calls = 0
    const fetchMock = stubApi({
      counties: makeMultiStateCounties(),
      stateScores: () => {
        calls += 1
        return calls === 1 ? 503 : makeStateScores('01', makeMultiStateCounties().counties)
      },
    })
    render(<Probe stateFips="01" />)

    await waitFor(() =>
      expect(screen.getByTestId('status')).toHaveTextContent('error'),
    )
    fireEvent.click(screen.getByRole('button', { name: /retry/i }))
    await waitFor(() =>
      expect(screen.getByTestId('status')).toHaveTextContent('ready'),
    )
    expect(
      fetchMock.mock.calls
        .map((call) => String(call[0]))
        .filter((url) => url.includes('/dimension-scores')),
    ).toHaveLength(2)
  })
})
