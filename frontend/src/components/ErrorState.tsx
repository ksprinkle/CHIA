export interface ErrorStateProps {
  title?: string
  message: string
  /** When provided, an accessible "Try again" control is offered. */
  onRetry?: () => void
}

/**
 * API / system error state (governing specification, section 16): explain that
 * data could not be loaded and offer a way forward. Kept visually and
 * semantically distinct from the not-found state.
 */
export function ErrorState({
  title = 'Something went wrong',
  message,
  onRetry,
}: ErrorStateProps) {
  return (
    <div className="state state--error" role="alert">
      <h2 className="state__title">{title}</h2>
      <p className="state__message">{message}</p>
      {onRetry ? (
        <button type="button" className="button" onClick={onRetry}>
          Try again
        </button>
      ) : null}
    </div>
  )
}
