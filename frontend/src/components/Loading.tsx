export interface LoadingProps {
  label?: string
}

/**
 * Explicit loading state (governing specification, section 16). Announced
 * politely so assistive technology reports it without interrupting.
 */
export function Loading({ label = 'Loading…' }: LoadingProps) {
  return (
    <div className="state state--loading" role="status" aria-live="polite">
      <span className="state__spinner" aria-hidden="true" />
      <span>{label}</span>
    </div>
  )
}
