"""Response models for the CE-E14a national (per-state) dimension-scores endpoint.

``GET /api/v1/states/dimension-scores`` returns, for every state, a
**display-only** per-dimension summary of that state's counties: the median of
the counties' persisted CHIA access-dimension scores for the v0.1 period.

This is a presentational aggregate, computed at request time from the already
persisted, versioned county ``dimension_score`` rows. It is **not** a validated
state-level CHIA score, is never persisted, and does not change the CHIA v0.1
analytical methodology (see
``Documentation/NATIONAL_MAP_STATE_SUMMARY.md.txt``). The median inherits the
provenance of the county scores it summarises: methodology version ``v0.1`` and
source vintage ``HRSA Data Warehouse snapshot 2026-08-29`` (CE-E12B).

Counties with no available score for a dimension are excluded from that
dimension's median; a state with no available county for a dimension reports
``median = null`` / ``available = false``. All 51 states / state-equivalents are
always represented.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


_FROZEN = ConfigDict(frozen=True)


class StateDimensionMedian(BaseModel):
    """One access dimension's display-only median for one state."""

    model_config = _FROZEN

    dimension_id: str = Field(
        ..., description="Canonical dimension id (e.g. 'PRIMARY_CARE'), matching CE-B02 / CE-E09."
    )
    available: bool = Field(
        ...,
        description="True when at least one county in the state has an available persisted score.",
    )
    median: float | None = Field(
        None,
        description=(
            "Request-time median of the state's counties' persisted "
            "dimension_score.score for this dimension (statistics.median: the "
            "mean of the two central values when the count is even). null when "
            "no county in the state has an available score. Never persisted."
        ),
    )
    county_count: int = Field(
        ..., ge=0, description="Counties / county-equivalents in the state (canonical universe)."
    )
    available_county_count: int = Field(
        ...,
        ge=0,
        description="Counties in the state with a non-null persisted score for this dimension.",
    )


class StateDimensionMedians(BaseModel):
    """The four access-dimension medians for one state, canonical order
    (primary care, dental, mental health, MUA/P)."""

    model_config = _FROZEN

    state_fips: str = Field(
        ..., min_length=2, max_length=2, pattern=r"^\d{2}$",
        description="Two-character state FIPS string.",
    )
    primary_care: StateDimensionMedian
    dental: StateDimensionMedian
    mental_health: StateDimensionMedian
    mua_p: StateDimensionMedian


class NationalDimensionScoresResponse(BaseModel):
    """Per-state display-only dimension medians for the whole country, v0.1."""

    model_config = _FROZEN

    period: str = Field(..., description="Persisted methodology period (v0.1).")
    aggregation: str = Field(
        ...,
        description=(
            "Human-readable statement of the (display-only) aggregation rule, "
            "for API consumers and to keep the value self-documenting."
        ),
    )
    count: int = Field(..., ge=0, description="Number of states represented (51).")
    states: list[StateDimensionMedians] = Field(
        ..., description="Every state, ordered by state_fips ascending."
    )


class NationalScoresErrorResponse(BaseModel):
    """Structured error body (503)."""

    model_config = _FROZEN

    detail: str
