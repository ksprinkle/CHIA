/**
 * TypeScript mirrors of the CE-B01 / CE-B02 API response contracts.
 *
 * These types must stay in lock-step with `app/schemas/county.py`
 * (`CountyListResponse`) and `app/schemas/explorer.py` (`ExplorerResponse`).
 * They describe the shape of persisted, server-assembled data only -- the
 * frontend performs no analytical calculation and derives no values.
 */

/** One canonical U.S. county / county-equivalent (GET /api/v1/counties). */
export interface County {
  county_fips: string
  state_fips: string
  state_abbr: string
  /** Returned verbatim from the canonical `county` table (never enriched). */
  county_name: string
  /** Returned verbatim from the canonical `county` table (never enriched). */
  state_name: string
}

/** Envelope for GET /api/v1/counties. */
export interface CountyListResponse {
  count: number
  counties: County[]
}

/** County identity block of the Explorer read model. */
export interface CountyBlock {
  county_fips: string
  county_name: string
  state_abbr: string
  state_name: string
}

/** Applicable canonical county-period. */
export interface PeriodBlock {
  value: string
  completeness_status: string | null
}

/** A dimension's canonical primary variable for the county-period. */
export interface PrimaryMeasure {
  variable_id: string
  display_name: string
  unit: string | null
  raw_value: number | null
  normalized_value: number | null
  normalization_method: string | null
  quality_flag: string | null
}

/** One declared supporting variable's persisted value. */
export interface SupportingEvidenceItem {
  variable_id: string
  display_name: string
  unit: string | null
  direction: string | null
  raw_value: number | null
  quality_flag: string | null
}

/** One of the four canonical access dimensions. */
export interface DimensionProfile {
  dimension_id: string
  dimension_name: string
  description: string | null
  primary_variable_id: string
  calculation_method: string | null
  direction: string | null
  normalized: boolean
  available: boolean
  score: number | null
  score_status: string | null
  source_id: number | null
  primary_measure: PrimaryMeasure
  supporting_evidence: SupportingEvidenceItem[]
}

/** The four dimensions, keyed as in the response contract. */
export interface AccessProfile {
  primary_care: DimensionProfile
  dental: DimensionProfile
  mental_health: DimensionProfile
  mua_p: DimensionProfile
}

/** Persisted experimental composite (never recomputed client-side). */
export interface ExperimentalComposite {
  label: string
  composite_value: number | null
  status: string | null
  missing_dimensions: string[]
}

/** One persisted source record. */
export interface SourceRef {
  source_id: number
  source_name: string
  publisher: string | null
  dataset_name: string | null
  /** Source-data vintage (CE-E12B: the HRSA Data Warehouse snapshot date). */
  reference_period: string | null
  url: string | null
  accessed_at: string | null
  /** CE-E12B: exact Data/Processed build-input workbook for this source. */
  artifact_filename: string | null
  /** CE-E12B: SHA-256 of that build-input workbook's bytes. */
  content_sha256: string | null
}

export interface Provenance {
  sources: SourceRef[]
}

export interface MethodologyBlock {
  methodology_version: string
  name: string
  description: string | null
  status: string | null
  created_at: string | null
  normalization_method: string | null
}

/** Complete County Explorer read model (GET /api/v1/counties/{county_fips}/explorer). */
export interface ExplorerResponse {
  county: CountyBlock
  period: PeriodBlock
  access_profile: AccessProfile
  experimental_composite: ExperimentalComposite
  provenance: Provenance
  methodology: MethodologyBlock
}

/**
 * CE-E09 / CE-E10 state dimension-scores contract.
 *
 * Mirrors `app/schemas/state_scores.py` (`StateDimensionScoresResponse`):
 * every county in one state with its four persisted access-dimension scores
 * for the v0.1 period, returned verbatim. Used only to colour the CE-E10
 * state county choropleth -- no analytical value is computed client-side.
 */
export interface DimensionScoreEntry {
  dimension_id: string
  available: boolean
  score: number | null
  score_status: string | null
}

export interface CountyDimensionScores {
  county_fips: string
  completeness_status: string | null
  primary_care: DimensionScoreEntry
  dental: DimensionScoreEntry
  mental_health: DimensionScoreEntry
  mua_p: DimensionScoreEntry
}

/** Envelope for GET /api/v1/states/{state_fips}/dimension-scores. */
export interface StateDimensionScoresResponse {
  state_fips: string
  period: string
  count: number
  counties: CountyDimensionScores[]
}
