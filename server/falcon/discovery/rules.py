"""Rule packs: declarative detection for source code and text.

A rule pack (``knowledge/rules/<pack>.json``) lists regular expressions with
named captures. A capture is interpreted through the name grammar named by the
rule, so a rule says *where* cryptography is written and the grammar says
*what* it means::

    {"id": "java.cipher", "pattern": "Cipher\\\\.getInstance\\\\(\\\\s*\\"(?P<name>[^\\"]+)\\"",
     "grammar": "jca-cipher", "function": "encrypt", "confidence": 0.95, "library": "JCA"}

Parameters written separately from the call site (``kpg.initialize(3072)``)
are found by an optional ``lookahead`` pattern over the next few lines.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any, Iterator

from . import names
from .catalogue import AlgorithmRef, canonical_curve
from .model import Evidence, Finding, algorithm_finding, protocol_finding, snippet

_RULES_DIR = Path(__file__).resolve().parents[1] / "knowledge" / "rules"

# Small vocabularies for APIs that name algorithms with constants.
_CNG = {
    "RSA": ("RSA", None), "DSA": ("DSA", None), "DH": ("DH", None), "ECDSA_P256": ("ECDSA", "P-256"),
    "ECDSA_P384": ("ECDSA", "P-384"), "ECDSA_P521": ("ECDSA", "P-521"), "ECDH_P256": ("ECDH", "P-256"),
    "ECDH_P384": ("ECDH", "P-384"), "ECDH_P521": ("ECDH", "P-521"), "ECDSA": ("ECDSA", None), "ECDH": ("ECDH", None),
    "AES": ("AES", None), "3DES": ("3DES", None), "3DES_112": ("3DES", None), "DES": ("DES", None), "RC4": ("RC4", None),
    "RC2": ("RC2", None), "MD5": ("MD5", None), "MD4": ("MD4", None), "SHA1": ("SHA-1", None), "SHA256": ("SHA-256", None),
    "SHA384": ("SHA-384", None), "SHA512": ("SHA-512", None), "MLKEM": ("ML-KEM", None), "MLDSA": ("ML-DSA", None),
    "PBKDF2": ("PBKDF2", None), "RNG": ("CSPRNG", None),
}
_CAPI = {
    "MD5": ("MD5", None), "MD4": ("MD4", None), "SHA1": ("SHA-1", None), "SHA": ("SHA-1", None), "SHA_256": ("SHA-256", None),
    "SHA_384": ("SHA-384", None), "SHA_512": ("SHA-512", None), "3DES": ("3DES", None), "3DES_112": ("3DES", None),
    "DES": ("DES", None), "RC4": ("RC4", None), "RC2": ("RC2", None), "AES_128": ("AES", "128"), "AES_192": ("AES", "192"),
    "AES_256": ("AES", "256"), "AES": ("AES", None), "RSA_SIGN": ("RSA", None), "RSA_KEYX": ("RSA", None),
    "DH_EPHEM": ("DH", None), "DH_SF": ("DH", None), "ECDSA": ("ECDSA", None), "ECDH": ("ECDH", None), "DSS_SIGN": ("DSA", None),
}
_WEBCRYPTO = {
    "RSA-OAEP": AlgorithmRef("RSA", padding="OAEP"), "RSASSA-PKCS1-V1_5": AlgorithmRef("RSA", padding="PKCS1v15"),
    "RSA-PSS": AlgorithmRef("RSA", padding="PSS"), "ECDSA": AlgorithmRef("ECDSA"), "ECDH": AlgorithmRef("ECDH"),
    "AES-GCM": AlgorithmRef("AES", mode="GCM"), "AES-CBC": AlgorithmRef("AES", mode="CBC"), "AES-CTR": AlgorithmRef("AES", mode="CTR"),
    "AES-KW": AlgorithmRef("AES", mode="KW"), "HMAC": AlgorithmRef("HMAC"), "PBKDF2": AlgorithmRef("PBKDF2"),
    "HKDF": AlgorithmRef("HKDF"), "ED25519": AlgorithmRef("EdDSA", "Ed25519"), "X25519": AlgorithmRef("X25519"),
    "ED448": AlgorithmRef("EdDSA", "Ed448"), "X448": AlgorithmRef("X448"),
}
_DOTNET_JWT = {
    "HMACSHA256": "HS256", "HMACSHA384": "HS384", "HMACSHA512": "HS512", "RSASHA256": "RS256", "RSASHA384": "RS384",
    "RSASHA512": "RS512", "ECDSASHA256": "ES256", "ECDSASHA384": "ES384", "ECDSASHA512": "ES512",
    "RSASSAPSSSHA256": "PS256", "RSASSAPSSSHA384": "PS384", "RSASSAPSSSHA512": "PS512",
}


@dataclass
class Rule:
    id: str
    pattern: re.Pattern[str]
    grammar: str
    confidence: float
    function: str | None = None
    library: str | None = None
    algorithm: str | None = None
    parameter: str | None = None
    mode: str | None = None
    padding: str | None = None
    hash: str | None = None
    lookahead: re.Pattern[str] | None = None
    lookahead_lines: int = 6
    note: str | None = None
    kind: str | None = None  # hardware / cloud_service rules
    attrs: dict[str, Any] | None = None
    # Searched once over the whole file (with line anchors): the rule's own pattern, whose
    # every line match is also a match here, or a cheaper literal "gate" the pack declares.
    # A rule whose gate finds nothing skips the per-line pass entirely.
    gate: re.Pattern[str] | None = None


@dataclass
class Pack:
    name: str
    # Lower-case literals; a file containing none of them cannot match any rule in the pack.
    prefilter: tuple[str, ...]
    rules: list[Rule]

    def may_match(self, text: str) -> bool:
        if not self.prefilter:
            return True
        lowered = text.lower()
        return any(token in lowered for token in self.prefilter)


@lru_cache
def load_pack(name: str) -> Pack:
    path = _RULES_DIR / f"{name}.json"
    with path.open(encoding="utf-8") as fh:
        data = json.load(fh)
    rules = []
    for raw in data["rules"]:
        flags = re.IGNORECASE if raw.get("ignore_case") else 0
        rules.append(Rule(
            id=raw["id"],
            pattern=re.compile(raw["pattern"], flags),
            gate=re.compile(raw.get("gate") or raw["pattern"], flags | re.MULTILINE),
            grammar=raw.get("grammar", "fixed"),
            confidence=raw.get("confidence", 0.85),
            function=raw.get("function"),
            library=raw.get("library"),
            algorithm=raw.get("algorithm"),
            parameter=raw.get("parameter"),
            mode=raw.get("mode"),
            padding=raw.get("padding"),
            hash=raw.get("hash"),
            lookahead=re.compile(raw["lookahead"], flags) if raw.get("lookahead") else None,
            lookahead_lines=raw.get("lookahead_lines", 6),
            note=raw.get("note"),
            kind=raw.get("kind"),
            attrs=raw.get("attrs"),
        ))
    # Prefilter entries are literals written regex-escaped (``rsa\.``): unescape and fold case once.
    prefilter = tuple(sorted({re.sub(r"\\(.)", r"\1", token).lower() for token in data.get("prefilter") or []}))
    return Pack(name, prefilter, rules)


def available_packs() -> list[str]:
    return sorted(p.stem for p in _RULES_DIR.glob("*.json"))


# ------------------------------------------------------------ interpretation

def _base(key: str) -> str:
    # Patterns cannot repeat a group name, so alternatives use "<name>_alt".
    return key[:-4] if key.endswith("_alt") else key


def _captures(match: re.Match[str], lines: list[str], index: int, rule: Rule) -> dict[str, str]:
    caps: dict[str, str] = {}
    for k, v in match.groupdict().items():
        if v:
            caps.setdefault(_base(k), v)
    if rule.lookahead is not None:
        window = "\n".join(lines[index: index + rule.lookahead_lines + 1])
        for m in rule.lookahead.finditer(window):
            for k, v in m.groupdict().items():
                if v:
                    caps.setdefault(_base(k), v)
    return caps


def _apply_parameters(ref: AlgorithmRef, caps: dict[str, str]) -> AlgorithmRef:
    parameter, mode, digest = ref.parameter, ref.mode, ref.hash
    if not parameter:
        if caps.get("bits"):
            parameter = caps["bits"]
        elif caps.get("bytes") and caps["bytes"].isdigit():
            parameter = str(int(caps["bytes"]) * 8)
        elif caps.get("curve"):
            curve = canonical_curve(caps["curve"])
            if curve in ("Curve25519", "Curve448") and ref.algorithm in ("ECDSA", "EdDSA"):
                return AlgorithmRef("EdDSA", "Ed25519" if curve == "Curve25519" else "Ed448")
            if curve in ("Curve25519", "Curve448") and ref.algorithm == "ECDH":
                return AlgorithmRef("X25519" if curve == "Curve25519" else "X448")
            parameter = curve
    if not mode and caps.get("mode"):
        mode = names._mode(caps["mode"].lower())
    if not digest and caps.get("hash"):
        digest = names.hash_name(caps["hash"])
    if not digest and caps.get("shabits"):
        digest = names.hash_name("sha" + caps["shabits"])
    return AlgorithmRef(ref.algorithm, parameter, mode, ref.padding, digest)


def interpret(rule: Rule, caps: dict[str, str]) -> tuple[list[AlgorithmRef], list[str], dict[str, Any]]:
    """Returns (algorithms, protocol versions, facts) for one rule match."""
    name = caps.get("name", "")
    grammar = rule.grammar
    refs: list[AlgorithmRef] = []
    versions: list[str] = []
    facts: dict[str, Any] = {}

    def add(ref: AlgorithmRef | None) -> None:
        if ref:
            refs.append(_apply_parameters(ref, caps))

    if grammar == "fixed":
        add(AlgorithmRef(rule.algorithm or "", rule.parameter, rule.mode, rule.padding, rule.hash))
    elif grammar == "cipher":
        add(names.cipher_name(name.replace("_", "-")))
    elif grammar == "jca-cipher":
        add(names.jca_transformation(name))
    elif grammar == "signature":
        add(names.signature_name(name))
    elif grammar == "signature-or-hash":
        ref = names.signature_name(name)
        add(ref or (AlgorithmRef(h) if (h := names.hash_name(name)) else None))
    elif grammar == "hash":
        digest = names.hash_name(name)
        add(AlgorithmRef(digest) if digest else None)
    elif grammar == "mac":
        ref = names.mac_name(name) or (AlgorithmRef("HMAC", hash=names.hash_name(name)) if names.hash_name(name) else None)
        add(ref)
    elif grammar == "key-type":
        add(names.key_type_name(name))
    elif grammar == "pbe":
        add(names.pbe_name(name) or names.cipher_name(name))
    elif grammar == "jose":
        add(names.jose_alg(name))
    elif grammar == "jose-list":
        for token in re.findall(r"[\"']([\w+-]+)[\"']", name):
            add(names.jose_alg(token))
    elif grammar == "curve":
        add(names.curve_ref(name, rule.algorithm or "ECDSA"))
    elif grammar == "pqc":
        add(names.pqc_name(name.replace("_", "-")))
    elif grammar == "evp":
        add(names.evp_function(name))
    elif grammar == "any":
        add(names.any_name(name))
    elif grammar == "random":
        add(AlgorithmRef(rule.algorithm or "CSPRNG"))
    elif grammar == "webcrypto":
        base = _WEBCRYPTO.get(name.upper())
        add(base)
    elif grammar == "cng":
        algorithm, parameter = _CNG.get(name.upper(), (None, None))
        add(AlgorithmRef(algorithm, parameter) if algorithm else None)
    elif grammar == "capi":
        algorithm, parameter = _CAPI.get(name.upper(), (None, None))
        add(AlgorithmRef(algorithm, parameter) if algorithm else None)
    elif grammar == "dotnet-jwt":
        alg = _DOTNET_JWT.get(re.sub(r"[^A-Z0-9]", "", name.upper()))
        add(names.jose_alg(alg) if alg else None)
    elif grammar == "tls-version":
        version = names.tls_version(name)
        if version:
            versions.append(version)
    elif grammar == "tls-version-list":
        for token in re.findall(r"(SSLv[23]|TLSv?1(?:[._]\d)?|DTLSv?1(?:[._]\d)?)", name, re.IGNORECASE):
            version = names.tls_version(token)
            if version and version not in versions:
                versions.append(version)
    elif grammar == "tls-suite":
        suite_refs, suite_facts = names.tls_suite(name.replace("TLS13_", "TLS_"))
        refs.extend(suite_refs)
        facts.update(suite_facts)
        facts["cipher_suite"] = name
    elif grammar == "tls-group":
        add(names.tls_group(name))
    elif grammar == "tls-group-list":
        for token in re.split(r"[:,\s]+", name):
            if token:
                add(names.tls_group(token))
    elif grammar == "openssl-cipher-list":
        from .detectors.tls_config import expand_cipher_string

        suites = expand_cipher_string(name)
        for suite in suites:
            suite_refs, _ = names.tls_suite(suite)
            refs.extend(suite_refs)
        facts["cipher_policy"] = name
    elif grammar == "ssh":
        add(names.ssh_algorithm(name))
    return refs, versions, facts


def scan_text(text: str, rel: str, pack: Pack, *, detector: str) -> Iterator[Finding]:
    """Apply a rule pack to one text file."""
    if not pack.may_match(text):
        return
    active = [rule for rule in pack.rules if rule.gate is None or rule.gate.search(text)]
    if not active:
        return
    lines = text.splitlines()
    for index, line in enumerate(lines):
        if len(line) > 4000:  # minified bundles: evidence would be unreadable
            line = line[:4000]
        for rule in active:
            for match in rule.pattern.finditer(line):
                caps = _captures(match, lines, index, rule)
                evidence = Evidence(rel, index + 1, match.start() + 1, snippet(lines, index))
                if rule.kind in ("hardware", "cloud_service"):
                    yield _special_finding(rule, caps, evidence, detector)
                    continue
                refs, versions, facts = interpret(rule, caps)
                for ref in refs:
                    if not ref.algorithm:
                        continue
                    extra = {"note": rule.note} if rule.note else {}
                    if facts.get("cipher_suite"):
                        extra["cipher_suite"] = facts["cipher_suite"]
                    yield algorithm_finding(
                        ref, evidence, detector=detector, rule=rule.id, confidence=rule.confidence,
                        function=rule.function, library=rule.library, extra=extra or None,
                    )
                if versions and rule.grammar == "tls-version" and re.search(r"(?i)min(?:imum)?[_ ]?(?:proto|version|tls)", line):
                    # A floor, not a single version: everything from it up to TLS 1.3 is enabled.
                    order = ["TLS 1.0", "TLS 1.1", "TLS 1.2", "TLS 1.3"]
                    if versions[0] in order:
                        versions = order[order.index(versions[0]):]
                for version in versions:
                    yield protocol_finding(
                        version, evidence, detector=detector, rule=rule.id, confidence=rule.confidence,
                        extra={"library": rule.library} if rule.library else None,
                    )


def _special_finding(rule: Rule, caps: dict[str, str], evidence: Evidence, detector: str) -> Finding:
    attrs = dict(rule.attrs or {})
    module = caps.get("module") or attrs.get("module")
    if rule.kind == "hardware":
        identity = {"type": attrs.get("type", "hsm"), "module": module or attrs.get("vendor")}
        vendor = attrs.get("vendor") or _hardware_vendor(module or "")
        name = attrs.get("label") or (f"{vendor} ({module})" if module and vendor else module or vendor or "Hardware security module")
        props = {"vendor": vendor, "type": attrs.get("type", "hsm"), "interface": attrs.get("interface")}
    else:
        identity = {"provider": attrs.get("provider"), "service": attrs.get("service"), "resource": caps.get("resource")}
        name = attrs.get("label", f"{attrs.get('provider', '').upper()} {attrs.get('service', '')}".strip())
        props = {k: v for k, v in attrs.items() if k not in ("label",)}
    return Finding(kind=rule.kind or "hardware", identity=identity, name=name, evidence=evidence, detector=detector,
                   rule=rule.id, confidence=rule.confidence, function=rule.function, properties=props)


_VENDORS = [
    ("softhsm", "SoftHSM (software emulation)"), ("cryptoki2", "Thales Luna"), ("luna", "Thales Luna"),
    ("cknfast", "Entrust nShield"), ("nshield", "Entrust nShield"), ("cs_pkcs11", "Utimaco"), ("utimaco", "Utimaco"),
    ("ykcs11", "Yubico YubiKey"), ("yubihsm", "Yubico YubiHSM"), ("opensc", "OpenSC smart card"),
    ("cloudhsm", "AWS CloudHSM"), ("tpm2", "TPM 2.0"), ("etpkcs11", "Thales SafeNet eToken"), ("nethsm", "Nitrokey NetHSM"),
    ("primus", "Securosys Primus"), ("fortanix", "Fortanix DSM"),
]


def _hardware_vendor(module: str) -> str | None:
    low = module.lower()
    return next((vendor for key, vendor in _VENDORS if key in low), None)
