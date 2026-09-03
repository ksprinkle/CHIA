export interface NotFoundProps {
  title?: string
  message?: string
}

/**
 * Not-found state (governing specification, section 16): a nonexistent county
 * FIPS must be distinguishable from a server/API failure. This uses role
 * "status" (not "alert") and its own copy so the two are never conflated.
 */
export function NotFound({
  title = 'Not found',
  message = 'The requested county could not be found.',
}: NotFoundProps) {
  return (
    <div className="state state--not-found" role="status">
      <h2 className="state__title">{title}</h2>
      <p className="state__message">{message}</p>
    </div>
  )
}
