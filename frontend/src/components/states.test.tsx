import { render, screen } from '@testing-library/react'

import { ErrorState } from './ErrorState'
import { Loading } from './Loading'
import { NotFound } from './NotFound'

describe('shared UI state primitives (CE-C01)', () => {
  it('Loading announces via role="status" without an alert', () => {
    render(<Loading label="Loading county data…" />)

    expect(screen.getByRole('status')).toHaveTextContent(/loading county data/i)
    expect(screen.queryByRole('alert')).toBeNull()
  })

  it('ErrorState uses role="alert" and can offer an accessible retry', () => {
    const onRetry = vi.fn()
    render(<ErrorState message="Could not load data." onRetry={onRetry} />)

    expect(screen.getByRole('alert')).toHaveTextContent(/could not load data/i)
    screen.getByRole('button', { name: /try again/i }).click()
    expect(onRetry).toHaveBeenCalledTimes(1)
  })

  it('NotFound is distinct from an error (role="status", not "alert")', () => {
    render(<NotFound />)

    expect(screen.getByRole('status')).toHaveTextContent(/not found/i)
    expect(screen.queryByRole('alert')).toBeNull()
  })
})
