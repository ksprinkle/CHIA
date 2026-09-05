-- ============================================================
-- Community Health Intelligence Atlas (CHIA)
-- v0.1 Canonical Data Model
-- ============================================================

PRAGMA foreign_keys = ON;

-- ============================================================
-- 1. COUNTY
-- ============================================================

CREATE TABLE IF NOT EXISTS county (
    county_fips TEXT PRIMARY KEY,
    state_fips TEXT NOT NULL,
    county_name TEXT NOT NULL,
    state_name TEXT NOT NULL,
    state_abbr TEXT NOT NULL
);

-- ============================================================
-- 2. COUNTY PERIOD
-- ============================================================

CREATE TABLE IF NOT EXISTS county_period (
    county_period_id INTEGER PRIMARY KEY AUTOINCREMENT,
    county_fips TEXT NOT NULL,
    period TEXT NOT NULL,
    completeness_status TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY (county_fips)
        REFERENCES county(county_fips),

    UNIQUE (county_fips, period)
);

-- ============================================================
-- 3. SOURCE
-- ============================================================

CREATE TABLE IF NOT EXISTS source (
    source_id INTEGER PRIMARY KEY AUTOINCREMENT,
    source_name TEXT NOT NULL,
    publisher TEXT,
    dataset_name TEXT,
    reference_period TEXT,
    url TEXT,
    accessed_at TEXT,
    -- CE-E12B source-vintage / reproducibility metadata. Nullable, additive,
    -- presentation-only: no analytical script reads the source table.
    -- artifact_filename: the exact Data/Processed build-input workbook this
    -- source was loaded from; content_sha256: SHA-256 of that file's bytes.
    -- Authoritative values catalogued in
    -- Documentation/ANALYTICAL_DATA_SOURCES.md.txt.
    artifact_filename TEXT,
    content_sha256 TEXT
);

-- ============================================================
-- 4. METHODOLOGY
-- ============================================================

CREATE TABLE IF NOT EXISTS methodology (
    methodology_version TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    description TEXT,
    status TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);

-- ============================================================
-- 5. VARIABLE DEFINITION
-- ============================================================

CREATE TABLE IF NOT EXISTS variable_definition (
    variable_id TEXT PRIMARY KEY,
    variable_name TEXT NOT NULL,
    display_name TEXT NOT NULL,
    description TEXT,
    unit TEXT,
    source_id INTEGER,
    direction TEXT,

    FOREIGN KEY (source_id)
        REFERENCES source(source_id)
);

-- ============================================================
-- 6. OBSERVATION
-- ============================================================

CREATE TABLE IF NOT EXISTS observation (
    observation_id INTEGER PRIMARY KEY AUTOINCREMENT,
    county_period_id INTEGER NOT NULL,
    variable_id TEXT NOT NULL,
    raw_value REAL,
    raw_text TEXT,
    quality_flag TEXT,
    notes TEXT,

    FOREIGN KEY (county_period_id)
        REFERENCES county_period(county_period_id),

    FOREIGN KEY (variable_id)
        REFERENCES variable_definition(variable_id),

    UNIQUE (county_period_id, variable_id)
);

-- ============================================================
-- 7. NORMALIZED MEASURE
-- ============================================================

CREATE TABLE IF NOT EXISTS normalized_measure (
    observation_id INTEGER NOT NULL,
    methodology_version TEXT NOT NULL,
    normalized_value REAL,
    normalization_method TEXT NOT NULL,

    PRIMARY KEY (
        observation_id,
        methodology_version
    ),

    FOREIGN KEY (observation_id)
        REFERENCES observation(observation_id),

    FOREIGN KEY (methodology_version)
        REFERENCES methodology(methodology_version)
);

-- ============================================================
-- 8. DIMENSION DEFINITION
-- ============================================================

CREATE TABLE IF NOT EXISTS dimension_definition (
    dimension_id TEXT PRIMARY KEY,
    dimension_name TEXT NOT NULL,
    description TEXT,
    primary_variable_id TEXT NOT NULL,
    supporting_variables TEXT,
    calculation_method TEXT,
    methodology_version TEXT NOT NULL,

    FOREIGN KEY (primary_variable_id)
        REFERENCES variable_definition(variable_id),

    FOREIGN KEY (methodology_version)
        REFERENCES methodology(methodology_version)
);

-- ============================================================
-- 9. DIMENSION SCORE
-- ============================================================

CREATE TABLE IF NOT EXISTS dimension_score (
    county_period_id INTEGER NOT NULL,
    dimension_id TEXT NOT NULL,
    score REAL,
    methodology_version TEXT NOT NULL,
    status TEXT,

    PRIMARY KEY (
        county_period_id,
        dimension_id,
        methodology_version
    ),

    FOREIGN KEY (county_period_id)
        REFERENCES county_period(county_period_id),

    FOREIGN KEY (dimension_id)
        REFERENCES dimension_definition(dimension_id),

    FOREIGN KEY (methodology_version)
        REFERENCES methodology(methodology_version)
);

-- ============================================================
-- 10. EXPERIMENTAL COMPOSITE SCORE
-- ============================================================

CREATE TABLE IF NOT EXISTS composite_score (
    county_period_id INTEGER NOT NULL,
    methodology_version TEXT NOT NULL,
    composite_value REAL,
    status TEXT,
    missing_dimensions TEXT,

    PRIMARY KEY (
        county_period_id,
        methodology_version
    ),

    FOREIGN KEY (county_period_id)
        REFERENCES county_period(county_period_id),

    FOREIGN KEY (methodology_version)
        REFERENCES methodology(methodology_version)
);

-- ============================================================
-- INDEXES
-- ============================================================

CREATE INDEX IF NOT EXISTS idx_county_period_fips
    ON county_period(county_fips);

CREATE INDEX IF NOT EXISTS idx_observation_county_period
    ON observation(county_period_id);

CREATE INDEX IF NOT EXISTS idx_observation_variable
    ON observation(variable_id);

CREATE INDEX IF NOT EXISTS idx_dimension_score_county
    ON dimension_score(county_period_id);

CREATE INDEX IF NOT EXISTS idx_composite_score_county
    ON composite_score(county_period_id);