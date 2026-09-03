import { screen, waitFor } from '@testing-library/react'

import { makeCounties, renderApp, stubCountiesFetch } from '../test/harness'

const C03_LEAKAGE = [
  /primary care/i,
  /dental/i,
  /mental health/i,
  /composite/i,
  /methodology/i,
  /provenance/i,
  /percentile/i,
  /completeness/i,
  /supporting evidence/i,
]

function assertOnlyCountyListFetches(
  fetchMock: ReturnType<typeof stubCountiesFetch>,
) {
  for (const call of fetchMock.mock.calls) {
    const url = String(call[0])
    expect(url).toContain('/api/v1/counties')
    expect(url).not.toContain('/explorer')
  }
}

afterEach(() => {
  vi.unstubAllGlobals()
  vi.restoreAllMocks()
})

describe('CountyPage (CE-C02 county route)', () => {
  it('renders a minimal acknowledgement (name + FIPS) for a valid known county', async () => {
    const fetchMock = stubCountiesFetch(makeCounties(['01001', '01003']))
    renderApp(['/counties/01001'])

    const heading = await screen.findByRole('heading', { level: 1 })
    expect(heading).toHaveTextContent('0')
    expect(heading).toHaveTextContent('(01001)')
    expect(screen.getByText(/county profile — ce-c03/i)).toBeInTheDocument()

    for (const pattern of C03_LEAKAGE) {
      expect(screen.queryByText(pattern)).toBeNull()
    }
    assertOnlyCountyListFetches(fetchMock)
  })

  it.each(['abcde', '123', '123456'])(
    'shows a distinct "invalid FIPS" not-found for malformed FIPS %s',
    async (bad) => {
      const fetchMock = stubCountiesFetch(makeCounties(['01001']))
      renderApp([`/counties/${bad}`])

      expect(
        await screen.findByText(/not a five-digit county fips/i),
      ).toBeInTheDocument()
      expect(
        screen.getByRole('link', { name: /return to the start/i }),
      ).toBeInTheDocument()
      assertOnlyCountyListFetches(fetchMock)
    },
  )

  it('shows a distinct "county not found" for a well-formed but unknown FIPS', async () => {
    const fetchMock = stubCountiesFetch(makeCounties(['01001', '01003']))
    renderApp(['/counties/99999'])

    expect(
      await screen.findByText(
        /no county with fips 99999 is in the chia county universe/i,
      ),
    ).toBeInTheDocument()
    expect(
      screen.getByRole('link', { name: /return to the start/i }),
    ).toBeInTheDocument()
    assertOnlyCountyListFetches(fetchMock)
  })

  it('surfaces the county-list error state when the list fails to load', async () => {
    stubCountiesFetch(new TypeError('network down'))
    renderApp(['/counties/01001'])

    await waitFor(() =>
      expect(screen.getAllByRole('alert').length).toBeGreaterThan(0),
    )
  })
})
