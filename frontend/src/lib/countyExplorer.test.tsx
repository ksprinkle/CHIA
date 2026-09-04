import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { useState } from 'react'

import { CountyExplorerProvider, useCountyExplorer } from './countyExplorer'
import { makeExplorer, stubApi } from '../test/harness'

function Probe() {
  const explorer = useCountyExplorer()
  return (
    <div>
      <span data-testid="status">{explorer.status}</span>
      <span data-testid="name">
        {explorer.data?.county.county_name ?? '—'}
      </span>
      <button type="button" onClick={explorer.retry}>
        retry
      </button>
    </div>
  )
}

function Harness({ fips }: { fips: string }) {
  return (
    <CountyExplorerProvider countyFips={fips}>
      <Probe />
    </CountyExplorerProvider>
  )
}

afterEach(() => {
  vi.unstubAllGlobals()
  vi.restoreAllMocks()
})

describe('CountyExplorerProvider (CE-C03)', () => {
  it('requests the selected FIPS and transitions loading -> ready', async () => {
    const fetchMock = stubApi({ explorer: (fips) => makeExplorer(fips) })
    render(<Harness fips="01001" />)

    expect(screen.getByTestId('status')).toHaveTextContent('loading')
    await waitFor(() =>
      expect(screen.getByTestId('status')).toHaveTextContent('ready'),
    )
    expect(
      fetchMock.mock.calls.map((call) => String(call[0])),
    ).toContain('/api/v1/counties/01001/explorer')
  })

  it('maps a 404 to the notfound status (not error)', async () => {
    stubApi({ explorer: () => 404 })
    render(<Harness fips="01001" />)

    await waitFor(() =>
      expect(screen.getByTestId('status')).toHaveTextContent('notfound'),
    )
  })

  it('maps a 503 to the error status', async () => {
    stubApi({ explorer: () => 503 })
    render(<Harness fips="01001" />)

    await waitFor(() =>
      expect(screen.getByTestId('status')).toHaveTextContent('error'),
    )
  })

  it('maps a network failure to the error status', async () => {
    stubApi({ explorer: () => new TypeError('network down') })
    render(<Harness fips="01001" />)

    await waitFor(() =>
      expect(screen.getByTestId('status')).toHaveTextContent('error'),
    )
  })

  it('retry re-requests the Explorer read model once', async () => {
    let calls = 0
    const fetchMock = stubApi({
      explorer: (fips) => {
        calls += 1
        return calls === 1 ? 503 : makeExplorer(fips)
      },
    })
    render(<Harness fips="01001" />)

    await waitFor(() =>
      expect(screen.getByTestId('status')).toHaveTextContent('error'),
    )
    fireEvent.click(screen.getByRole('button', { name: 'retry' }))
    await waitFor(() =>
      expect(screen.getByTestId('status')).toHaveTextContent('ready'),
    )
    expect(
      fetchMock.mock.calls
        .map((call) => String(call[0]))
        .filter((url) => url.includes('/explorer')),
    ).toHaveLength(2)
  })

  it('drops the previous county and re-requests when the FIPS changes', async () => {
    const fetchMock = stubApi({
      explorer: (fips) =>
        makeExplorer(fips, { county: { county_name: `Name-${fips}` } }),
    })

    function Switcher() {
      const [fips, setFips] = useState('01001')
      return (
        <>
          <button type="button" onClick={() => setFips('01003')}>
            switch
          </button>
          <CountyExplorerProvider countyFips={fips}>
            <Probe />
          </CountyExplorerProvider>
        </>
      )
    }

    render(<Switcher />)
    await waitFor(() =>
      expect(screen.getByTestId('name')).toHaveTextContent('Name-01001'),
    )

    fireEvent.click(screen.getByRole('button', { name: 'switch' }))

    // No stale prior-county data while the new request is in flight.
    expect(screen.getByTestId('name')).toHaveTextContent('—')

    await waitFor(() =>
      expect(screen.getByTestId('name')).toHaveTextContent('Name-01003'),
    )
    expect(
      fetchMock.mock.calls
        .map((call) => String(call[0]))
        .filter((url) => url.includes('/explorer')),
    ).toEqual([
      '/api/v1/counties/01001/explorer',
      '/api/v1/counties/01003/explorer',
    ])
  })

  it('throws when used outside a provider', () => {
    function Orphan() {
      useCountyExplorer()
      return null
    }
    const consoleError = vi
      .spyOn(console, 'error')
      .mockImplementation(() => {})
    expect(() => render(<Orphan />)).toThrow(/CountyExplorerProvider/)
    consoleError.mockRestore()
  })
})
