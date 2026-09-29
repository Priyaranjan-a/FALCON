"""Live TLS endpoint assessment, including post-quantum key exchange.

Python's ``ssl`` module cannot report which key-exchange group a server
chose, so FALCON writes its own TLS 1.3 ClientHello. It offers the hybrid
X25519MLKEM768 group with a genuine ML-KEM-768 encapsulation key (plus X25519
and P-256 as fallbacks) and reads the group from the ServerHello, or from a
HelloRetryRequest, without completing the handshake. A standard handshake
then collects the negotiated version, cipher and certificate chain, and
legacy protocol versions are tested individually.
"""
from __future__ import annotations

import os
import re
import socket
import ssl
import struct
import warnings
from dataclasses import dataclass, field
from typing import Any, Iterator

from cryptography import x509
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ec, x25519

from . import names
from .detectors.material import certificate_finding
from .model import Evidence, Finding, algorithm_finding, algorithm_relation, protocol_finding

DETECTOR = "tls-endpoint"
_HRR_RANDOM = bytes.fromhex("CF21AD74E59A6111BE1D8C021E65B891C2A211167ABB8C5E079E09E2C8A8339C")
_HOST = re.compile(r"^(?:\[?[0-9a-fA-F:.]+\]?|[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?(?:\.[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?)*)$")


_ENDPOINT = re.compile(r"^\[(?P<v6>[0-9a-fA-F:.]+)\](?::(?P<p6>\d{1,5}))?$|^(?P<host>[^:\[\]]+)(?::(?P<port>\d{1,5}))?$")


class EndpointError(ValueError):
    pass


def parse_endpoints(text: str) -> list[tuple[str, int]]:
    endpoints = []
    for raw in re.split(r"[\s,;]+", text.strip()):
        if not raw:
            continue
        raw = re.sub(r"^(?:https?|tls)://", "", raw).split("/", 1)[0]
        m = _ENDPOINT.match(raw)
        if not m:
            raise EndpointError(f"“{raw}” is not a valid host:port")
        host = m.group("v6") or m.group("host")
        port_number = int(m.group("p6") or m.group("port") or 443)
        if not _HOST.match(host) or not 0 < port_number < 65536:
            raise EndpointError(f"“{raw}” is not a valid host:port")
        endpoints.append((host, port_number))
    if not endpoints:
        raise EndpointError("Enter at least one host, for example portal.example.org:443")
    if len(endpoints) > 50:
        raise EndpointError("Probe at most 50 endpoints per source")
    return endpoints


# -------------------------------------------------------------- ClientHello

def _u16(v: int) -> bytes:
    return struct.pack(">H", v)


def _vec16(data: bytes) -> bytes:
    return _u16(len(data)) + data


def _ext(ext_type: int, body: bytes) -> bytes:
    return _u16(ext_type) + _vec16(body)


def _mlkem768_share() -> bytes | None:
    try:
        from cryptography.hazmat.primitives.asymmetric import mlkem  # type: ignore[attr-defined]

        key = mlkem.MLKEM768PrivateKey.generate()
        return key.public_key().public_bytes_raw()
    except Exception:  # noqa: BLE001 - library without ML-KEM
        return None


def client_hello(host: str, offer_hybrid: bool = True) -> bytes:
    x25519_pub = x25519.X25519PrivateKey.generate().public_key().public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw)
    p256_pub = ec.generate_private_key(ec.SECP256R1()).public_key().public_bytes(serialization.Encoding.X962, serialization.PublicFormat.UncompressedPoint)
    groups = [0x001D, 0x0017, 0x0018]
    shares = _u16(0x001D) + _vec16(x25519_pub) + _u16(0x0017) + _vec16(p256_pub)
    if offer_hybrid:
        mlkem_ek = _mlkem768_share()
        if mlkem_ek:
            groups = [0x11EC] + groups
            # X25519MLKEM768 key share: ML-KEM-768 encapsulation key, then the X25519 public key.
            shares = _u16(0x11EC) + _vec16(mlkem_ek + x25519_pub) + shares
    suites = [0x1301, 0x1302, 0x1303, 0xC02B, 0xC02F, 0xC02C, 0xC030, 0xCCA9, 0xCCA8, 0x009C, 0x009D, 0x002F, 0x0035]
    extensions = b""
    if not re.match(r"^[0-9.:]+$", host):
        name = host.encode("idna")
        extensions += _ext(0x0000, _vec16(b"\x00" + _vec16(name)))
    extensions += _ext(0x000A, _vec16(b"".join(_u16(g) for g in groups)))
    extensions += _ext(0x000B, b"\x01\x00")
    sig_algs = [0x0403, 0x0804, 0x0401, 0x0503, 0x0805, 0x0501, 0x0806, 0x0601, 0x0807, 0x0808, 0x0904, 0x0905, 0x0906, 0x0201, 0x0203]
    extensions += _ext(0x000D, _vec16(b"".join(_u16(s) for s in sig_algs)))
    extensions += _ext(0x002B, b"\x04" + _u16(0x0304) + _u16(0x0303))
    extensions += _ext(0x002D, b"\x01\x01")
    extensions += _ext(0x0033, _vec16(shares))
    body = _u16(0x0303) + os.urandom(32) + b"\x20" + os.urandom(32) + _vec16(b"".join(_u16(s) for s in suites)) + b"\x01\x00" + _vec16(extensions)
    handshake = b"\x01" + struct.pack(">I", len(body))[1:] + body
    return b"\x16\x03\x01" + _u16(len(handshake)) + handshake


@dataclass
class HelloResult:
    version: str | None = None
    cipher: str | None = None
    group: str | None = None
    retry: bool = False
    alert: str | None = None
    raw_group: int | None = None
    notes: list[str] = field(default_factory=list)


_SUITE_NAMES = {0x1301: "TLS_AES_128_GCM_SHA256", 0x1302: "TLS_AES_256_GCM_SHA384", 0x1303: "TLS_CHACHA20_POLY1305_SHA256",
                0xC02B: "TLS_ECDHE_ECDSA_WITH_AES_128_GCM_SHA256", 0xC02F: "TLS_ECDHE_RSA_WITH_AES_128_GCM_SHA256",
                0xC02C: "TLS_ECDHE_ECDSA_WITH_AES_256_GCM_SHA384", 0xC030: "TLS_ECDHE_RSA_WITH_AES_256_GCM_SHA384",
                0xCCA9: "TLS_ECDHE_ECDSA_WITH_CHACHA20_POLY1305_SHA256", 0xCCA8: "TLS_ECDHE_RSA_WITH_CHACHA20_POLY1305_SHA256",
                0x009C: "TLS_RSA_WITH_AES_128_GCM_SHA256", 0x009D: "TLS_RSA_WITH_AES_256_GCM_SHA384",
                0x002F: "TLS_RSA_WITH_AES_128_CBC_SHA", 0x0035: "TLS_RSA_WITH_AES_256_CBC_SHA"}
_ALERTS = {40: "handshake failure", 70: "protocol version not supported", 71: "insufficient security", 47: "illegal parameter", 112: "unrecognised name"}


def _recv_exact(sock: socket.socket, n: int) -> bytes:
    data = b""
    while len(data) < n:
        chunk = sock.recv(n - len(data))
        if not chunk:
            raise ConnectionError("connection closed")
        data += chunk
    return data


def probe_hello(host: str, port: int, timeout: float = 6.0, offer_hybrid: bool = True) -> HelloResult:
    result = HelloResult()
    with socket.create_connection((host, port), timeout=timeout) as sock:
        sock.sendall(client_hello(host, offer_hybrid))
        header = _recv_exact(sock, 5)
        content_type, _, length = header[0], header[1:3], struct.unpack(">H", header[3:5])[0]
        record = _recv_exact(sock, length)
    if content_type == 0x15:
        result.alert = _ALERTS.get(record[1] if len(record) > 1 else 0, f"alert {record[1] if len(record) > 1 else '?'}")
        return result
    if content_type != 0x16 or record[0] != 0x02:
        result.alert = "unexpected response"
        return result
    body = record[4:]
    legacy_version = struct.unpack(">H", body[0:2])[0]
    random = body[2:34]
    sid_len = body[34]
    offset = 35 + sid_len
    cipher = struct.unpack(">H", body[offset: offset + 2])[0]
    offset += 3
    result.retry = random == _HRR_RANDOM
    result.cipher = _SUITE_NAMES.get(cipher, f"0x{cipher:04X}")
    result.version = {0x0303: "TLS 1.2", 0x0302: "TLS 1.1", 0x0301: "TLS 1.0"}.get(legacy_version)
    if offset + 2 <= len(body):
        ext_len = struct.unpack(">H", body[offset: offset + 2])[0]
        offset += 2
        end = min(len(body), offset + ext_len)
        while offset + 4 <= end:
            ext_type, ext_size = struct.unpack(">HH", body[offset: offset + 4])
            data = body[offset + 4: offset + 4 + ext_size]
            if ext_type == 0x002B and len(data) >= 2 and struct.unpack(">H", data[:2])[0] == 0x0304:
                result.version = "TLS 1.3"
            elif ext_type == 0x0033 and len(data) >= 2:
                result.raw_group = struct.unpack(">H", data[:2])[0]
                result.group = names.GROUP_CODES.get(result.raw_group, f"0x{result.raw_group:04X}")
            offset += 4 + ext_size
    return result


# --------------------------------------------------------- standard handshake

def _handshake(host: str, port: int, timeout: float, version: ssl.TLSVersion | None = None) -> tuple[str | None, str | None, list[bytes]]:
    ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    if version is not None:
        # Testing whether a server still accepts TLS 1.0/1.1 means asking for them on purpose.
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", DeprecationWarning)
            ctx.minimum_version = version
            ctx.maximum_version = version
        try:
            ctx.set_ciphers("ALL:@SECLEVEL=0")
        except ssl.SSLError:
            pass
    with socket.create_connection((host, port), timeout=timeout) as raw:
        server_name = None if re.match(r"^[0-9.:]+$", host) else host
        with ctx.wrap_socket(raw, server_hostname=server_name) as tls:
            chain: list[bytes] = []
            try:
                chain = [c if isinstance(c, bytes) else c.public_bytes(ssl.ENCODING_DER) for c in tls.get_unverified_chain() or []]
            except (AttributeError, ssl.SSLError):
                der = tls.getpeercert(binary_form=True)
                chain = [der] if der else []
            cipher = tls.cipher()
            raw_version = tls.version()
            version = (names.tls_version(raw_version) or raw_version) if raw_version else None
            return version, cipher[0] if cipher else None, chain


_LEGACY = [("TLS 1.0", "TLSv1"), ("TLS 1.1", "TLSv1_1"), ("TLS 1.2", "TLSv1_2")]


def assess_endpoint(host: str, port: int, timeout: float = 6.0) -> tuple[list[Finding], dict[str, Any]]:
    """Returns findings and a summary for one endpoint. Raises OSError when unreachable."""
    locator = f"tls://{host}:{port}"
    evidence = Evidence(locator)
    findings: list[Finding] = []
    summary: dict[str, Any] = {"endpoint": f"{host}:{port}"}

    hello = probe_hello(host, port, timeout)
    summary["pq_probe"] = {"offered": ["X25519MLKEM768", "x25519", "secp256r1", "secp384r1"], "selected": hello.group,
                           "hello_retry": hello.retry, "alert": hello.alert, "version": hello.version}
    hybrid = hello.group in ("X25519MLKEM768", "SecP256r1MLKEM768", "SecP384r1MLKEM1024")

    try:
        version, cipher, chain = _handshake(host, port, timeout)
    except (OSError, ssl.SSLError) as err:
        version, cipher, chain = hello.version, hello.cipher, []
        summary["handshake_error"] = str(err)[:200]
    summary.update(version=version, cipher=cipher, certificates=len(chain))

    related = []
    if hello.group:
        group_ref = names.tls_group(hello.group)
        if group_ref:
            related.append(algorithm_relation("negotiates", group_ref))
            findings.append(algorithm_finding(group_ref, evidence, detector=DETECTOR, rule="endpoint.key-exchange", confidence=0.99,
                                              function="key-agree", extra={"endpoint": f"{host}:{port}", "negotiated": True}))
    if cipher:
        suite_refs, facts = names.tls_suite(cipher)
        for ref in suite_refs:
            related.append(algorithm_relation("negotiates", ref))
            findings.append(algorithm_finding(ref, evidence, detector=DETECTOR, rule="endpoint.cipher", confidence=0.99,
                                              function="tls-cipher-suite", extra={"endpoint": f"{host}:{port}", "cipher_suite": cipher}))
    if version:
        findings.append(protocol_finding(version, evidence, detector=DETECTOR, rule="endpoint.negotiated", confidence=0.99,
                                         hybrid=hybrid and version == "TLS 1.3",
                                         extra={"endpoint": f"{host}:{port}", "negotiated": True, "cipher_suite": cipher,
                                                "key_exchange": hello.group}, related=related))
    for index, der in enumerate(chain):
        try:
            cert = x509.load_der_x509_certificate(der)
        except ValueError:
            continue
        finding = certificate_finding(cert, evidence, rule="endpoint.certificate", source=f"served by {host}:{port}")
        finding.properties.update(chain_position=index, served_by=f"{host}:{port}")
        findings.append(finding)

    also_accepted = []
    for label, attr in _LEGACY:
        tls_version = getattr(ssl.TLSVersion, attr, None)
        if tls_version is None or label == version:
            continue
        try:
            _handshake(host, port, timeout, tls_version)
        except (OSError, ssl.SSLError, ValueError):
            continue
        also_accepted.append(label)
        findings.append(protocol_finding(label, evidence, detector=DETECTOR, rule="endpoint.accepted", confidence=0.97,
                                         extra={"endpoint": f"{host}:{port}", "negotiated": False, "accepted_when_offered": True}))
    summary["also_accepted"] = also_accepted
    return findings, summary


def assess(endpoints: list[tuple[str, int]], timeout: float = 6.0) -> Iterator[tuple[str, list[Finding] | None, dict[str, Any]]]:
    for host, port in endpoints:
        try:
            findings, summary = assess_endpoint(host, port, timeout)
            yield f"{host}:{port}", findings, summary
        except (OSError, ConnectionError, ssl.SSLError, struct.error, IndexError) as err:
            yield f"{host}:{port}", None, {"endpoint": f"{host}:{port}", "error": str(err)[:200] or type(err).__name__}
