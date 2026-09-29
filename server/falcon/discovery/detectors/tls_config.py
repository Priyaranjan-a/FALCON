"""Protocol configuration: TLS, SSH and IPsec settings in configuration files.

One engine reads ``key = value`` style settings across formats (nginx, Apache,
HAProxy, OpenSSL, Spring, Tomcat, Envoy, Traefik, Kubernetes annotations,
PostgreSQL, Redis, strongSwan, OpenSSH) and classifies each key by meaning:
protocol versions, cipher suites, key-exchange groups, IPsec proposals, SSH
algorithm lists, JWT algorithms and general algorithm settings.
"""
from __future__ import annotations

import re
import ssl
from functools import lru_cache
from typing import Iterator

from .. import names
from ..catalogue import AlgorithmRef
from ..model import Evidence, Finding, algorithm_finding, algorithm_relation, protocol_finding, snippet
from ..walker import FileInfo

DETECTOR = "protocol-config"

ALL_TLS = ["TLS 1.0", "TLS 1.1", "TLS 1.2", "TLS 1.3"]
_VERSION_TOKEN = re.compile(r"([+-]?)(SSLv[23]|TLSv?1(?:[._]\d)?(?!\d)|TLS[_ ]?1[._]\d|DTLSv?1(?:[._]\d)?|VersionTLS1\d|\ball\b)", re.IGNORECASE)

_VERSION_KEYS = ("protocol", "minversion", "min_version", "min-version", "minimum_protocol_version", "tls_version", "tlsversion",
                 "sslversion", "ssl_version", "ssl-min-ver", "enabled-protocols", "enabledprotocols", "sslenabledprotocols",
                 "tls_minimum_protocol_version", "min_tls_version", "minimum_tls_version", "minimumtlsversion", "tls-protocols",
                 "ssl_protocols", "sslprotocol", "security_policy", "ssl_min_protocol_version", "protocols", "minprotocol")
_CIPHER_KEYS = ("cipher", "ciphersuites", "cipher_suites", "cipherstring")
_GROUP_KEYS = ("ecdh_curve", "ecdhcurve", "ecdh-curves", "ecdh_curves", "groups", "curves", "curve_preferences",
               "curvepreferences", "supported_groups", "tls-groups", "ssl-default-bind-curves")
_IPSEC_KEYS = ("ike", "esp", "ah", "proposals", "esp_proposals", "ike_proposals", "phase1alg", "phase2alg", "ike-proposal")
_SSH_KEYS = {"kexalgorithms": "kex", "ciphers": "cipher", "macs": "mac", "hostkeyalgorithms": "hostkey",
             "pubkeyacceptedalgorithms": "hostkey", "pubkeyacceptedkeytypes": "hostkey", "casignaturealgorithms": "hostkey",
             "hostbasedacceptedalgorithms": "hostkey"}
_ALGORITHM_KEY = re.compile(r"(?:^|[._-])(algorithm|algorithms|digest|hash_?algorithm|signature_?algorithm|key_?algorithm|default_md|mac_?algorithm|encryption_?algorithm|kdf)$")

_PAIR = re.compile(r"""^[-\s]*["']?(?P<key>[A-Za-z_][\w.@/\[\]:-]*?)["']?\s*(?:[:=]\s*|\s+)(?P<value>.+?)\s*[;,]?\s*$""")
_XML_ATTR = re.compile(r'([\w.:-]+)\s*=\s*"([^"]*)"')
_JSON_PAIR = re.compile(r'"([\w.-]+)"\s*:\s*"([^"]*)"')
_COMMENT = ("#", "//", ";", "<!--", "*", "/*", "--")


@lru_cache(maxsize=512)
def expand_cipher_string(value: str) -> tuple[str, ...]:
    """Explicit suite names are returned as written; OpenSSL policy strings
    (``HIGH:!aNULL:!MD5``) are expanded with the local OpenSSL build."""
    text = value.strip().strip("\"'")
    tokens = [t for t in re.split(r"[:,\s]+", text) if t]
    explicit = [t for t in tokens if names.tls_suite(t)[0]]
    if explicit and len(explicit) >= len(tokens) - tokens.count("!aNULL") - 1:
        return tuple(explicit)
    try:
        ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
        ctx.set_ciphers(text)
        return tuple(c["name"] for c in ctx.get_ciphers() if not c["name"].startswith("TLS_") or "TLS_" in text)
    except (ssl.SSLError, ValueError):
        return tuple(explicit)


def _pairs(line: str) -> list[tuple[str, str]]:
    stripped = line.strip()
    if not stripped or stripped.startswith(_COMMENT):
        return []
    found: list[tuple[str, str]] = []
    if '="' in stripped and "<" in stripped:
        found += _XML_ATTR.findall(stripped)
    if '":' in stripped.replace(" ", ""):
        found += _JSON_PAIR.findall(stripped)
    if not found:
        m = _PAIR.match(stripped)
        if m:
            value = re.split(r"\s+#", m.group("value"), maxsplit=1)[0].strip().strip("\"'")
            found.append((m.group("key"), value))
    return found


def _versions(key: str, value: str) -> list[str]:
    tokens = _VERSION_TOKEN.findall(value)
    if not tokens:
        return []
    enabled: list[str] = []
    for sign, token in tokens:
        versions = ALL_TLS if token.lower() == "all" else [v for v in [names.tls_version(token.replace(" ", ""))] if v]
        for version in versions:
            if sign == "-":
                enabled = [v for v in enabled if v != version]
            elif version not in enabled:
                enabled.append(version)
    low = key.lower()
    if "min" in low and len(enabled) == 1 and enabled[0] in ALL_TLS:
        enabled = ALL_TLS[ALL_TLS.index(enabled[0]):]
    return enabled


def _elb_policy(value: str) -> list[str]:
    """AWS listener policy names encode their floor, e.g. ELBSecurityPolicy-TLS13-1-2-2021-06."""
    m = re.search(r"TLS13-1-([0-3])|TLS-1-([0-3])|FS-1-([0-3])", value)
    if m:
        floor = next(g for g in m.groups() if g)
        return ALL_TLS[int(floor):]
    if re.search(r"ELBSecurityPolicy-201[5-6]", value):
        return ALL_TLS[:3]
    return []


def scan(file: FileInfo, text: str) -> Iterator[Finding]:
    lines = text.splitlines()
    rel = file.rel
    is_ssh = "ssh" in rel.lower() and (file.name.endswith("_config") or ".conf" in file.name or "sshd" in file.name)
    settings: list[tuple[int, str, str]] = []
    for index, line in enumerate(lines):
        for key, value in _pairs(line):
            if value:
                settings.append((index, key, value))

    # First pass: hybrid key exchange anywhere in the file upgrades TLS 1.3 findings.
    groups_by_line: dict[int, list[AlgorithmRef]] = {}
    for index, key, value in settings:
        last = key.lower().split(".")[-1].split("/")[-1]
        if any(g == last or last.endswith(g) for g in _GROUP_KEYS) or ("groups" in last and "ssl" in key.lower()):
            refs = [r for t in re.split(r"[:,\s\[\]\"']+", value) if t and (r := names.tls_group(t))]
            if refs:
                groups_by_line[index] = refs
    hybrid = any(r.algorithm in ("X25519MLKEM768", "SecP256r1MLKEM768", "SecP384r1MLKEM1024", "X25519Kyber768Draft00") or
                 (r.algorithm == "ML-KEM") for refs in groups_by_line.values() for r in refs)

    ssh_versions: list[tuple[int, str]] = []
    ssh_hybrid = False
    for index, key, value in settings:
        low = key.lower()
        last = low.split(".")[-1].split("/")[-1]
        evidence = Evidence(rel, index + 1, None, snippet(lines, index))

        if is_ssh and last in _SSH_KEYS:
            for token in re.split(r"[,\s]+", value.lstrip("+-^")):
                ref = names.ssh_algorithm(token) if token else None
                if ref:
                    if ref.algorithm in ("sntrup761x25519", "mlkem768x25519", "SecP256r1MLKEM768", "SecP384r1MLKEM1024"):
                        ssh_hybrid = True
                    yield algorithm_finding(ref, evidence, detector=DETECTOR, rule=f"ssh.{_SSH_KEYS[last]}", confidence=0.93,
                                            function={"kex": "key-agree", "cipher": "encrypt", "mac": "mac", "hostkey": "sign"}[_SSH_KEYS[last]],
                                            library="OpenSSH", extra={"setting": key})
            ssh_versions.append((index, "SSH 2"))
            continue
        if is_ssh and last == "protocol":
            ssh_versions.append((index, "SSH 1" if value.strip().startswith("1") else "SSH 2"))
            continue

        if index in groups_by_line:
            for ref in groups_by_line[index]:
                yield algorithm_finding(ref, evidence, detector=DETECTOR, rule="tls.groups", confidence=0.93,
                                        function="key-agree", extra={"setting": key})
            continue

        if last in _IPSEC_KEYS:
            for proposal in re.split(r"[,\s]+", value):
                refs, post_quantum = names.ipsec_proposal(proposal)
                for ref in refs:
                    yield algorithm_finding(ref, evidence, detector=DETECTOR, rule="ipsec.proposal", confidence=0.9,
                                            function="ipsec", library="IPsec", extra={"proposal": proposal})
                if refs and last in ("ike", "proposals", "ike_proposals", "phase1alg", "ike-proposal"):
                    version = "IKEv1" if re.search(r"keyexchange\s*=\s*ikev1", text, re.IGNORECASE) else "IKEv2"
                    yield protocol_finding(version, evidence, detector=DETECTOR, rule="ipsec.version", confidence=0.85,
                                           hybrid=post_quantum, extra={"proposal": proposal},
                                           related=[algorithm_relation("negotiates", r) for r in refs])
            continue

        if "cipher" in last and "disabled" not in low and "exclude" not in low and not is_ssh:
            suites = expand_cipher_string(value)
            if not suites:
                continue
            explicit = bool(names.tls_suite(re.split(r"[:,\s]+", value.strip())[0])[0])
            seen: set[tuple] = set()
            weak_facts: set[str] = set()
            for suite in suites:
                refs, facts = names.tls_suite(suite)
                if facts.get("forward_secrecy") is False:
                    weak_facts.add("Suites without forward secrecy (RSA key transport)")
                if facts.get("export"):
                    weak_facts.add("Export-grade suites")
                if facts.get("anonymous"):
                    weak_facts.add("Anonymous (unauthenticated) suites")
                for ref in refs:
                    if (ref.algorithm, ref.parameter, ref.mode, ref.hash) in seen:
                        continue
                    seen.add((ref.algorithm, ref.parameter, ref.mode, ref.hash))
                    yield algorithm_finding(ref, evidence, detector=DETECTOR, rule="tls.ciphers", confidence=0.9,
                                            function="tls-cipher-suite",
                                            extra={"setting": key, "cipher_policy": value[:300], "suites": len(suites),
                                                   "expanded_with": None if explicit else ssl.OPENSSL_VERSION,
                                                   "warnings": sorted(weak_facts) or None})
            continue

        if (last in ("ssl_policy",) or value.startswith("ELBSecurityPolicy")) and "ELBSecurityPolicy" in value:
            for version in _elb_policy(value):
                yield protocol_finding(version, evidence, detector=DETECTOR, rule="tls.aws-policy", confidence=0.85,
                                       hybrid=("PQ" in value and version == "TLS 1.3"), extra={"policy": value})
            continue

        if any(k in last for k in _VERSION_KEYS) and "disabled" not in low and "exclude" not in low:
            for version in _versions(last, value):
                yield protocol_finding(version, evidence, detector=DETECTOR, rule="tls.protocols", confidence=0.9,
                                       hybrid=hybrid and version == "TLS 1.3", extra={"setting": key})
            continue

        if ("jwt" in low or "jws" in low or "jose" in low or last in ("alg", "jws-algorithms", "jws-algorithm")) and not is_ssh:
            for token in re.split(r"[,\s\[\]]+", value):
                ref = names.jose_alg(token)
                if ref:
                    yield algorithm_finding(ref, evidence, detector=DETECTOR, rule="jwt.algorithm", confidence=0.88,
                                            function="sign", library="JWT", extra={"setting": key})
            continue

        if last == "default_bits" and value.isdigit():
            yield algorithm_finding(AlgorithmRef("RSA", value), evidence, detector=DETECTOR, rule="openssl.default_bits",
                                    confidence=0.85, function="keygen", library="OpenSSL", extra={"setting": key})
            continue

        if _ALGORITHM_KEY.search(last) and len(value) < 80:
            ref = names.any_name(value.split(",")[0].strip())
            if ref:
                yield algorithm_finding(ref, evidence, detector=DETECTOR, rule="config.algorithm", confidence=0.75,
                                        function="config", extra={"setting": key})

    for index, version in ssh_versions[:1]:
        yield protocol_finding(version, Evidence(rel, index + 1, None, snippet(lines, index)), detector=DETECTOR,
                               rule="ssh.protocol", confidence=0.85, hybrid=ssh_hybrid, extra={"product": "OpenSSH"})
