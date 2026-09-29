"""CycloneDX 1.6 Cryptography Bill of Materials (CBOM), in JSON and XML.

Every artefact becomes a component: algorithms, certificates, keys and
protocols as ``cryptographic-asset`` components with their CycloneDX crypto
properties, libraries as ``library`` components with a package URL, hardware
as ``device``. Each system is an ``application`` that depends on the
artefacts found in it; certificates reference their key and signature
algorithm, keys their algorithm, protocols what they negotiate. Evidence
travels as ``evidence.occurrences``; FALCON's assessment (quantum status,
risk, Mosca, harvest-now-decrypt-later, compliance, recommendation) travels
as ``falcon:*`` properties, so standard CBOM consumers read the inventory and
FALCON can read its own analysis back.

``bom-ref`` values are stable across exports (system and fingerprint), which
is what makes drift between two CBOMs computable.
"""
from __future__ import annotations

import hashlib
import json
import re
import uuid
from datetime import datetime, timezone
from typing import Any
from xml.etree import ElementTree as ET

from ..domains.horizon.model import format_decimal_year
from .inventory import TOOL_NAME, TOOL_VENDOR, TOOL_VERSION, Item, Report

SPEC_VERSION = "1.6"
XML_NS = "http://cyclonedx.org/schema/bom/1.6"

_PRIMITIVE = {
    "signature": "signature", "key-agreement": "key-agree", "kem": "kem", "pke": "pke", "block-cipher": "block-cipher",
    "stream-cipher": "stream-cipher", "ae": "ae", "hash": "hash", "xof": "xof", "mac": "mac", "kdf": "kdf", "drbg": "drbg",
    "prng": "other",
}
_MODES = {"cbc", "ecb", "ccm", "gcm", "cfb", "ofb", "ctr"}
_PADDING = {"pkcs5": "pkcs5", "pkcs7": "pkcs7", "pkcs1v15": "pkcs1v15", "pkcs1": "pkcs1v15", "pkcs#1 v1.5": "pkcs1v15",
            "oaep": "oaep", "raw": "raw", "none": "raw"}
_FUNCTIONS = {
    "keygen": ["keygen"], "encrypt": ["encrypt", "decrypt"], "digest": ["digest"], "mac": ["tag"], "derive": ["keyderive"],
    "sign": ["sign", "verify"], "kem": ["encapsulate", "decapsulate"], "random": ["generate"], "key-agree": ["keyderive"],
}
_PROTOCOLS = {"TLS": "tls", "DTLS": "tls", "SSL": "tls", "SSH": "ssh", "IPsec": "ipsec", "IKE": "ike", "IKEv2": "ike",
              "SSTP": "sstp", "WPA": "wpa"}
_TECHNIQUE = {"python-ast": "ast-fingerprint", "java-bytecode": "binary-analysis", "binaries": "binary-analysis",
              "dependencies": "manifest-analysis", "infrastructure-as-code": "manifest-analysis", "protocol-config": "source-code-analysis",
              "crypto-material": "hash-comparison", "tls-endpoint": "dynamic-analysis"}
_OID = {
    ("RSA", None): "1.2.840.113549.1.1.1", ("ECDSA", None): "1.2.840.10045.2.1", ("ECDH", None): "1.2.840.10045.2.1",
    ("DSA", None): "1.2.840.10040.4.1", ("DH", None): "1.2.840.113549.1.3.1", ("EdDSA", "Ed25519"): "1.3.101.112",
    ("EdDSA", "Ed448"): "1.3.101.113", ("X25519", None): "1.3.101.110", ("X448", None): "1.3.101.111",
    ("AES", "128/GCM"): "2.16.840.1.101.3.4.1.6", ("AES", "192/GCM"): "2.16.840.1.101.3.4.1.26", ("AES", "256/GCM"): "2.16.840.1.101.3.4.1.46",
    ("AES", "128/CBC"): "2.16.840.1.101.3.4.1.2", ("AES", "192/CBC"): "2.16.840.1.101.3.4.1.22", ("AES", "256/CBC"): "2.16.840.1.101.3.4.1.42",
    ("AES", "128/CCM"): "2.16.840.1.101.3.4.1.7", ("AES", "256/CCM"): "2.16.840.1.101.3.4.1.47",
    ("SHA-1", None): "1.3.14.3.2.26", ("SHA-256", None): "2.16.840.1.101.3.4.2.1", ("SHA-384", None): "2.16.840.1.101.3.4.2.2",
    ("SHA-512", None): "2.16.840.1.101.3.4.2.3", ("SHA3-256", None): "2.16.840.1.101.3.4.2.8", ("MD5", None): "1.2.840.113549.2.5",
    ("ML-KEM", "512"): "2.16.840.1.101.3.4.4.1", ("ML-KEM", "768"): "2.16.840.1.101.3.4.4.2", ("ML-KEM", "1024"): "2.16.840.1.101.3.4.4.3",
    ("ML-DSA", "44"): "2.16.840.1.101.3.4.3.17", ("ML-DSA", "65"): "2.16.840.1.101.3.4.3.18", ("ML-DSA", "87"): "2.16.840.1.101.3.4.3.19",
    ("3DES", None): "1.2.840.113549.3.7", ("ChaCha20-Poly1305", None): "1.2.840.113549.1.9.16.3.18",
}
_HMAC_OID = {"SHA-1": "1.2.840.113549.2.7", "SHA-256": "1.2.840.113549.2.9", "SHA-384": "1.2.840.113549.2.10", "SHA-512": "1.2.840.113549.2.11"}
_PURL_TYPE = {"pypi": "pypi", "npm": "npm", "maven": "maven", "go": "golang", "cargo": "cargo", "nuget": "nuget", "gem": "gem",
              "composer": "composer", "os": "generic", "binary": "generic", "go-toolchain": "golang"}


def _prop(name: str, value: Any) -> dict[str, str] | None:
    if value is None or value == "":
        return None
    if isinstance(value, bool):
        value = "true" if value else "false"
    return {"name": name, "value": str(value)}


def _iso(value: Any) -> str | None:
    if isinstance(value, datetime):
        return value.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    if isinstance(value, str) and value:
        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        except ValueError:
            return None
    return None


def _oid(identity: dict[str, Any]) -> str | None:
    algorithm, parameter = identity.get("algorithm"), identity.get("parameter")
    if algorithm == "HMAC":
        return _HMAC_OID.get(identity.get("hash") or "")
    if algorithm == "AES" and parameter and identity.get("mode"):
        return _OID.get(("AES", f"{parameter}/{identity['mode'].upper()}"))
    return _OID.get((algorithm, parameter)) or _OID.get((algorithm, None))


def _quantum_level(item: Item) -> int | None:
    a = item.facts
    assessment = a.assessment
    if assessment.get("nist_category"):
        return int(assessment["nist_category"])
    if a.quantum == "vulnerable":
        return 0
    bits = a.classical_bits
    if a.primitive in ("block-cipher", "ae", "stream-cipher") and bits:
        return 5 if bits >= 256 else 3 if bits >= 192 else 1 if bits >= 128 else 0
    if a.primitive in ("hash", "xof"):
        size = re.search(r"(\d{3})", str(a.identity.get("algorithm") or ""))
        if size:
            return {"256": 2, "384": 4, "512": 5}.get(size.group(1))
    return None


def _falcon_properties(item: Item, report: Report) -> list[dict[str, str]]:
    a, r = item.facts, item.risk
    now = report.model.now
    props = [
        _prop("falcon:artefact-kind", a.kind),
        _prop("falcon:system", item.system.code),
        _prop("falcon:quantum-status", a.quantum),
        _prop("falcon:classical-status", a.classical),
        _prop("falcon:confidence", round(item.confidence, 2) if item.confidence else None),
        _prop("falcon:occurrences", item.occurrence_total),
        _prop("falcon:fingerprint", item.fingerprint),
    ]
    if a.kind not in ("library", "hardware") or r.score:
        props += [
            _prop("falcon:risk:score", r.score), _prop("falcon:risk:band", r.band),
            _prop("falcon:roles", ",".join(r.roles)),
            _prop("falcon:mosca:x", r.mosca["x"]), _prop("falcon:mosca:y", r.mosca["y"]), _prop("falcon:mosca:z", r.mosca["z"]),
            _prop("falcon:mosca:status", r.mosca["status"]), _prop("falcon:crqc-probability", r.mosca["probability"]),
            _prop("falcon:hndl", r.hndl["exposed"] if r.hndl["applies"] else None),
        ]
        if r.timeline.get("broken"):
            props.append(_prop("falcon:broken-from", format_decimal_year(r.timeline["broken"])))
        for p in r.policies:
            props.append(_prop(f"falcon:policy:{p.framework}", p.status_at(now)))
    rec = item.recommendation
    if rec and rec.get("action") not in (None, "keep"):
        props.append(_prop("falcon:recommendation", rec.get("title")))
        if rec.get("primary"):
            props.append(_prop("falcon:recommendation:primary", rec["primary"]["name"]))
        if rec.get("hybrid"):
            props.append(_prop("falcon:recommendation:hybrid", rec["hybrid"]["name"]))
    return [p for p in props if p]


def _evidence(item: Item) -> dict[str, Any] | None:
    if not item.occurrences:
        return None
    occurrences = []
    for o in item.occurrences:
        occ: dict[str, Any] = {"location": o.path}
        if o.line:
            occ["line"] = int(o.line)
        if o.column:
            occ["offset"] = int(o.column)
        occ["additionalContext"] = f"{o.detector} {o.rule}" + (f" ({o.function})" if o.function else "")
        occurrences.append(occ)
    techniques = sorted({_TECHNIQUE.get(o.detector, "source-code-analysis" if o.detector.startswith("rules:") else "other") for o in item.occurrences})
    confidence = round(min(max(item.confidence or 0.5, 0.0), 1.0), 2)
    return {
        "identity": [{"field": "name", "confidence": confidence,
                      "methods": [{"technique": t, "confidence": confidence} for t in techniques]}],
        "occurrences": occurrences,
    }


def _algorithm_component(item: Item) -> dict[str, Any]:
    a = item.facts
    identity = a.identity
    algorithm: dict[str, Any] = {"primitive": _PRIMITIVE.get(a.primitive or "", "unknown")}
    if identity.get("parameter"):
        parameter = str(identity["parameter"])
        if parameter.startswith(("P-", "secp", "brainpool", "Ed", "Curve")):
            algorithm["curve"] = parameter
        algorithm["parameterSetIdentifier"] = parameter
    mode = str(identity.get("mode") or "").lower()
    if mode:
        algorithm["mode"] = mode if mode in _MODES else "other"
    padding = str(identity.get("padding") or "").lower()
    if padding:
        algorithm["padding"] = _PADDING.get(padding, "other")
    algorithm["executionEnvironment"] = "hardware" if "hardware" in a.detectors else "software-plain-ram"
    algorithm["implementationPlatform"] = "unknown"
    algorithm["certificationLevel"] = ["unknown"]
    functions = sorted({f for fn in a.functions for f in _FUNCTIONS.get(fn, [])})
    if functions:
        algorithm["cryptoFunctions"] = functions
    if a.classical_bits is not None:
        algorithm["classicalSecurityLevel"] = a.classical_bits
    level = _quantum_level(item)
    if level is not None:
        algorithm["nistQuantumSecurityLevel"] = level
    crypto: dict[str, Any] = {"assetType": "algorithm", "algorithmProperties": algorithm}
    oid = _oid(identity)
    if oid:
        crypto["oid"] = oid
    return {"type": "cryptographic-asset", "name": a.name, "cryptoProperties": crypto}


def _key_size(text: str) -> int | None:
    m = re.search(r"(\d{3,5})", text)
    return int(m.group(1)) if m else ({"P-256": 256, "P-384": 384, "P-521": 521}.get(next(iter(re.findall(r"P-\d{3}", text)), "")))


def _key_component(item: Item, refs: dict[str, list[tuple[str, str]]], report_refs: dict[str, str]) -> dict[str, Any]:
    a = item.facts
    p = a.properties
    material: dict[str, Any] = {"type": "private-key" if p.get("private") else "public-key", "state": "active"}
    if p.get("kid"):
        material["id"] = str(p["kid"])
    size = _key_size(str(p.get("key_algorithm") or ""))
    if size:
        material["size"] = size
    if p.get("format"):
        material["format"] = str(p["format"])
    algorithm = next((report_refs[t] for rel, t in refs.get(item.id, []) if rel == "uses-algorithm" and t in report_refs), None)
    if algorithm:
        material["algorithmRef"] = algorithm
    if p.get("encrypted"):
        material["securedBy"] = {"mechanism": "Password-based encryption"}
    return {"type": "cryptographic-asset", "name": a.name,
            "cryptoProperties": {"assetType": "related-crypto-material", "relatedCryptoMaterialProperties": material}}


def _certificate_component(item: Item, refs: dict[str, list[tuple[str, str]]], report_refs: dict[str, str]) -> dict[str, Any]:
    a = item.facts
    p = a.properties
    cert: dict[str, Any] = {}
    for field, key in (("subjectName", "subject"), ("issuerName", "issuer")):
        if p.get(key):
            cert[field] = str(p[key])
    for field, key in (("notValidBefore", "not_before"), ("notValidAfter", "not_after")):
        stamp = _iso(p.get(key))
        if stamp:
            cert[field] = stamp
    for rel, target in refs.get(item.id, []):
        if target not in report_refs:
            continue
        if rel == "signed-with" and "signatureAlgorithmRef" not in cert:
            cert["signatureAlgorithmRef"] = report_refs[target]
        if rel == "certifies-key" and "subjectPublicKeyRef" not in cert:
            cert["subjectPublicKeyRef"] = report_refs[target]
    cert["certificateFormat"] = "X.509"
    return {"type": "cryptographic-asset", "name": a.name, "version": str(p["serial"]) if p.get("serial") else None,
            "cryptoProperties": {"assetType": "certificate", "certificateProperties": cert}}


def _protocol_component(item: Item, refs: dict[str, list[tuple[str, str]]], report_refs: dict[str, str]) -> dict[str, Any]:
    a = item.facts
    protocol: dict[str, Any] = {"type": _PROTOCOLS.get(str(a.identity.get("protocol") or ""), "other")}
    if a.identity.get("version"):
        protocol["version"] = str(a.identity["version"])
    negotiated = sorted({report_refs[t] for rel, t in refs.get(item.id, []) if rel == "negotiates" and t in report_refs})
    if negotiated:
        protocol["cipherSuites"] = [{"name": f"{a.name} negotiated", "algorithms": negotiated}]
    return {"type": "cryptographic-asset", "name": a.name, "cryptoProperties": {"assetType": "protocol", "protocolProperties": protocol}}


def _cloud_component(item: Item, refs: dict[str, list[tuple[str, str]]], report_refs: dict[str, str]) -> dict[str, Any]:
    a = item.facts
    p = a.properties
    spec = str(p.get("key_spec") or "").upper()
    usage = str(p.get("key_usage") or "").upper()
    kind = "secret-key" if spec.startswith(("SYMMETRIC", "AES", "HMAC")) else "private-key" if spec else "key"
    material: dict[str, Any] = {"type": kind, "id": str(a.identity.get("resource") or a.name), "state": "active",
                                "securedBy": {"mechanism": f"{str(p.get('provider') or '').upper()} {str(p.get('service') or '').upper()}".strip()}}
    size = _key_size(spec.replace("_", "-"))
    if size:
        material["size"] = size
    if spec:
        material["format"] = spec
    algorithm = next((report_refs[t] for rel, t in refs.get(item.id, []) if rel == "protects-with" and t in report_refs), None)
    if algorithm:
        material["algorithmRef"] = algorithm
        material["securedBy"]["algorithmRef"] = algorithm
    component = {"type": "cryptographic-asset", "name": a.name,
                 "cryptoProperties": {"assetType": "related-crypto-material", "relatedCryptoMaterialProperties": material}}
    component["_extra"] = [_prop("falcon:cloud:usage", usage or None), _prop("falcon:cloud:rotation", p.get("rotation"))]
    return component


def _purl(item: Item) -> str | None:
    p, ident = item.facts.properties, item.facts.identity
    ptype = _PURL_TYPE.get(str(p.get("ecosystem") or ""))
    version = ident.get("version")
    if not ptype:
        return None
    name = str(p.get("package") or ident.get("library") or item.facts.name)
    if ptype == "maven" and ":" in name:
        group, artifact = name.split(":", 1)
        base = f"pkg:maven/{group}/{artifact}"
    elif ptype == "npm" and name.startswith("@"):
        base = "pkg:npm/%40" + name[1:]
    else:
        base = f"pkg:{ptype}/{name}"
    return f"{base}@{version}" if version else base


def _library_component(item: Item) -> dict[str, Any]:
    a = item.facts
    p = a.properties
    component: dict[str, Any] = {"type": "library", "name": str(p.get("library") or a.name),
                                 "version": str(a.identity["version"]) if a.identity.get("version") else None}
    purl = _purl(item)
    if purl:
        component["purl"] = purl
    pqc = p.get("pqc") or {}
    eol = p.get("eol") or {}
    component["_extra"] = [
        _prop("falcon:library:category", p.get("category")),
        _prop("falcon:library:pqc", pqc.get("status")),
        _prop("falcon:library:pqc-since", pqc.get("since")),
        _prop("falcon:library:pqc-capable", pqc.get("capable")),
        _prop("falcon:library:end-of-life", eol.get("date")),
        _prop("falcon:library:end-of-life-reached", eol.get("reached")),
        _prop("falcon:library:statically-linked", p.get("statically_linked")),
    ]
    return component


def _hardware_component(item: Item) -> dict[str, Any]:
    a = item.facts
    p = a.properties
    component: dict[str, Any] = {"type": "device", "name": a.name}
    if p.get("vendor"):
        component["supplier"] = {"name": str(p["vendor"])}
    component["_extra"] = [_prop("falcon:hardware:type", p.get("type")), _prop("falcon:hardware:interface", p.get("interface"))]
    return component


def _canonical_json(data: Any) -> bytes:
    return json.dumps(data, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def build(report: Report, *, serial: str | None = None) -> dict[str, Any]:
    """The CBOM as a CycloneDX 1.6 document (a plain dict, ready for ``json.dumps``)."""
    by_id = report.by_id()
    report_refs = {i.id: i.ref for i in report.items}
    refs: dict[str, list[tuple[str, str]]] = {}
    for f, t, rel in report.links:
        refs.setdefault(f, []).append((rel, t))

    components: list[dict[str, Any]] = []
    systems_used: dict[str, list[str]] = {}
    for item in sorted(report.items, key=lambda i: (i.system.code, i.facts.kind, i.facts.name, i.fingerprint)):
        kind = item.facts.kind
        if kind == "algorithm":
            component = _algorithm_component(item)
        elif kind == "key":
            component = _key_component(item, refs, report_refs)
        elif kind == "certificate":
            component = _certificate_component(item, refs, report_refs)
        elif kind == "protocol":
            component = _protocol_component(item, refs, report_refs)
        elif kind == "cloud_service":
            component = _cloud_component(item, refs, report_refs)
        elif kind == "library":
            component = _library_component(item)
        else:
            component = _hardware_component(item)
        extra = [p for p in component.pop("_extra", []) if p]
        ordered: dict[str, Any] = {"type": component.pop("type"), "bom-ref": item.ref}
        ordered.update({k: v for k, v in component.items() if v is not None})
        evidence = _evidence(item)
        if evidence:
            ordered["evidence"] = evidence
        ordered["properties"] = _falcon_properties(item, report) + extra
        components.append(ordered)
        systems_used.setdefault(item.system.id, []).append(item.ref)

    system_components = []
    for sid, members in sorted(systems_used.items(), key=lambda kv: report.systems[kv[0]].code):
        s = report.systems[sid]
        system_components.append({
            "type": "application", "bom-ref": f"system/{s.code}", "name": s.name,
            "properties": [p for p in (
                _prop("falcon:system:code", s.code), _prop("falcon:system:kind", s.kind),
                _prop("falcon:system:criticality", s.criticality), _prop("falcon:system:exposure", s.exposure),
                _prop("falcon:system:classification", s.classification),
                _prop("falcon:system:shelf-life-years", s.shelf_life_years), _prop("falcon:system:migration-years", s.migration_years),
            ) if p],
        })

    dependencies: list[dict[str, Any]] = []
    for sid, members in sorted(systems_used.items(), key=lambda kv: report.systems[kv[0]].code):
        dependencies.append({"ref": f"system/{report.systems[sid].code}", "dependsOn": sorted(set(members))})
    for f in sorted(refs, key=lambda k: report_refs.get(k, "")):
        if f not in by_id:
            continue
        targets = sorted({report_refs[t] for _, t in refs[f] if t in report_refs})
        if targets:
            dependencies.append({"ref": report_refs[f], "dependsOn": targets})

    model = report.model
    root = f"scope/{hashlib.sha1(report.scope.encode()).hexdigest()[:12]}"
    doc: dict[str, Any] = {
        "$schema": "http://cyclonedx.org/schema/bom-1.6.schema.json",
        "bomFormat": "CycloneDX",
        "specVersion": SPEC_VERSION,
        "serialNumber": serial or f"urn:uuid:{uuid.uuid4()}",
        "version": 1,
        "metadata": {
            "timestamp": _iso(report.generated_at),
            "lifecycles": [{"phase": "operations" if report.origin.get("mode") == "platform" else "build"}],
            "tools": {"components": [{"type": "application", "author": TOOL_VENDOR, "name": TOOL_NAME, "version": TOOL_VERSION}]},
            "component": {"type": "application", "bom-ref": root, "name": report.scope},
            "manufacturer": {"name": report.organisation},
            "properties": [p for p in (
                _prop("falcon:threat-model:scenario", model.scenario),
                _prop("falcon:threat-model:planning-year", format_decimal_year(model.planning_year)),
                _prop("falcon:threat-model:tolerance", model.tolerance),
                _prop("falcon:artefacts", len(report.items)),
                _prop("falcon:origin", report.origin.get("mode")),
                _prop("falcon:source", report.origin.get("path")),
            ) if p],
        },
        "components": system_components + components,
        "dependencies": [{"ref": root, "dependsOn": [c["bom-ref"] for c in system_components]}] + dependencies,
    }
    return doc


def to_json(doc: dict[str, Any], *, indent: int | None = 2) -> str:
    return json.dumps(doc, indent=indent, ensure_ascii=False)


def digest(doc: dict[str, Any]) -> str:
    """SHA-256 of the canonical form (sorted keys, no whitespace); independent of the serial number and timestamp."""
    stable = {k: v for k, v in doc.items() if k not in ("serialNumber",)}
    stable["metadata"] = {k: v for k, v in doc.get("metadata", {}).items() if k != "timestamp"}
    return hashlib.sha256(_canonical_json(stable)).hexdigest()


# ------------------------------------------------------------------------ XML

_XML_INVALID = re.compile(r"[^\t\n\r\u0020-\ud7ff\ue000-\ufffd\U00010000-\U0010ffff]")


def _xml_text(value: Any) -> str:
    """XML 1.0 cannot carry control characters (binary banners, NUL-padded strings): drop them."""
    return _XML_INVALID.sub("", str(value))


def _el(parent: ET.Element, tag: str, text: Any = None, **attrs: Any) -> ET.Element:
    node = ET.SubElement(parent, tag, {k.replace("_", "-"): _xml_text(v) for k, v in attrs.items() if v is not None})
    if text is not None:
        node.text = _xml_text(text)
    return node


def _xml_properties(parent: ET.Element, props: list[dict[str, str]]) -> None:
    if props:
        container = _el(parent, "properties")
        for p in props:
            _el(container, "property", p["value"], name=p["name"])


def _xml_crypto(parent: ET.Element, crypto: dict[str, Any]) -> None:
    node = _el(parent, "cryptoProperties")
    _el(node, "assetType", crypto["assetType"])
    if "algorithmProperties" in crypto:
        a = crypto["algorithmProperties"]
        ap = _el(node, "algorithmProperties")
        for key in ("primitive", "parameterSetIdentifier", "curve", "executionEnvironment", "implementationPlatform"):
            if key in a:
                _el(ap, key, a[key])
        for level in a.get("certificationLevel", []):
            _el(ap, "certificationLevel", level)
        for key in ("mode", "padding"):
            if key in a:
                _el(ap, key, a[key])
        if a.get("cryptoFunctions"):
            functions = _el(ap, "cryptoFunctions")
            for f in a["cryptoFunctions"]:
                _el(functions, "cryptoFunction", f)
        for key in ("classicalSecurityLevel", "nistQuantumSecurityLevel"):
            if key in a:
                _el(ap, key, a[key])
    if "certificateProperties" in crypto:
        c = crypto["certificateProperties"]
        cp = _el(node, "certificateProperties")
        for key in ("subjectName", "issuerName", "notValidBefore", "notValidAfter", "signatureAlgorithmRef", "subjectPublicKeyRef",
                    "certificateFormat", "certificateExtension"):
            if key in c:
                _el(cp, key, c[key])
    if "relatedCryptoMaterialProperties" in crypto:
        m = crypto["relatedCryptoMaterialProperties"]
        mp = _el(node, "relatedCryptoMaterialProperties")
        for key in ("type", "id", "state", "algorithmRef", "creationDate", "activationDate", "updateDate", "expirationDate",
                    "value", "size", "format"):
            if key in m:
                _el(mp, key, m[key])
        if "securedBy" in m:
            sb = _el(mp, "securedBy")
            for key in ("mechanism", "algorithmRef"):
                if key in m["securedBy"]:
                    _el(sb, key, m["securedBy"][key])
    if "protocolProperties" in crypto:
        p = crypto["protocolProperties"]
        pp = _el(node, "protocolProperties")
        for key in ("type", "version"):
            if key in p:
                _el(pp, key, p[key])
        if p.get("cipherSuites"):
            suites = _el(pp, "cipherSuites")
            for suite in p["cipherSuites"]:
                s = _el(suites, "cipherSuite")
                _el(s, "name", suite["name"])
                algorithms = _el(s, "algorithms")
                for ref in suite["algorithms"]:
                    _el(algorithms, "algorithm", ref)
    if "oid" in crypto:
        _el(node, "oid", crypto["oid"])


def _xml_component(parent: ET.Element, c: dict[str, Any]) -> None:
    node = _el(parent, "component", type=c["type"], bom_ref=c.get("bom-ref"))
    if "supplier" in c:
        supplier = _el(node, "supplier")
        _el(supplier, "name", c["supplier"]["name"])
    if "author" in c:
        _el(node, "author", c["author"])
    _el(node, "name", c["name"])
    for key in ("version", "purl"):
        if c.get(key):
            _el(node, key, c[key])
    # Element order follows the 1.6 XSD: properties, evidence, then cryptoProperties.
    _xml_properties(node, c.get("properties", []))
    if "evidence" in c:
        ev = _el(node, "evidence")
        for ident in c["evidence"].get("identity", []):
            ie = _el(ev, "identity")
            _el(ie, "field", ident["field"])
            _el(ie, "confidence", ident["confidence"])
            methods = _el(ie, "methods")
            for m in ident["methods"]:
                me = _el(methods, "method")
                _el(me, "technique", m["technique"])
                _el(me, "confidence", m["confidence"])
        occurrences = _el(ev, "occurrences")
        for o in c["evidence"]["occurrences"]:
            oe = _el(occurrences, "occurrence")
            _el(oe, "location", o["location"])
            for key in ("line", "offset", "symbol", "additionalContext"):
                if key in o:
                    _el(oe, key, o[key])
    if "cryptoProperties" in c:
        _xml_crypto(node, c["cryptoProperties"])


def to_xml(doc: dict[str, Any]) -> str:
    ET.register_namespace("", XML_NS)
    bom = ET.Element("bom", {"xmlns": XML_NS, "serialNumber": doc["serialNumber"], "version": str(doc["version"])})
    meta = doc["metadata"]
    m = _el(bom, "metadata")
    _el(m, "timestamp", meta["timestamp"])
    lifecycles = _el(m, "lifecycles")
    for lc in meta["lifecycles"]:
        _el(_el(lifecycles, "lifecycle"), "phase", lc["phase"])
    tools = _el(_el(m, "tools"), "components")
    for tool in meta["tools"]["components"]:
        _xml_component(tools, tool)
    _xml_component(m, meta["component"])
    manufacturer = _el(m, "manufacturer")
    _el(manufacturer, "name", meta["manufacturer"]["name"])
    _xml_properties(m, meta.get("properties", []))
    components = _el(bom, "components")
    for c in doc["components"]:
        _xml_component(components, c)
    deps = _el(bom, "dependencies")
    for d in doc["dependencies"]:
        dep = _el(deps, "dependency", ref=d["ref"])
        for target in d.get("dependsOn", []):
            _el(dep, "dependency", ref=target)
    ET.indent(bom)
    return '<?xml version="1.0" encoding="UTF-8"?>\n' + ET.tostring(bom, encoding="unicode")
