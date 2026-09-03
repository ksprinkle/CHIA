import { fireEvent, render, screen, waitFor } from '@testing-library/react'

import { CountyDirectoryProvider, useCountyDirectory } from './countyDirectory'
import { makeCounties, stubCountiesFetch } from '../test/harness'

function Probe() {
  const directory = useCountyDirectory()
  return (
    <div>
      <span data-testid="status">{directory.status}</span>
      <span data-testid="count">{directory.counties.length}</span>
      <button type="button" onClick={directory.retry}>
        retry
      </button>
    </div>
  )
}

afterEach(() => {
  vi.unstubAllGlobals()
  vi.restoreAllMocks()
})

describe('CountyDirectoryProvider (CE-C02)', () => {
  it('transitions loading -> ready and exposes the county list', async () => {
    stubCountiesFetch(makeCounties(['01001', '01003']))
    render(
      <CountyDirectoryProvider>
        <Probe />
      </CountyDirectoryProvider>,
    )

    expect(screen.getByTestId('status')).toHaveTextContent('loading')
    await waitFor(() =>
      expect(screen.getByTestId('status')).toHaveTextContent('ready'),
    )
    expect(screen.getByTestId('count')).toHaveTextContent('2')
  })

  it('reports "empty" when the API returns zero counties', async () => {
    stubCountiesFetch(makeCounties([]))
    render(
      <CountyDirectoryProvider>
        <Probe />
      </CountyDirectoryProvider>,
    )

    await waitFor(() =>
      expect(screen.getByTestId('status')).toHaveTextContent('empty'),
    )
  })

  it('reports "error" when the county list request fails', async () => {
    stubCountiesFetch(new TypeError('network down'))
    render(
      <CountyDirectoryProvider>
        <Probe />
      </CountyDirectoryProvider>,
    )

    await waitFor(() =>
      expect(screen.getByTestId('status')).toHaveTextContent('error'),
    )
  })

  it('retry re-requests the county list once', async () => {
    let calls = 0
    stubCountiesFetch(() => {
      calls += 1
      if (calls === 1) {
        throw new TypeError('network down')
      }
      return {
        ok: true,
        status: 200,
        json: async () => makeCounties(['01001', '01003']),
      } as Response
    })
    render(
      <CountyDirectoryProvider>
        <Probe />
      </CountyDirectoryProvider>,
    )

    await waitFor(() =>
      expect(screen.getByTestId('status')).toHaveTextContent('error'),
    )
    fireEvent.click(screen.getByRole('button', { name: 'retry' }))
    await waitFor(() =>
      expect(screen.getByTestId('status')).toHaveTextContent('ready'),
    )
    expect(calls).toBe(2)
  })
})
