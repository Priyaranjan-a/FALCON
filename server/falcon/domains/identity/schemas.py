from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, field_validator

from ...kernel.validation import Email

AssignableRole = Literal["admin", "security_lead", "analyst", "auditor", "viewer"]


def clean_person_name(value: str) -> str:
    value = " ".join(value.split())
    if len(value) < 2:
        raise ValueError("Enter a full name")
    return value


class SignInIn(BaseModel):
    email: Email
    password: str = Field(min_length=1, max_length=256)


class PasswordChangeIn(BaseModel):
    current_password: str = Field(min_length=1, max_length=256)
    new_password: str = Field(min_length=1, max_length=256)


class ActivateIn(BaseModel):
    token: str = Field(min_length=20, max_length=128)
    name: str = Field(min_length=2, max_length=120)
    password: str = Field(min_length=1, max_length=256)

    @field_validator("name")
    @classmethod
    def _name(cls, value: str) -> str:
        return clean_person_name(value)


class InviteIn(BaseModel):
    email: Email
    name: str = Field(min_length=2, max_length=120)
    role: AssignableRole

    @field_validator("name")
    @classmethod
    def _name(cls, value: str) -> str:
        return clean_person_name(value)


class MemberPatch(BaseModel):
    role: AssignableRole | None = None
    status: Literal["active", "disabled"] | None = None


class ProfilePatch(BaseModel):
    name: str = Field(min_length=2, max_length=120)

    @field_validator("name")
    @classmethod
    def _name(cls, value: str) -> str:
        return clean_person_name(value)


class TokenIn(BaseModel):
    name: str = Field(min_length=2, max_length=80)
    expires_in_days: Literal[7, 30, 90, 365] | None = 90


class MemberOut(BaseModel):
    id: str
    email: str
    name: str
    role: str
    status: str
    created_at: datetime
    last_sign_in_at: datetime | None
    invitation_expires_at: datetime | None = None


class SessionOut(BaseModel):
    id: str
    created_at: datetime
    last_seen_at: datetime
    expires_at: datetime
    ip: str | None
    user_agent: str | None
    current: bool


class TokenOut(BaseModel):
    id: str
    name: str
    prefix: str
    created_at: datetime
    expires_at: datetime | None
    last_used_at: datetime | None
