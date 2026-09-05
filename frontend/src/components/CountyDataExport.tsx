import { useState } from 'react'

import { buildCountyCsv } from '../lib/countyCsv'
import type { ExplorerResponse } from '../lib/types'

/**
 * CE-E11 per-county data export (governing specification section 8.5 -- "a
 * user who wants the actual numerical data should be able to access it
 * directly").
 *
 * Generates a self-describing CSV entirely client-side from the already-loaded
 * Explorer read model (`lib/countyCsv.ts`) and offers it as a download. No
 * network request, no server-side generation, no hosted file. Values in the
 * file are verbatim from the analytical pipeline (unrounded), unlike the
 * deliberately rounded on-screen display.
 *
 * Placed after the page-level Sources panel, in its own labelled region. The
 * trigger is a native `<button>` (normal tab order, no focus trap); a polite
 * `role="status"` line confirms the download for assistive technology.
 */
export function CountyDataExport({ data }: { data: ExplorerResponse }) {
  const [confirmation, setConfirmation] = useState('')

  function handleExport() {
    const { filename, csv } = buildCountyCsv(data)
    const blob = new Blob([csv], { type: 'text/csv;charset=utf-8' })
    const url = URL.createObjectURL(blob)
    const anchor = document.createElement('a')
    anchor.href = url
    anchor.download = filename
    document.body.appendChild(anchor)
    anchor.click()
    anchor.remove()
    URL.revokeObjectURL(url)
    setConfirmation(`Downloaded ${filename}`)
  }

  return (
    <section className="county-data-export" aria-labelledby="county-data-export-heading">
      <h2 id="county-data-export-heading">County data export</h2>
      <p className="county-data-export__description">
        Download every displayed and underlying value for this county — the four
        dimensions, their primary and supporting variables, the experimental
        composite, and full source provenance — as a CSV. Numbers are exact
        (unrounded).
      </p>
      <button
        type="button"
        className="county-data-export__button"
        onClick={handleExport}
      >
        {"Download this county's data (CSV)"}
      </button>
      <p className="county-data-export__status" role="status">
        {confirmation}
      </p>
    </section>
  )
}
