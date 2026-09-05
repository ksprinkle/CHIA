import { deriveDataVintage } from './provenance'
import type { SourceRef } from './types'

function source(overrides: Partial<SourceRef>): SourceRef {
  return {
    source_id: 1,
    source_name: 'Primary Care HPSA',
    publisher: 'HRSA',
    dataset_name: 'Primary Care HPSA Spatial Coverage',
    reference_period: 'HRSA Data Warehouse snapshot 2026-08-29',
    url: 'https://data.hrsa.gov/data/download',
    accessed_at: '2026-08-29',
    artifact_filename: 'CHIA_Primary_Care_HPSA_Spatial_Coverage_Validated_FINAL.xlsx',
    content_sha256: '709e9ed6070f71e466b65b0928d1dbe23d3dd685ecfb81d4cb1cc0ee637c2d93',
    ...overrides,
  }
}

describe('deriveDataVintage', () => {
  it('extracts the ISO date from a single shared reference period', () => {
    const sources = [
      source({ source_id: 1 }),
      source({ source_id: 2, source_name: 'Dental HPSA' }),
      source({ source_id: 3, source_name: 'Mental Health HPSA' }),
      source({ source_id: 4, source_name: 'MUA/P' }),
    ]
    expect(deriveDataVintage(sources)).toBe('2026-08-29')
  })

  it('is derived, not hard-coded: follows a different shared reference period', () => {
    const sources = [
      source({
        source_id: 1,
        reference_period: 'HRSA Data Warehouse snapshot 2025-01-15',
        accessed_at: '2025-01-15',
      }),
      source({
        source_id: 2,
        reference_period: 'HRSA Data Warehouse snapshot 2025-01-15',
        accessed_at: '2025-01-15',
      }),
    ]
    expect(deriveDataVintage(sources)).toBe('2025-01-15')
  })

  it('falls back to a single shared accessed_at when reference periods lack a date', () => {
    const sources = [
      source({ source_id: 1, reference_period: 'v0.1 source period', accessed_at: '2026-08-29' }),
      source({ source_id: 2, reference_period: 'v0.1 source period', accessed_at: '2026-08-29' }),
    ]
    expect(deriveDataVintage(sources)).toBe('2026-08-29')
  })

  it('returns null when sources disagree on the reference period and on accessed_at', () => {
    const sources = [
      source({
        source_id: 1,
        reference_period: 'HRSA Data Warehouse snapshot 2026-08-29',
        accessed_at: '2026-08-29',
      }),
      source({
        source_id: 2,
        reference_period: 'HRSA Data Warehouse snapshot 2025-01-15',
        accessed_at: '2025-01-15',
      }),
    ]
    expect(deriveDataVintage(sources)).toBeNull()
  })

  it('returns null when there is no vintage metadata at all', () => {
    expect(deriveDataVintage([])).toBeNull()
    expect(
      deriveDataVintage([source({ reference_period: null, accessed_at: null })]),
    ).toBeNull()
  })
})
