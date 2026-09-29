from __future__ import annotations

import re
from typing import Literal

from pydantic import BaseModel, Field, field_validator

Kind = Literal["application", "service", "product", "platform", "infrastructure", "device", "data_store"]
Criticality = Literal["critical", "high", "moderate", "low"]
Classification = Literal["secret", "restricted", "confidential", "internal", "public"]
Exposure = Literal["external", "partner", "internal", "isolated"]
Lifecycle = Literal["planned", "active", "sunsetting", "retired"]
Environment = Literal["production", "staging", "development", "disaster_recovery"]

_CODE = re.compile(r"^[A-Z0-9][A-Z0-9-]{1,23}$")
_TAG = re.compile(r"^[a-z0-9][a-z0-9-]{0,31}$")


def _clean_code(value: str) -> str:
    value = value.strip().upper().replace(" ", "-")
    if not _CODE.match(value):
        raise ValueError("Use 2–24 capital letters, digits or hyphens, e.g. PAY-GW")
    return value


def _clean_tags(value: list[str]) -> list[str]:
    cleaned = []
    for tag in value:
        tag = tag.strip().lower().replace(" ", "-")
        if not _TAG.match(tag):
            raise ValueError(f"Tag “{tag}” must use lowercase letters, digits or hyphens")
        if tag not in cleaned:
            cleaned.append(tag)
    if len(cleaned) > 12:
        raise ValueError("Use at most 12 tags")
    return cleaned


def _clean_name(value: str) -> str:
    cleaned = _clean_text(value)
    if not cleaned or len(cleaned) < 2:
        raise ValueError("Enter the system's name")
    return cleaned


def _clean_text(value: str | None) -> str | None:
    if value is None:
        return None
    value = " ".join(value.split())
    return value or None


class SystemIn(BaseModel):
    code: str = Field(min_length=2, max_length=24)
    name: str = Field(min_length=2, max_length=160)
    description: str | None = Field(default=None, max_length=2000)
    kind: Kind
    lifecycle: Lifecycle = "active"
    environment: Environment = "production"
    exposure: Exposure
    criticality: Criticality
    data_classification: Classification
    data_shelf_life_years: int = Field(ge=0, le=100)
    migration_years: float = Field(gt=0, le=20)
    owner: str | None = Field(default=None, max_length=160)
    team: str | None = Field(default=None, max_length=160)
    tags: list[str] = Field(default_factory=list)

    @field_validator("code")
    @classmethod
    def _code(cls, v: str) -> str:
        return _clean_code(v)

    @field_validator("name")
    @classmethod
    def _name(cls, v: str) -> str:
        return _clean_name(v)

    @field_validator("owner", "team")
    @classmethod
    def _text(cls, v: str | None) -> str | None:
        return _clean_text(v)

    @field_validator("description")
    @classmethod
    def _description(cls, v: str | None) -> str | None:
        return (v or "").strip() or None

    @field_validator("tags")
    @classmethod
    def _tags(cls, v: list[str]) -> list[str]:
        return _clean_tags(v)

    @field_validator("migration_years")
    @classmethod
    def _years(cls, v: float) -> float:
        return round(v, 1)


class SystemPatch(BaseModel):
    code: str | None = Field(default=None, min_length=2, max_length=24)
    name: str | None = Field(default=None, min_length=2, max_length=160)
    description: str | None = Field(default=None, max_length=2000)
    kind: Kind | None = None
    lifecycle: Lifecycle | None = None
    environment: Environment | None = None
    exposure: Exposure | None = None
    criticality: Criticality | None = None
    data_classification: Classification | None = None
    data_shelf_life_years: int | None = Field(default=None, ge=0, le=100)
    migration_years: float | None = Field(default=None, gt=0, le=20)
    owner: str | None = Field(default=None, max_length=160)
    team: str | None = Field(default=None, max_length=160)
    tags: list[str] | None = None

    @field_validator("code")
    @classmethod
    def _code(cls, v: str | None) -> str | None:
        return None if v is None else _clean_code(v)

    @field_validator("name")
    @classmethod
    def _name(cls, v: str | None) -> str | None:
        return None if v is None else _clean_name(v)

    @field_validator("owner", "team")
    @classmethod
    def _text(cls, v: str | None) -> str | None:
        return _clean_text(v)

    @field_validator("description")
    @classmethod
    def _description(cls, v: str | None) -> str | None:
        return (v or "").strip() or None

    @field_validator("tags")
    @classmethod
    def _tags(cls, v: list[str] | None) -> list[str] | None:
        return None if v is None else _clean_tags(v)

    @field_validator("migration_years")
    @classmethod
    def _years(cls, v: float | None) -> float | None:
        return None if v is None else round(v, 1)
