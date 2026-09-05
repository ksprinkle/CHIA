-- ============================================================
-- CHIA v0.1
-- Methodology and Variable Definitions
-- ============================================================

PRAGMA foreign_keys = ON;

-- ============================================================
-- 1. METHODOLOGY
-- ============================================================

INSERT OR IGNORE INTO methodology (
    methodology_version,
    name,
    description,
    status
)
VALUES (
    'v0.1',
    'CHIA Access Profile v0.1',
    'Four-domain county-level healthcare access profile using validated geographic coverage measures, county percentile-rank normalization, and an experimental equal-weight composite burden measure.',
    'prototype'
);

-- ============================================================
-- 2. SOURCE RECORDS
-- ============================================================
-- CE-E12B: authoritative source-vintage and reproducibility metadata.
-- reference_period / url / accessed_at describe the HRSA Data Warehouse
-- snapshot the v0.1 pipeline consumed; artifact_filename / content_sha256
-- pin the exact Data/Processed build-input workbook (SHA-256 of its bytes).
-- Full catalogue and verification: Documentation/ANALYTICAL_DATA_SOURCES.md.txt.
-- These fields are presentation/provenance only -- no analytical script
-- reads the source table.

INSERT OR IGNORE INTO source (
    source_name,
    publisher,
    dataset_name,
    reference_period,
    url,
    accessed_at,
    artifact_filename,
    content_sha256
)
VALUES
(
    'Primary Care HPSA',
    'HRSA',
    'Primary Care HPSA Spatial Coverage',
    'HRSA Data Warehouse snapshot 2026-08-29',
    'https://data.hrsa.gov/data/download',
    '2026-08-29',
    'CHIA_Primary_Care_HPSA_Spatial_Coverage_Validated_FINAL.xlsx',
    '709e9ed6070f71e466b65b0928d1dbe23d3dd685ecfb81d4cb1cc0ee637c2d93'
),
(
    'Dental HPSA',
    'HRSA',
    'Dental HPSA Spatial Coverage',
    'HRSA Data Warehouse snapshot 2026-08-29',
    'https://data.hrsa.gov/data/download',
    '2026-08-29',
    'CHIA_Dental_HPSA_Spatial_Coverage_Validated_FINAL.xlsx',
    '3334807f5cd7ecbd2002e2a672705dfd1a7f2a36df43d313db0b234332c61065'
),
(
    'Mental Health HPSA',
    'HRSA',
    'Mental Health HPSA Spatial Coverage',
    'HRSA Data Warehouse snapshot 2026-08-29',
    'https://data.hrsa.gov/data/download',
    '2026-08-29',
    'CHIA_Mental_Health_HPSA_Spatial_Coverage_Validated_FINAL.xlsx',
    '72e6b52fa73247e6975ccb47bd09368bfc1f56f7a7f5ac14f95b8def67bb430b'
),
(
    'MUA/P',
    'HRSA',
    'MUA/P Spatial Coverage',
    'HRSA Data Warehouse snapshot 2026-08-29',
    'https://data.hrsa.gov/data/download',
    '2026-08-29',
    'CHIA_MUA_P_Spatial_Coverage_Validated.xlsx',
    '7e8b0fd83bed93f0a8d1f0939b79e7302a96fa218775dd7d7b41597ab922f218'
);

-- ============================================================
-- 3. PRIMARY VARIABLE DEFINITIONS
-- ============================================================

INSERT OR IGNORE INTO variable_definition (
    variable_id,
    variable_name,
    display_name,
    description,
    unit,
    direction
)
VALUES
(
    'PC_HPSA_GEOGRAPHIC_COVERAGE',
    'pc_hpsa_geographic_coverage',
    'Primary Care HPSA Geographic Coverage',
    'Percentage of county land area represented by the validated Primary Care geographic HPSA footprint.',
    'percent',
    'higher_burden'
),
(
    'DENTAL_HPSA_GEOGRAPHIC_COVERAGE',
    'dental_hpsa_geographic_coverage',
    'Dental HPSA Geographic Coverage',
    'Percentage of county land area represented by the validated Dental geographic HPSA footprint.',
    'percent',
    'higher_burden'
),
(
    'MH_HPSA_GEOGRAPHIC_COVERAGE',
    'mh_hpsa_geographic_coverage',
    'Mental Health HPSA Geographic Coverage',
    'Percentage of county land area represented by the validated Mental Health geographic HPSA footprint.',
    'percent',
    'higher_burden'
),
(
    'MUAP_GEOGRAPHIC_COVERAGE',
    'muap_geographic_coverage',
    'MUA/P Geographic Coverage',
    'Percentage of county land area represented by the validated MUA/P geographic footprint.',
    'percent',
    'higher_burden'
);

-- ============================================================
-- 4. DIMENSION DEFINITIONS
-- ============================================================

INSERT OR IGNORE INTO dimension_definition (
    dimension_id,
    dimension_name,
    description,
    primary_variable_id,
    supporting_variables,
    calculation_method,
    methodology_version
)
VALUES
(
    'PRIMARY_CARE',
    'Primary Care Access',
    'Geographic primary care shortage coverage at the county level.',
    'PC_HPSA_GEOGRAPHIC_COVERAGE',
    'PC_HPSA_AREA_WEIGHTED_SCORE, PC_HPSA_MAX_SCORE, PC_HPSA_DESIGNATION_COUNT',
    'Primary variable normalized using county percentile rank; supporting HPSA severity and designation measures displayed separately.',
    'v0.1'
),
(
    'DENTAL',
    'Dental Access',
    'Geographic dental shortage coverage at the county level.',
    'DENTAL_HPSA_GEOGRAPHIC_COVERAGE',
    'DENTAL_HPSA_AREA_WEIGHTED_SCORE, DENTAL_HPSA_MAX_SCORE, DENTAL_HPSA_DESIGNATION_COUNT',
    'Primary variable normalized using county percentile rank; supporting HPSA severity and designation measures displayed separately.',
    'v0.1'
),
(
    'MENTAL_HEALTH',
    'Mental Health Access',
    'Geographic mental health shortage coverage at the county level.',
    'MH_HPSA_GEOGRAPHIC_COVERAGE',
    'MH_HPSA_AREA_WEIGHTED_SCORE, MH_HPSA_MAX_SCORE, MH_HPSA_DESIGNATION_COUNT',
    'Primary variable normalized using county percentile rank; supporting HPSA severity and designation measures displayed separately.',
    'v0.1'
),
(
    'MUA_P',
    'MUA/P Access',
    'Geographic medically underserved area/population coverage at the county level.',
    'MUAP_GEOGRAPHIC_COVERAGE',
    'MUAP_MEAN_SCORE, MUAP_MAX_SCORE, MUAP_FEATURE_COUNT, MUA_FEATURE_COUNT, MUP_FEATURE_COUNT, MUAP_UNIQUE_SOURCE_COUNT',
    'Primary variable retained as raw geographic coverage; supporting MUA/P measures displayed separately and no MUA/P normalization is applied.',
    'v0.1'
);

-- ============================================================
-- SUPPORTING VARIABLE DEFINITIONS
-- ============================================================

INSERT OR IGNORE INTO variable_definition (
    variable_id,
    variable_name,
    display_name,
    description,
    unit,
    direction
)
VALUES
(
    'PC_HPSA_AREA_WEIGHTED_SCORE',
    'pc_hpsa_area_weighted_score',
    'Primary Care HPSA Area-Weighted Score',
    'Area-weighted Primary Care HPSA severity score.',
    'score',
    'higher_burden'
),
(
    'PC_HPSA_MAX_SCORE',
    'pc_hpsa_max_score',
    'Primary Care HPSA Maximum Score',
    'Maximum Primary Care HPSA severity score.',
    'score',
    'higher_burden'
),
(
    'PC_HPSA_DESIGNATION_COUNT',
    'pc_hpsa_designation_count',
    'Primary Care HPSA Designation Count',
    'Count of Primary Care geographic HPSA designations.',
    'count',
    'higher_burden'
),
(
    'DENTAL_HPSA_AREA_WEIGHTED_SCORE',
    'dental_hpsa_area_weighted_score',
    'Dental HPSA Area-Weighted Score',
    'Area-weighted Dental HPSA severity score.',
    'score',
    'higher_burden'
),
(
    'DENTAL_HPSA_MAX_SCORE',
    'dental_hpsa_max_score',
    'Dental HPSA Maximum Score',
    'Maximum Dental HPSA severity score.',
    'score',
    'higher_burden'
),
(
    'DENTAL_HPSA_DESIGNATION_COUNT',
    'dental_hpsa_designation_count',
    'Dental HPSA Designation Count',
    'Count of Dental geographic HPSA designations.',
    'count',
    'higher_burden'
),
(
    'MH_HPSA_AREA_WEIGHTED_SCORE',
    'mh_hpsa_area_weighted_score',
    'Mental Health HPSA Area-Weighted Score',
    'Area-weighted Mental Health HPSA severity score.',
    'score',
    'higher_burden'
),
(
    'MH_HPSA_MAX_SCORE',
    'mh_hpsa_max_score',
    'Mental Health HPSA Maximum Score',
    'Maximum Mental Health HPSA severity score.',
    'score',
    'higher_burden'
),
(
    'MH_HPSA_DESIGNATION_COUNT',
    'mh_hpsa_designation_count',
    'Mental Health HPSA Designation Count',
    'Count of Mental Health geographic HPSA designations.',
    'count',
    'higher_burden'
),
(
    'MUAP_MEAN_SCORE',
    'muap_mean_score',
    'MUA/P Mean Score',
    'Mean MUA/P score among intersecting validated features.',
    'score',
    'higher_burden'
),
(
    'MUAP_MAX_SCORE',
    'muap_max_score',
    'MUA/P Maximum Score',
    'Maximum MUA/P score among intersecting validated features.',
    'score',
    'higher_burden'
),
(
    'MUAP_FEATURE_COUNT',
    'muap_feature_count',
    'MUA/P Feature Count',
    'Number of intersecting MUA/P features.',
    'count',
    'higher_burden'
),
(
    'MUA_FEATURE_COUNT',
    'mua_feature_count',
    'MUA Feature Count',
    'Number of MUA features.',
    'count',
    'higher_burden'
),
(
    'MUP_FEATURE_COUNT',
    'mup_feature_count',
    'MUP Feature Count',
    'Number of MUP features.',
    'count',
    'higher_burden'
),
(
    'MUAP_UNIQUE_SOURCE_COUNT',
    'muap_unique_source_count',
    'MUA/P Unique Source Count',
    'Number of unique MUA/P source designations.',
    'count',
    'higher_burden'
);


-- -- ============================================================
-- 5. NORMALIZATION METHOD
-- ============================================================
-- Applied to the primary geographic coverage variables for:
-- Primary Care, Dental, and Mental Health.
--
-- Methodology:
-- county_percentile_rank_average
--
-- Higher normalized values = greater access burden.
-- Missing observations remain missing.
-- Valid zero values remain zero.
-- Ties use average rank.
--
-- MUA/P geographic coverage is retained as a raw measure
-- and is not percentile-normalized in v0.1.
--
-- Actual normalized values are generated by the v0.1
-- processing pipeline, not stored here.

-- ============================================================
-- 6. EXPERIMENTAL COMPOSITE
-- ============================================================
-- Experimental Composite Access Burden:
--
--   (Primary Care + Dental + Mental Health + MUA/P) / 4
--
-- Each dimension contributes 25%.
-- Composite is calculated only when all four dimensions
-- are available.
-- Missing dimensions are never substituted with zero.
--
-- Composite values are generated by the processing pipeline.