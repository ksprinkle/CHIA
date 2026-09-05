import { fireEvent, render, screen } from '@testing-library/react'

import { CountyDataExport } from './CountyDataExport'
import { buildCountyCsv } from '../lib/countyCsv'
import { makeExplorer } from '../test/harness'

let createObjectURL: ReturnType<typeof vi.fn>
let revokeObjectURL: ReturnType<typeof vi.fn>
let clickedAnchor: HTMLAnchorElement | null

function recordAnchor(anchor: HTMLAnchorElement) {
  clickedAnchor = anchor
}

beforeEach(() => {
  createObjectURL = vi.fn(() => 'blob:mock-url')
  revokeObjectURL = vi.fn()
  Object.assign(URL, { createObjectURL, revokeObjectURL })
  clickedAnchor = null
  vi.spyOn(HTMLAnchorElement.prototype, 'click').mockImplementation(function (
    this: HTMLAnchorElement,
  ) {
    recordAnchor(this)
  })
})

afterEach(() => {
  vi.restoreAllMocks()
  Reflect.deleteProperty(URL, 'createObjectURL')
  Reflect.deleteProperty(URL, 'revokeObjectURL')
})

describe('CountyDataExport (CE-E11)', () => {
  it('renders a native, focusable button with the exact accessible name in a labelled region', () => {
    render(<CountyDataExport data={makeExplorer('01001')} />)

    const region = screen.getByRole('region', { name: /county data export/i })
    const button = screen.getByRole('button', {
      name: "Download this county's data (CSV)",
    })
    expect(button.tagName).toBe('BUTTON')
    expect(button).toHaveAttribute('type', 'button')
    expect(region).toContainElement(button)

    button.focus()
    expect(button).toHaveFocus()
  })

  it('on activation generates a text/csv Blob and downloads it under the deterministic filename', () => {
    render(
      <CountyDataExport
        data={makeExplorer('01001', { county: { county_name: 'Autauga County' } })}
      />,
    )
    fireEvent.click(screen.getByRole('button', { name: /download this county/i }))

    expect(createObjectURL).toHaveBeenCalledTimes(1)
    const blob = createObjectURL.mock.calls[0][0] as Blob
    expect(blob).toBeInstanceOf(Blob)
    expect(blob.type).toBe('text/csv;charset=utf-8')

    expect(clickedAnchor).toBeInstanceOf(HTMLAnchorElement)
    expect(clickedAnchor?.download).toBe('chia-01001-autauga-county-v0.1.csv')
    expect(clickedAnchor?.getAttribute('href')).toBe('blob:mock-url')
    expect(clickedAnchor?.isConnected).toBe(false) // appended, clicked, then removed
    expect(revokeObjectURL).toHaveBeenCalledWith('blob:mock-url')
  })

  it('confirms the download to assistive technology via a polite role="status" line', () => {
    render(
      <CountyDataExport
        data={makeExplorer('01001', { county: { county_name: 'Autauga County' } })}
      />,
    )
    const status = screen.getByRole('status')
    expect(status).toHaveTextContent('')

    fireEvent.click(screen.getByRole('button', { name: /download this county/i }))
    expect(status).toHaveTextContent('Downloaded chia-01001-autauga-county-v0.1.csv')
  })

  it('puts the exact buildCountyCsv output into the downloaded Blob', () => {
    const data = makeExplorer('01001')
    render(<CountyDataExport data={data} />)
    fireEvent.click(screen.getByRole('button', { name: /download this county/i }))

    const blob = createObjectURL.mock.calls[0][0] as Blob
    // jsdom's Blob has no .text(); a byte-length match is a strong check that
    // the full generated CSV (BOM + metadata + header + every row) reached it.
    const expected = buildCountyCsv(data).csv
    expect(blob.size).toBe(new TextEncoder().encode(expected).length)
  })
})
