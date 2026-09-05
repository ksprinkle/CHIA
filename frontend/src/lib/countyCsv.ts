/**
 * CE-E11 per-county CSV export.
 *
 * A pure transform of the already-fetched `/counties/{fips}/explorer` payload
 * into a self-describing CSV. No second request, no server generation, no
 * hosted file, no CSV dependency. Every numeric value is written **verbatim**
 * from the payload (no rounding) -- this file is the exact-data artifact,
 * distinct from the deliberately rounded on-screen display.
 *
 * Shape: long / normalized -- one row per variable observation. Ordering is
 * fully deterministic: dimensions in `DIMENSION_ORDER`, each dimension's
 * `primary` row then its `supporting` rows in payload order, then a single
 * trailing `EXPERIMENTAL_COMPOSITE` row.
 *
 * Semantics: RFC 4180 -- every field is quoted, embedded `"` doubled, records
 * terminated with CRLF. A genuine `0` is written as `"0"`; a missing/null
 * value is an empty field (`""`), never a sentinel string. A UTF-8 BOM is
 * prepended so spreadsheet tools open accented county names correctly.
 */
import { DIMENSION_ORDER } from './dimensions'
import type { ExplorerResponse, SourceRef } from './types'

export const CSV_COLUMNS = [
  'county_fips',
  'county_name',
  'state_abbr',
  'state_name',
  'methodology_version',
  'methodology_name',
  'period',
  'completeness_status',
  'dimension_id',
  'dimension_name',
  'dimension_direction',
  'role',
  'variable_id',
  'variable_display_name',
  'unit',
  'raw_value',
  'normalized_value',
  'normalization_method',
  'dimension_score',
  'score_status',
  'quality_flag',
  'calculation_method',
  'source_id',
  'source_name',
  'source_publisher',
  'source_dataset',
  'source_reference_period',
  'source_url',
  'source_accessed_at',
  'source_artifact_filename',
  'source_content_sha256',
] as const

type CsvColumn = (typeof CSV_COLUMNS)[number]
type CsvRow = Record<CsvColumn, string>

const CRLF = '\r\n'
const BOM = '﻿'

/** RFC 4180: quote every field, double any embedded quote. */
export function escapeCsvField(value: string): string {
  return `"${value.replace(/"/g, '""')}"`
}

/** `null`/`undefined` -> empty field; numbers verbatim (`0` stays `"0"`). */
function cell(value: string | number | null | undefined): string {
  if (value === null || value === undefined) return ''
  return String(value)
}

/** Lowercase, non-alphanumeric runs -> single hyphen, trimmed. */
export function slugify(value: string): string {
  return value
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, '-')
    .replace(/^-+|-+$/g, '')
}

function emptyRow(): CsvRow {
  return Object.fromEntries(CSV_COLUMNS.map((column) => [column, ''])) as CsvRow
}

function serializeRow(row: CsvRow): string {
  return CSV_COLUMNS.map((column) => escapeCsvField(row[column])).join(',')
}

export interface CountyCsv {
  filename: string
  csv: string
}

export function buildCountyCsv(data: ExplorerResponse): CountyCsv {
  const { county, period, access_profile, methodology, provenance, experimental_composite } = data
  const sourceById = new Map<number, SourceRef>(
    provenance.sources.map((source) => [source.source_id, source]),
  )

  const identity = {
    county_fips: county.county_fips,
    county_name: county.county_name,
    state_abbr: county.state_abbr,
    state_name: county.state_name,
    methodology_version: methodology.methodology_version,
    methodology_name: methodology.name,
    period: period.value,
    completeness_status: cell(period.completeness_status),
  }

  const rows: CsvRow[] = []

  for (const key of DIMENSION_ORDER) {
    const dimension = access_profile[key]
    const measure = dimension.primary_measure
    const source =
      dimension.source_id === null ? undefined : sourceById.get(dimension.source_id)

    const primary = emptyRow()
    Object.assign(primary, identity, {
      dimension_id: dimension.dimension_id,
      dimension_name: dimension.dimension_name,
      dimension_direction: cell(dimension.direction),
      role: 'primary',
      variable_id: measure.variable_id,
      variable_display_name: measure.display_name,
      unit: cell(measure.unit),
      raw_value: cell(measure.raw_value),
      normalized_value: cell(measure.normalized_value),
      normalization_method: cell(measure.normalization_method),
      dimension_score: cell(dimension.score),
      score_status: cell(dimension.score_status),
      quality_flag: cell(measure.quality_flag),
      calculation_method: cell(dimension.calculation_method),
      source_id: cell(dimension.source_id),
      source_name: cell(source?.source_name),
      source_publisher: cell(source?.publisher),
      source_dataset: cell(source?.dataset_name),
      source_reference_period: cell(source?.reference_period),
      source_url: cell(source?.url),
      source_accessed_at: cell(source?.accessed_at),
      source_artifact_filename: cell(source?.artifact_filename),
      source_content_sha256: cell(source?.content_sha256),
    })
    rows.push(primary)

    for (const item of dimension.supporting_evidence) {
      const supporting = emptyRow()
      Object.assign(supporting, identity, {
        dimension_id: dimension.dimension_id,
        dimension_name: dimension.dimension_name,
        dimension_direction: cell(dimension.direction),
        role: 'supporting',
        variable_id: item.variable_id,
        variable_display_name: item.display_name,
        unit: cell(item.unit),
        raw_value: cell(item.raw_value),
        quality_flag: cell(item.quality_flag),
      })
      rows.push(supporting)
    }
  }

  const composite = emptyRow()
  Object.assign(composite, identity, {
    dimension_id: 'EXPERIMENTAL_COMPOSITE',
    dimension_name: experimental_composite.label,
    role: 'composite',
    dimension_score: cell(experimental_composite.composite_value),
    score_status: cell(experimental_composite.status),
  })
  rows.push(composite)

  const metaLine1 = escapeCsvField(
    `CHIA County Data Export — ${county.county_name}, ${county.state_abbr} — methodology ${methodology.methodology_version}`,
  )
  const metaLine2 = escapeCsvField(
    'Values verbatim from the CHIA v0.1 analytical pipeline; empty = not available; supporting-evidence rows have no per-variable source in v0.1.',
  )
  const header = CSV_COLUMNS.map((column) => escapeCsvField(column)).join(',')

  const csv =
    BOM +
    [metaLine1, metaLine2, header, ...rows.map(serializeRow)].join(CRLF) +
    CRLF

  const filename = `chia-${county.county_fips}-${slugify(county.county_name)}-${methodology.methodology_version}.csv`

  return { filename, csv }
}
