from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, field_validator, model_validator

from ..horizon.model import TOLERANCES

SECTORS = (
    "government", "defence", "banking", "insurance", "telecom", "energy",
    "healthcare", "technology", "manufacturing", "transport", "education", "other",
)
Sector = Literal[
    "government", "defence", "banking", "insurance", "telecom", "energy",
    "healthcare", "technology", "manufacturing", "transport", "education", "other",
]
Scenario = Literal["aggressive", "moderate", "conservative", "custom"]
Uncertainty = Literal["narrow", "moderate", "wide"]


class ThreatModelIn(BaseModel):
    crqc_scenario: Scenario = "moderate"
    crqc_median_year: float | None = Field(default=None, ge=2027, le=2070)
    crqc_uncertainty: Uncertainty | None = None
    risk_tolerance: float = 0.05

    @field_validator("risk_tolerance")
    @classmethod
    def _tolerance(cls, value: float) -> float:
        if value not in TOLERANCES:
            raise ValueError(f"Risk tolerance must be one of {', '.join(f'{t:.0%}' for t in TOLERANCES)}")
        return value

    @model_validator(mode="after")
    def _custom_fields(self) -> ThreatModelIn:
        if self.crqc_scenario == "custom":
            if self.crqc_median_year is None:
                raise ValueError("A custom scenario needs a median arrival year")
            self.crqc_uncertainty = self.crqc_uncertainty or "moderate"
        else:
            self.crqc_median_year = None
            self.crqc_uncertainty = None
        return self


def clean_name(value: str) -> str:
    value = " ".join(value.split())
    if len(value) < 2:
        raise ValueError("Enter the organisation's name")
    return value


def clean_country(value: str) -> str:
    if len(value) != 2 or not value.isalpha():
        raise ValueError("Use a two-letter ISO country code")
    return value.upper()


class OrganisationProfileIn(BaseModel):
    name: str = Field(min_length=2, max_length=160)
    sector: Sector
    country: str = Field(min_length=2, max_length=2)

    @field_validator("name")
    @classmethod
    def _name(cls, value: str) -> str:
        return clean_name(value)

    @field_validator("country")
    @classmethod
    def _country(cls, value: str) -> str:
        return clean_country(value)


class OrganisationProfilePatch(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=160)
    sector: Sector | None = None
    country: str | None = Field(default=None, min_length=2, max_length=2)

    @field_validator("name")
    @classmethod
    def _name(cls, value: str | None) -> str | None:
        return None if value is None else clean_name(value)

    @field_validator("country")
    @classmethod
    def _country(cls, value: str | None) -> str | None:
        return None if value is None else clean_country(value)
