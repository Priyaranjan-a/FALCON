"""Shared field types.

``Email`` validates RFC 5321 dot-atom syntax without rejecting internal
domains. FALCON is deployed on-premises and in air-gapped networks where
addresses such as ``analyst@agency.local`` are normal, and general-purpose
validators refuse those special-use names.
"""
from __future__ import annotations

import re
from typing import Annotated

from pydantic import AfterValidator

_LOCAL = re.compile(r"^[A-Za-z0-9!#$%&'*+/=?^_`{|}~-]+(\.[A-Za-z0-9!#$%&'*+/=?^_`{|}~-]+)*$")
_LABEL = re.compile(r"^[A-Za-z0-9]([A-Za-z0-9-]{0,61}[A-Za-z0-9])?$")


def normalise_email(value: str) -> str:
    value = value.strip()
    if len(value) > 254 or value.count("@") != 1:
        raise ValueError("Enter a valid email address")
    local, domain = value.rsplit("@", 1)
    if not local or len(local) > 64 or not _LOCAL.match(local):
        raise ValueError("Enter a valid email address")
    labels = domain.split(".")
    if not domain or any(not _LABEL.match(label) for label in labels):
        raise ValueError("Enter a valid email address")
    return f"{local}@{domain}".lower()


Email = Annotated[str, AfterValidator(normalise_email)]
