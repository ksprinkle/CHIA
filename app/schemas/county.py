"""Response models for the CHIA County API (governing specification, section 11.1).

``GET /api/v1/counties`` returns the canonical county universe. ``county_fips``
always serializes as a five-character string, never an integer.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class County(BaseModel):
    """A single canonical U.S. county / county-equivalent."""

    model_config = ConfigDict(frozen=True)

    county_fips: str = Field(
        ...,
        min_length=5,
        max_length=5,
        pattern=r"^\d{5}$",
        description="Five-character county FIPS code, always a string.",
    )
    state_fips: str = Field(..., description="State FIPS code, as stored.")
    state_abbr: str = Field(..., description="USPS state abbreviation, as stored.")
    county_name: str = Field(
        ...,
        description="County name exactly as stored in the canonical database.",
    )
    state_name: str = Field(
        ...,
        description="State name exactly as stored in the canonical database.",
    )


class CountyListResponse(BaseModel):
    """Canonical county-universe envelope for ``GET /api/v1/counties``."""

    model_config = ConfigDict(frozen=True)

    count: int = Field(..., ge=0, description="Number of counties returned.")
    counties: list[County] = Field(
        ...,
        description="Complete canonical county universe, ordered by county_fips ascending.",
    )
