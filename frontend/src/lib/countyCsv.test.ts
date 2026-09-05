import { CSV_COLUMNS, buildCountyCsv, escapeCsvField, slugify } from './countyCsv'
import { makeExplorer } from '../test/harness'

const COL = Object.fromEntries(
  CSV_COLUMNS.map((name, index) => [name, index]),
) as Record<(typeof CSV_COLUMNS)[number], number>

function linesOf(csv: string): string[] {
  return csv.split('\r\n')
}

/** Data records = everything after the 2 metadata lines + header, minus the
 *  trailing empty entry from the final CRLF. Fixtures used here contain no
 *  embedded `","`, so a naive quoted-field split is exact. */
function dataRows(csv: string): string[][] {
  return linesOf(csv)
    .slice(3)
    .filter(Boolean)
    .map((line) => line.replace(/^"/, '').replace(/"$/, '').split('","'))
}

function findRow(csv: string, dimensionId: string, role: string): string[] {
  const row = dataRows(csv).find(
    (fields) =>
      fields[COL.dimension_id] === dimensionId && fields[COL.role] === role,
  )
  if (!row) throw new Error(`no ${dimensionId}/${role} row`)
  return row
}

describe('escapeCsvField (RFC 4180)', () => {
  it('quotes every field and doubles embedded quotes', () => {
    expect(escapeCsvField('plain')).toBe('"plain"')
    expect(escapeCsvField('a,b')).toBe('"a,b"')
    expect(escapeCsvField('say "hi"')).toBe('"say ""hi"""')
    expect(escapeCsvField('')).toBe('""')
  })
})

describe('slugify', () => {
  it('lowercases, collapses non-alphanumerics to hyphens, trims', () => {
    expect(slugify('Autauga County')).toBe('autauga-county')
    expect(slugify('Doña Ana County')).toBe('do-a-ana-county')
    expect(slugify('St. Louis city')).toBe('st-louis-city')
  })
})

describe('buildCountyCsv (CE-E11)', () => {
  it('starts with a UTF-8 BOM, two quoted metadata lines, then the exact 29-column header', () => {
    const { csv } = buildCountyCsv(
      makeExplorer('01001', { county: { county_name: 'Autauga County' } }),
    )
    expect(csv.startsWith('﻿')).toBe(true)

    const lines = linesOf(csv)
    expect(lines[0]).toBe(
      '﻿"CHIA County Data Export — Autauga County, AL — methodology v0.1"',
    )
    expect(lines[1]).toMatch(/^"Values verbatim from the CHIA v0\.1 analytical pipeline;/)
    expect(lines[2]).toBe(CSV_COLUMNS.map((c) => `"${c}"`).join(','))
    expect(CSV_COLUMNS).toHaveLength(29)
  })

  it('terminates every record with CRLF, including the last, and uses no bare LF', () => {
    const { csv } = buildCountyCsv(makeExplorer('01001'))
    expect(csv.endsWith('\r\n')).toBe(true)
    expect(csv.replace(/\r\n/g, '')).not.toContain('\n')
  })

  it('orders rows deterministically: per dimension primary then supporting, composite last', () => {
    const { csv } = buildCountyCsv(makeExplorer('01001'))
    const rows = dataRows(csv).map((f) => [f[COL.dimension_id], f[COL.role]])

    expect(rows.slice(0, 4)).toEqual([
      ['PRIMARY_CARE', 'primary'],
      ['PRIMARY_CARE', 'supporting'],
      ['PRIMARY_CARE', 'supporting'],
      ['PRIMARY_CARE', 'supporting'],
    ])
    expect(rows.at(-1)).toEqual(['EXPERIMENTAL_COMPOSITE', 'composite'])
    expect(rows.filter(([, role]) => role === 'primary').map(([d]) => d)).toEqual([
      'PRIMARY_CARE',
      'DENTAL',
      'MENTAL_HEALTH',
      'MUA_P',
    ])
  })

  it('writes numeric values verbatim (unrounded) for raw, normalized, and score', () => {
    const { csv } = buildCountyCsv(
      makeExplorer('01001', {
        dimensions: {
          primary_care: {
            score: 88.75776397515529,
            primary_measure: {
              raw_value: 42.123456789,
              normalized_value: 88.75776397515529,
            },
          },
        },
      }),
    )
    const row = findRow(csv, 'PRIMARY_CARE', 'primary')
    expect(row[COL.raw_value]).toBe('42.123456789')
    expect(row[COL.normalized_value]).toBe('88.75776397515529')
    expect(row[COL.dimension_score]).toBe('88.75776397515529')
  })

  it('distinguishes a genuine 0 ("0") from a missing value ("")', () => {
    const { csv } = buildCountyCsv(
      makeExplorer('01001', {
        dimensions: {
          primary_care: {
            score: 0,
            primary_measure: { raw_value: 0, normalized_value: 0, quality_flag: null },
          },
          dental: {
            available: false,
            score: null,
            score_status: null,
            primary_measure: { raw_value: null, normalized_value: null },
          },
        },
      }),
    )
    const pc = findRow(csv, 'PRIMARY_CARE', 'primary')
    expect(pc[COL.raw_value]).toBe('0')
    expect(pc[COL.dimension_score]).toBe('0')

    const dental = findRow(csv, 'DENTAL', 'primary')
    expect(dental[COL.raw_value]).toBe('')
    expect(dental[COL.normalized_value]).toBe('')
    expect(dental[COL.dimension_score]).toBe('')
    // metadata for the unavailable dimension is still present
    expect(dental[COL.variable_id]).not.toBe('')
    expect(dental[COL.source_name]).toBe('Dental HPSA')
  })

  it('quotes and escapes free text containing commas and quotes', () => {
    const { csv } = buildCountyCsv(
      makeExplorer('01001', {
        dimensions: { primary_care: { calculation_method: 'rank, then "adjust"' } },
      }),
    )
    const line = linesOf(csv).find(
      (l) => l.includes('"PRIMARY_CARE"') && l.includes('"primary"'),
    )!
    expect(line).toContain('"rank, then ""adjust"""')
  })

  it('leaves source columns blank on supporting-evidence rows (no per-variable source in v0.1)', () => {
    const { csv } = buildCountyCsv(makeExplorer('01001'))
    const supporting = dataRows(csv).find(
      (f) => f[COL.dimension_id] === 'PRIMARY_CARE' && f[COL.role] === 'supporting',
    )!
    for (const column of [
      'source_id',
      'source_name',
      'source_publisher',
      'source_dataset',
      'source_reference_period',
    ] as const) {
      expect(supporting[COL[column]]).toBe('')
    }
    expect(supporting[COL.variable_id]).toMatch(/_SUP_\d$/)
    expect(supporting[COL.dimension_name]).toBe('Primary Care Access')
  })

  it('emits the experimental composite as a single trailing row carrying composite_value', () => {
    const { csv } = buildCountyCsv(makeExplorer('01001'))
    const composite = findRow(csv, 'EXPERIMENTAL_COMPOSITE', 'composite')
    expect(composite[COL.dimension_name]).toBe('Experimental / Provisional')
    expect(composite[COL.dimension_score]).toBe('59.75')
    expect(composite[COL.score_status]).toBe('experimental_provisional')
    expect(composite[COL.variable_id]).toBe('')
  })

  it('carries full source provenance on primary rows', () => {
    const { csv } = buildCountyCsv(makeExplorer('01001'))
    const row = findRow(csv, 'PRIMARY_CARE', 'primary')
    expect(row[COL.source_id]).toBe('1')
    expect(row[COL.source_name]).toBe('Primary Care HPSA')
    expect(row[COL.source_publisher]).toBe('HRSA')
    expect(row[COL.source_dataset]).toBe('Primary Care HPSA Spatial Coverage')
    expect(row[COL.source_reference_period]).toBe('v0.1 source period')
    expect(row[COL.source_url]).toBe('')
    expect(row[COL.methodology_version]).toBe('v0.1')
    expect(row[COL.county_fips]).toBe('01001')
  })

  it('builds a deterministic filename from FIPS, county slug, and methodology version', () => {
    const { filename } = buildCountyCsv(
      makeExplorer('35013', { county: { county_name: 'Doña Ana County' } }),
    )
    expect(filename).toBe('chia-35013-do-a-ana-county-v0.1.csv')
  })
})
