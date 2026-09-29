"""What detectors emit.

A :class:`Finding` is one piece of evidence that a cryptographic artefact
exists. Its ``identity`` is what makes two findings the *same* artefact (two
calls that both use AES-256-GCM, two copies of one certificate); the
fingerprint of ``(kind, identity)`` is stable across scans, so an artefact keeps
its history as a system evolves.

Findings cross a process boundary (worker to server), so they are plain data.
"""
from __future__ import annotations

import hashlib
import json
import re
from dataclasses import asdict, dataclass, field
from typing import Any

from .catalogue import AlgorithmRef, assess, display_name, protocol_assessment

KINDS = ("algorithm", "key", "certificate", "protocol", "library", "hardware", "cloud_service")

# Values that look like secrets are masked before any snippet leaves the worker.
_SECRETISH = re.compile(r"(?<![A-Za-z0-9+/=_-])([A-Za-z0-9+/_-]{32,}={0,2})(?![A-Za-z0-9+/=_-])")
_ASSIGNED_SECRET = re.compile(
    r"(?i)((?:password|passwd|secret|token|api[_-]?key|private[_-]?key|passphrase|credential)s?\s*[:=]\s*)([\"']?)([^\"'\s,;)]{4,})"
)


def mask(line: str) -> str:
    line = _ASSIGNED_SECRET.sub(lambda m: f"{m.group(1)}{m.group(2)}••••••", line)
    return _SECRETISH.sub(lambda m: m.group(1)[:4] + "…" + "•" * 6, line)


@dataclass
class Evidence:
    path: str
    line: int | None = None
    column: int | None = None
    snippet: list[tuple[int, str]] | None = None  # (line number, masked text)


@dataclass
class Relation:
    relation: str  # e.g. "uses-key", "signed-with", "negotiates", "provides"
    kind: str
    identity: dict[str, Any]
    name: str
    properties: dict[str, Any] = field(default_factory=dict)


@dataclass
class Finding:
    kind: str
    identity: dict[str, Any]
    name: str
    evidence: Evidence
    detector: str
    rule: str
    confidence: float
    function: str | None = None
    properties: dict[str, Any] = field(default_factory=dict)
    related: list[Relation] = field(default_factory=list)

    @property
    def fingerprint(self) -> str:
        return fingerprint(self.kind, self.identity)

    def as_message(self) -> dict[str, Any]:
        data = asdict(self)
        data["fingerprint"] = self.fingerprint
        data["related"] = [
            {**asdict(r), "fingerprint": fingerprint(r.kind, r.identity)} for r in self.related
        ]
        return data


def fingerprint(kind: str, identity: dict[str, Any]) -> str:
    present = {k: v for k, v in identity.items() if v not in (None, "", [], {})}
    canonical = json.dumps({"kind": kind, **present}, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(canonical.encode()).hexdigest()[:40]


def snippet(lines: list[str], index: int, radius: int = 1, width: int = 220) -> list[tuple[int, str]]:
    """Masked context around ``lines[index]`` (0-based); line numbers are 1-based."""
    start, end = max(0, index - radius), min(len(lines), index + radius + 1)
    out = []
    for i in range(start, end):
        text = lines[i].rstrip("\r\n").replace("\t", "    ")
        if len(text) > width:
            text = text[: width - 1] + "…"
        out.append((i + 1, mask(text)))
    return out


def algorithm_properties(ref: AlgorithmRef) -> dict[str, Any]:
    assessment = assess(ref)
    props: dict[str, Any] = {"assessment": assessment.as_dict()}
    return props


def algorithm_finding(
    ref: AlgorithmRef,
    evidence: Evidence,
    *,
    detector: str,
    rule: str,
    confidence: float,
    function: str | None = None,
    library: str | None = None,
    extra: dict[str, Any] | None = None,
) -> Finding:
    props = algorithm_properties(ref)
    if library:
        props["library"] = library
    if extra:
        props.update(extra)
    return Finding(
        kind="algorithm", identity=ref.identity(), name=display_name(ref), evidence=evidence,
        detector=detector, rule=rule, confidence=confidence, function=function, properties=props,
    )


def algorithm_relation(relation: str, ref: AlgorithmRef) -> Relation:
    return Relation(relation, "algorithm", ref.identity(), display_name(ref), algorithm_properties(ref))


def protocol_finding(
    protocol: str,
    evidence: Evidence,
    *,
    detector: str,
    rule: str,
    confidence: float,
    hybrid: bool = False,
    extra: dict[str, Any] | None = None,
    related: list[Relation] | None = None,
) -> Finding:
    assessment = protocol_assessment(protocol, hybrid_key_exchange=hybrid)
    props: dict[str, Any] = {"assessment": assessment.as_dict()}
    if extra:
        props.update(extra)
    family, _, version = protocol.partition(" ")
    return Finding(
        kind="protocol", identity={"protocol": family, "version": version or None, "hybrid": hybrid or None},
        name=protocol + (" (hybrid PQC)" if hybrid else ""), evidence=evidence, detector=detector, rule=rule,
        confidence=confidence, function="secure-channel", properties=props, related=related or [],
    )
