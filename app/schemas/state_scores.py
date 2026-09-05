"""Response models for the CE-E09 state dimension-scores endpoint.

``GET /api/v1/states/{state_fips}/dimension-scores`` returns, for every county
in one state, the four persisted CHIA access-dimension scores for the v0.1
period -- the minimum needed to paint a state-level county choropleth without
fetching a full per-county Explorer read model.

Every value is returned **verbatim** from the persisted analytical tables
(``dimension_score``, ``county_period``). No score is recomputed, normalized,
averaged, or otherwise altered here; this endpoint performs no analytical
calculation and never writes to the database. ``county_fips`` / ``state_fips``
always serialize as fixed-width strings, consistent with CE-B01 / CE-B02.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


_FROZEN = ConfigDict(frozen=True)


class DimensionScoreEntry(BaseModel):
    """One access dimension's persisted score for one county-period."""

    model_config = _FROZEN

    dimension_id: str = Field(
        ..., description="Persisted dimension_score.dimension_id (e.g. 'PRIMARY_CARE')."
    )
    available: bool = Field(
        ...,
        description="True when a persisted dimension score exists (score is not null).",
    )
    score: float | None = Field(
        None,
        description="Persisted dimension_score.score, verbatim. Never recomputed.",
    )
    score_status: str | None = Field(
        None, description="Persisted dimension_score.status, verbatim."
    )


class CountyDimensionScores(BaseModel):
    """The four access dimensions for one county, keyed as in CE-B02's
    ``access_profile`` (canonical order: primary care, dental, mental health,
    MUA/P)."""

    model_config = _FROZEN

    county_fips: str = Field(
        ..., min_length=5, max_length=5, pattern=r"^\d{5}$",
        description="Five-character county FIPS string.",
    )
    completeness_status: str | None = Field(
        None, description="Persisted county_period.completeness_status, verbatim."
    )
    primary_care: DimensionScoreEntry
    dental: DimensionScoreEntry
    mental_health: DimensionScoreEntry
    mua_p: DimensionScoreEntry


class StateDimensionScoresResponse(BaseModel):
    """All counties' dimension scores for one state and the v0.1 period."""

    model_config = _FROZEN

    state_fips: str = Field(
        ..., min_length=2, max_length=2, pattern=r"^\d{2}$",
        description="Two-character state FIPS string.",
    )
    period: str = Field(..., description="Persisted methodology period (v0.1).")
    count: int = Field(..., ge=0, description="Number of counties returned.")
    counties: list[CountyDimensionScores] = Field(
        ...,
        description="Every county in the state, ordered by county_fips ascending.",
    )


class StateScoresErrorResponse(BaseModel):
    """Structured error body (404 / 422 / 503)."""

    model_config = _FROZEN

    detail: str
