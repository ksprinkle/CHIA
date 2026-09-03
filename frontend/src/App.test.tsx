import { render, screen } from '@testing-library/react'

import { App } from './App'

// CE-C02 wraps the app in CountyDirectoryProvider, which requests the county
// list on mount. These CE-C01 foundation tests assert only the pre-selection
// state, so the request is held pending: the provider stays in its loading
// state (exactly what these tests already observed) and no post-test state
// update fires, which would otherwise raise an asynchronous act() warning.
beforeEach(() => {
  vi.stubGlobal(
    'fetch',
    vi.fn(() => new Promise<Response>(() => {})),
  )
})

afterEach(() => {
  vi.unstubAllGlobals()
  vi.restoreAllMocks()
})

describe('App (CE-C01 foundation)', () => {
  it('renders the initial state with no county assumed or selected', () => {
    render(<App />)

    expect(
      screen.getByRole('heading', { level: 1, name: /chia county explorer/i }),
    ).toBeInTheDocument()
    expect(
      screen.getByText(/no county is currently selected/i),
    ).toBeInTheDocument()
  })

  it('provides a skip link that targets the main content landmark', () => {
    render(<App />)

    const skipLink = screen.getByRole('link', { name: /skip to main content/i })
    expect(skipLink).toHaveAttribute('href', '#main-content')
    expect(screen.getByRole('main')).toHaveAttribute('id', 'main-content')
  })

  it('does not render any county or dimension data (deferred to CE-C02/CE-C03)', () => {
    render(<App />)

    expect(screen.queryByRole('combobox')).toBeNull()
    expect(screen.queryByText(/primary care/i)).toBeNull()
    expect(screen.queryByText(/composite/i)).toBeNull()
  })
})
