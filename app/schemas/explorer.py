"""Response models for the CE-B02 County Explorer read model.

``GET /api/v1/counties/{county_fips}/explorer`` returns one fully assembled,
read-only projection of the persisted canonical + analytical data for a county
and the v0.1 period (governing specification, section 11.2 / 11.3).

The identifier is ``county_fips`` (a five-character string), consistent with the
CE-B01 County API. No analytical value is recomputed here; every score, status,
and composite figure is the value persisted by CE-A00..A06.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


_FROZEN = ConfigDict(frozen=True)


class CountyBlock(BaseModel):
    """Canonical county identity, returned exactly as stored."""

    model_config = _FROZEN

    county_fips: str = Field(
        ..., min_length=5, max_length=5, pattern=r"^\d{5}$",
        description="Five-character county FIPS string.",
    )
    county_name: str = Field(..., description="Verbatim from the canonical county table.")
    state_abbr: str = Field(..., description="Verbatim from the canonical county table.")
    state_name: str = Field(..., description="Verbatim from the canonical county table.")


class PeriodBlock(BaseModel):
    """The applicable canonical county-period."""

    model_config = _FROZEN

    value: str = Field(..., description="Persisted county_period.period (v0.1).")
    completeness_status: str | None = Field(
        None, description="Persisted county_period.completeness_status."
    )


class PrimaryMeasure(BaseModel):
    """The dimension's canonical primary variable for this county-period."""

    model_config = _FROZEN

    variable_id: str
    display_name: str
    unit: str | None = None
    raw_value: float | None = Field(
        None, description="Persisted observation.raw_value for the primary variable."
    )
    normalized_value: float | None = Field(
        None,
        description=(
            "Persisted normalized_measure.normalized_value; null for the raw "
            "MUA/P dimension, which is not percentile-normalized in v0.1."
        ),
    )
    normalization_method: str | None = Field(
        None, description="Persisted normalized_measure.normalization_method; null for MUA/P."
    )
    quality_flag: str | None = Field(
        None, description="Persisted observation.quality_flag."
    )


class SupportingEvidenceItem(BaseModel):
    """One declared supporting variable's persisted value (raw only in v0.1).

    Supporting evidence explains the primary measure; it never alters the
    persisted dimension score (governing specification, section 13).
    """

    model_config = _FROZEN

    variable_id: str
    display_name: str
    unit: str | None = None
    direction: str | None = None
    raw_value: float | None = None
    quality_flag: str | None = None


class DimensionProfile(BaseModel):
    """One of the four canonical access dimensions for this county-period."""

    model_config = _FROZEN

    dimension_id: str
    dimension_name: str
    description: str | None = None
    primary_variable_id: str
    calculation_method: str | None = Field(
        None,
        description="Persisted dimension_definition.calculation_method, verbatim (not corrected).",
    )
    direction: str | None = Field(
        None, description="Persisted variable_definition.direction of the primary variable."
    )
    normalized: bool = Field(
        ...,
        description=(
            "True when the persisted dimension score is derived from a "
            "normalized_measure; False for the raw MUA/P dimension."
        ),
    )
    available: bool = Field(
        ...,
        description="True when a persisted dimension score exists (score is not null).",
    )
    score: float | None = Field(
        None, description="Persisted dimension_score.score. Never recomputed."
    )
    score_status: str | None = Field(
        None, description="Persisted dimension_score.status."
    )
    source_id: int | None = Field(
        None, description="Provenance link (variable_definition.source_id of the primary variable)."
    )
    primary_measure: PrimaryMeasure
    supporting_evidence: list[SupportingEvidenceItem]


class AccessProfile(BaseModel):
    """The four canonical dimensions, keyed as in the response contract."""

    model_config = _FROZEN

    primary_care: DimensionProfile
    dental: DimensionProfile
    mental_health: DimensionProfile
    mua_p: DimensionProfile


class ExperimentalComposite(BaseModel):
    """The persisted experimental composite (governing specification, section 9).

    Returned exactly as persisted by CE-A05. It is never averaged or otherwise
    recomputed in the request. All four dimension scores are required; if any is
    missing, ``composite_value`` is null and ``missing_dimensions`` names them.
    """

    model_config = _FROZEN

    label: str = Field(
        "Experimental / Provisional",
        description="Fixed label required by governing specification section 9.",
    )
    composite_value: float | None = Field(
        None, description="Persisted composite_score.composite_value. Never recomputed."
    )
    status: str | None = Field(None, description="Persisted composite_score.status.")
    missing_dimensions: list[str] = Field(
        default_factory=list,
        description="Persisted composite_score.missing_dimensions, parsed. Empty when complete.",
    )


class SourceRef(BaseModel):
    """One persisted source record."""

    model_config = _FROZEN

    source_id: int
    source_name: str
    publisher: str | None = None
    dataset_name: str | None = None
    reference_period: str | None = None
    url: str | None = None
    accessed_at: str | None = None


class Provenance(BaseModel):
    """Persisted source metadata for the variables used in this Explorer view."""

    model_config = _FROZEN

    sources: list[SourceRef]


class MethodologyBlock(BaseModel):
    """Persisted methodology metadata (governing specification, section 15)."""

    model_config = _FROZEN

    methodology_version: str
    name: str
    description: str | None = None
    status: str | None = None
    created_at: str | None = None
    normalization_method: str | None = Field(
        None, description="Persisted normalized_measure.normalization_method."
    )


class ExplorerResponse(BaseModel):
    """Complete County Explorer read model for one county and the v0.1 period."""

    model_config = _FROZEN

    county: CountyBlock
    period: PeriodBlock
    access_profile: AccessProfile
    experimental_composite: ExperimentalComposite
    provenance: Provenance
    methodology: MethodologyBlock


class ExplorerErrorResponse(BaseModel):
    """Structured error body (404 / 422 / 503)."""

    model_config = _FROZEN

    detail: str
