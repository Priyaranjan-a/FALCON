"""Certificates, keys and keystores.

Key material never leaves this module: a key is identified by the SHA-256 of
its public key (SubjectPublicKeyInfo), and only metadata (algorithm, size,
whether it was private or encrypted) is reported. Finding an unencrypted
private key in a repository or image is itself flagged as an exposure.
"""
from __future__ import annotations

import base64
import hashlib
import json
import re
import struct
from datetime import datetime, timezone
from typing import Any, Iterator

from cryptography import x509
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import dh, dsa, ec, ed448, ed25519, rsa, x448, x25519
from cryptography.hazmat.primitives.serialization import pkcs12

from ..catalogue import AlgorithmRef, canonical_curve, display_name
from ..model import Evidence, Finding, Relation, algorithm_properties, algorithm_relation
from ..walker import FileInfo

DETECTOR = "crypto-material"
_PEM = re.compile(rb"-----BEGIN ([A-Z0-9 ]+)-----\r?\n(.*?)-----END \1-----", re.DOTALL)
_DEFAULT_PASSWORDS = (None, b"", b"changeit", b"password", b"changeme")


# ------------------------------------------------------------------- helpers

def key_algorithm(key: Any) -> AlgorithmRef | None:
    if isinstance(key, (rsa.RSAPublicKey, rsa.RSAPrivateKey)):
        return AlgorithmRef("RSA", str(key.key_size))
    if isinstance(key, (ec.EllipticCurvePublicKey, ec.EllipticCurvePrivateKey)):
        return AlgorithmRef("ECDSA", canonical_curve(key.curve.name) or key.curve.name)
    if isinstance(key, (ed25519.Ed25519PublicKey, ed25519.Ed25519PrivateKey)):
        return AlgorithmRef("EdDSA", "Ed25519")
    if isinstance(key, (ed448.Ed448PublicKey, ed448.Ed448PrivateKey)):
        return AlgorithmRef("EdDSA", "Ed448")
    if isinstance(key, (x25519.X25519PublicKey, x25519.X25519PrivateKey)):
        return AlgorithmRef("X25519")
    if isinstance(key, (x448.X448PublicKey, x448.X448PrivateKey)):
        return AlgorithmRef("X448")
    if isinstance(key, (dsa.DSAPublicKey, dsa.DSAPrivateKey)):
        return AlgorithmRef("DSA", str(key.key_size))
    if isinstance(key, (dh.DHPublicKey, dh.DHPrivateKey)):
        return AlgorithmRef("DH", str(key.key_size))
    type_name = type(key).__name__
    m = re.search(r"MLDSA(\d+)", type_name)
    if m:
        return AlgorithmRef("ML-DSA", m.group(1))
    m = re.search(r"MLKEM(\d+)", type_name)
    if m:
        return AlgorithmRef("ML-KEM", m.group(1))
    return None


def _spki_digest(public_key: Any) -> str | None:
    try:
        der = public_key.public_bytes(serialization.Encoding.DER, serialization.PublicFormat.SubjectPublicKeyInfo)
    except Exception:  # noqa: BLE001 - some key types have no SPKI form
        try:
            der = public_key.public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw)
        except Exception:  # noqa: BLE001
            return None
    return hashlib.sha256(der).hexdigest()


def _key_finding(ref: AlgorithmRef | None, spki: str | None, evidence: Evidence, *, private: bool, encrypted: bool,
                 fmt: str, rule: str, extra: dict[str, Any] | None = None, raw_digest: str | None = None) -> Finding:
    identity = {"spki_sha256": spki} if spki else {"file_sha256": raw_digest}
    algorithm_label = display_name(ref) if ref else "Unknown algorithm"
    kind_label = "private key" if private else "public key"
    props: dict[str, Any] = {"format": fmt, "private": private, "encrypted": encrypted, "key_algorithm": algorithm_label}
    if ref:
        props.update(algorithm_properties(ref))
    if private and not encrypted:
        props["exposure"] = "Unencrypted private key stored at rest"
    if extra:
        props.update(extra)
    return Finding(kind="key", identity=identity, name=f"{algorithm_label} {kind_label}", evidence=evidence, detector=DETECTOR,
                   rule=rule, confidence=0.99 if ref else 0.7, function="key-material", properties=props,
                   related=[algorithm_relation("uses-algorithm", ref)] if ref else [])


def certificate_finding(cert: x509.Certificate, evidence: Evidence, *, rule: str, source: str = "file") -> Finding:
    der = cert.public_bytes(serialization.Encoding.DER)
    sha256 = hashlib.sha256(der).hexdigest()
    public_key = cert.public_key()
    key_ref = key_algorithm(public_key)
    spki = _spki_digest(public_key)
    sig_ref = _signature_ref(cert)
    now = datetime.now(timezone.utc)
    not_after = cert.not_valid_after_utc
    not_before = cert.not_valid_before_utc
    try:
        basic = cert.extensions.get_extension_for_class(x509.BasicConstraints).value
        is_ca = basic.ca
    except x509.ExtensionNotFound:
        is_ca = False
    try:
        sans = cert.extensions.get_extension_for_class(x509.SubjectAlternativeName).value
        dns_names = sans.get_values_for_type(x509.DNSName)
    except x509.ExtensionNotFound:
        dns_names = []
    subject = cert.subject.rfc4514_string()
    common_name = next((a.value for a in cert.subject if a.oid == x509.NameOID.COMMON_NAME), None)
    props: dict[str, Any] = {
        "subject": subject, "issuer": cert.issuer.rfc4514_string(), "serial": format(cert.serial_number, "x"),
        "not_before": not_before.isoformat(), "not_after": not_after.isoformat(),
        "days_remaining": (not_after - now).days, "expired": not_after < now,
        "self_signed": cert.issuer == cert.subject, "is_ca": is_ca, "dns_names": dns_names[:20],
        "key_algorithm": display_name(key_ref) if key_ref else None,
        "signature_algorithm": display_name(sig_ref) if sig_ref else cert.signature_algorithm_oid.dotted_string,
        "version": cert.version.name, "source": source,
    }
    if key_ref:
        props.update(algorithm_properties(key_ref))
    related: list[Relation] = []
    if key_ref and spki:
        related.append(Relation("certifies-key", "key", {"spki_sha256": spki}, f"{display_name(key_ref)} public key",
                                {"format": "certificate", "private": False, "encrypted": False,
                                 "key_algorithm": display_name(key_ref), **algorithm_properties(key_ref)}))
    if sig_ref:
        related.append(algorithm_relation("signed-with", sig_ref))
    label = common_name or subject or "certificate"
    return Finding(kind="certificate", identity={"sha256": sha256}, name=str(label), evidence=evidence, detector=DETECTOR,
                   rule=rule, confidence=0.99, function="certificate", properties=props, related=related)


def _signature_ref(cert: x509.Certificate) -> AlgorithmRef | None:
    from .. import names

    oid_name = cert.signature_algorithm_oid._name  # e.g. sha256WithRSAEncryption, ecdsa-with-SHA384
    ref = names.signature_name(oid_name) if oid_name else None
    if ref:
        return ref
    dotted = cert.signature_algorithm_oid.dotted_string
    pq = {"2.16.840.1.101.3.4.3.17": ("ML-DSA", "44"), "2.16.840.1.101.3.4.3.18": ("ML-DSA", "65"),
          "2.16.840.1.101.3.4.3.19": ("ML-DSA", "87")}.get(dotted)
    if pq:
        return AlgorithmRef(*pq)
    if dotted.startswith("2.16.840.1.101.3.4.3.") and 20 <= int(dotted.rsplit(".", 1)[1]) <= 31:
        return AlgorithmRef("SLH-DSA")
    return None


# ----------------------------------------------------------------- PEM / DER

def _load_private(data: bytes, pem: bool) -> tuple[Any | None, bool]:
    loader = serialization.load_pem_private_key if pem else serialization.load_der_private_key
    try:
        # Only the key's type and size are read, so the costly RSA consistency check is skipped.
        return loader(data, password=None, unsafe_skip_rsa_key_validation=True), False
    except TypeError:
        return None, True  # password required
    except (ValueError, Exception):  # noqa: BLE001 - unsupported or corrupt
        return None, False


def _scan_pem(raw: bytes, file: FileInfo) -> Iterator[Finding]:
    text_lines = raw.decode("latin-1").splitlines()
    for match in _PEM.finditer(raw):
        label = match.group(1).decode()
        block = match.group(0)
        line = raw[: match.start()].count(b"\n") + 1
        evidence = Evidence(file.rel, line, None, [(line, text_lines[line - 1] if line - 1 < len(text_lines) else f"-----BEGIN {label}-----")])
        try:
            if label in ("CERTIFICATE", "TRUSTED CERTIFICATE", "X509 CERTIFICATE"):
                yield certificate_finding(x509.load_pem_x509_certificate(block.replace(b"TRUSTED ", b"")), evidence, rule="pem.certificate")
            elif label in ("CERTIFICATE REQUEST", "NEW CERTIFICATE REQUEST"):
                csr = x509.load_pem_x509_csr(block)
                ref = key_algorithm(csr.public_key())
                yield _key_finding(ref, _spki_digest(csr.public_key()), evidence, private=False, encrypted=False,
                                   fmt="certificate request", rule="pem.csr",
                                   extra={"subject": csr.subject.rfc4514_string()})
            elif label == "OPENSSH PRIVATE KEY":
                yield from _openssh_private(base64.b64decode(match.group(2)), evidence)
            elif "PRIVATE KEY" in label:
                key, encrypted = _load_private(block, pem=True)
                encrypted = encrypted or label == "ENCRYPTED PRIVATE KEY" or b"Proc-Type: 4,ENCRYPTED" in block
                if key is not None:
                    public = key.public_key()
                    yield _key_finding(key_algorithm(key), _spki_digest(public), evidence, private=True, encrypted=False,
                                       fmt=f"PEM ({label.title()})", rule="pem.private-key")
                else:
                    guess = {"RSA PRIVATE KEY": AlgorithmRef("RSA"), "EC PRIVATE KEY": AlgorithmRef("ECDSA"),
                             "DSA PRIVATE KEY": AlgorithmRef("DSA")}.get(label)
                    yield _key_finding(guess, None, evidence, private=True, encrypted=encrypted, fmt=f"PEM ({label.title()})",
                                       rule="pem.private-key", raw_digest=hashlib.sha256(block).hexdigest())
            elif "PUBLIC KEY" in label:
                key = serialization.load_pem_public_key(block)
                yield _key_finding(key_algorithm(key), _spki_digest(key), evidence, private=False, encrypted=False,
                                   fmt="PEM public key", rule="pem.public-key")
            elif label.startswith("PGP"):
                yield _key_finding(None, None, evidence, private="PRIVATE" in label, encrypted=True, fmt="OpenPGP",
                                   rule="pgp.block", raw_digest=hashlib.sha256(block).hexdigest(),
                                   extra={"note": "OpenPGP key block; algorithm not parsed"})
        except Exception:  # noqa: BLE001 - a corrupt block must not stop the scan
            continue


def _scan_der(raw: bytes, file: FileInfo) -> Iterator[Finding]:
    evidence = Evidence(file.rel, None, None, None)
    try:
        yield certificate_finding(x509.load_der_x509_certificate(raw), evidence, rule="der.certificate")
        return
    except Exception:  # noqa: BLE001
        pass
    try:
        key = serialization.load_der_public_key(raw)
        yield _key_finding(key_algorithm(key), _spki_digest(key), evidence, private=False, encrypted=False,
                           fmt="DER public key", rule="der.public-key")
        return
    except Exception:  # noqa: BLE001
        pass
    key, encrypted = _load_private(raw, pem=False)
    if key is not None:
        yield _key_finding(key_algorithm(key), _spki_digest(key.public_key()), evidence, private=True, encrypted=False,
                           fmt="DER private key", rule="der.private-key")


# ------------------------------------------------------------------- OpenSSH

def _ssh_string(data: bytes, offset: int) -> tuple[bytes, int]:
    (length,) = struct.unpack(">I", data[offset: offset + 4])
    return data[offset + 4: offset + 4 + length], offset + 4 + length


def ssh_public_blob(blob: bytes) -> AlgorithmRef | None:
    key_type, offset = _ssh_string(blob, 0)
    kt = key_type.decode("ascii", "replace")
    if kt == "ssh-rsa":
        _e, offset = _ssh_string(blob, offset)
        n, _ = _ssh_string(blob, offset)
        return AlgorithmRef("RSA", str(int.from_bytes(n, "big").bit_length()))
    if kt.startswith("ecdsa-sha2-") or kt.startswith("sk-ecdsa-sha2-"):
        return AlgorithmRef("ECDSA", canonical_curve(kt.split("-")[-1].split("@")[0]) or "P-256")
    if kt in ("ssh-ed25519", "sk-ssh-ed25519@openssh.com"):
        return AlgorithmRef("EdDSA", "Ed25519")
    if kt == "ssh-ed448":
        return AlgorithmRef("EdDSA", "Ed448")
    if kt == "ssh-dss":
        _p, _ = _ssh_string(blob, offset)
        return AlgorithmRef("DSA", str(int.from_bytes(_p, "big").bit_length()))
    return None


def _openssh_private(data: bytes, evidence: Evidence) -> Iterator[Finding]:
    if not data.startswith(b"openssh-key-v1\x00"):
        return
    offset = len(b"openssh-key-v1\x00")
    cipher, offset = _ssh_string(data, offset)
    _kdf, offset = _ssh_string(data, offset)
    _kdf_options, offset = _ssh_string(data, offset)
    (count,) = struct.unpack(">I", data[offset: offset + 4])
    offset += 4
    for _ in range(min(count, 8)):
        blob, offset = _ssh_string(data, offset)
        ref = ssh_public_blob(blob)
        yield _key_finding(ref, hashlib.sha256(blob).hexdigest(), evidence, private=True, encrypted=cipher != b"none",
                           fmt="OpenSSH private key", rule="openssh.private-key")


def _scan_ssh_public_lines(text: str, file: FileInfo) -> Iterator[Finding]:
    lines = text.splitlines()
    for index, line in enumerate(lines[:5000]):
        m = re.search(r"\b((?:sk-)?(?:ssh-(?:rsa|dss|ed25519|ed448)|ecdsa-sha2-nistp\d+)(?:@openssh\.com)?)\s+([A-Za-z0-9+/]{40,}={0,2})", line)
        if not m:
            continue
        try:
            blob = base64.b64decode(m.group(2))
            ref = ssh_public_blob(blob)
        except Exception:  # noqa: BLE001
            continue
        comment = line[m.end():].strip()
        evidence = Evidence(file.rel, index + 1, None, [(index + 1, f"{m.group(1)} {m.group(2)[:12]}… {comment[:40]}".strip())])
        yield _key_finding(ref, hashlib.sha256(blob).hexdigest(), evidence, private=False, encrypted=False,
                           fmt="OpenSSH public key", rule="openssh.public-key",
                           extra={"context": "known_hosts" if "known_hosts" in file.name else "authorized key" if "authorized" in file.name else "public key"})


# ------------------------------------------------------------------- PKCS#12

def _scan_pkcs12(raw: bytes, file: FileInfo) -> Iterator[Finding]:
    evidence = Evidence(file.rel, None, None, None)
    for password in _DEFAULT_PASSWORDS:
        try:
            key, cert, extra = pkcs12.load_key_and_certificates(raw, password)
        except Exception:  # noqa: BLE001
            continue
        props = {"keystore": "PKCS#12", "opened_with": "no password" if not password else "a well-known default password"}
        if cert is not None:
            finding = certificate_finding(cert, evidence, rule="pkcs12.certificate", source="PKCS#12")
            finding.properties.update(props)
            yield finding
        for c in extra or []:
            yield certificate_finding(c, evidence, rule="pkcs12.chain", source="PKCS#12")
        if key is not None:
            yield _key_finding(key_algorithm(key), _spki_digest(key.public_key()), evidence, private=True, encrypted=password is None,
                               fmt="PKCS#12", rule="pkcs12.key",
                               extra={"exposure": f"Private key protected by {props['opened_with']}" if password is not None else None})
        return
    yield Finding(kind="key", identity={"file_sha256": hashlib.sha256(raw).hexdigest()}, name="Password-protected keystore (PKCS#12)",
                  evidence=evidence, detector=DETECTOR, rule="pkcs12.locked", confidence=0.9, function="keystore",
                  properties={"format": "PKCS#12", "private": True, "encrypted": True, "note": "Contents need the keystore password"})


# ----------------------------------------------------------------------- JKS

def _scan_jks(raw: bytes, file: FileInfo) -> Iterator[Finding]:
    """Java KeyStore: certificate entries are stored unencrypted, so trusted
    certificates and certificate chains can be read without the password."""
    evidence = Evidence(file.rel, None, None, None)
    if raw[:4] not in (b"\xfe\xed\xfe\xed", b"\xce\xce\xce\xce"):
        return
    try:
        _version, count = struct.unpack(">II", raw[4:12])
        offset = 12
        private_entries = 0
        for _ in range(min(count, 5000)):
            (tag,) = struct.unpack(">I", raw[offset: offset + 4])
            offset += 4
            (alias_len,) = struct.unpack(">H", raw[offset: offset + 2])
            alias = raw[offset + 2: offset + 2 + alias_len].decode("utf-8", "replace")
            offset += 2 + alias_len + 8  # alias + timestamp
            if tag == 1:  # private key entry: encrypted key, then certificate chain
                private_entries += 1
                (key_len,) = struct.unpack(">I", raw[offset: offset + 4])
                offset += 4 + key_len
                (chain,) = struct.unpack(">I", raw[offset: offset + 4])
                offset += 4
                for _c in range(chain):
                    offset, cert = _jks_cert(raw, offset)
                    if cert is not None:
                        finding = certificate_finding(cert, evidence, rule="jks.chain", source=f"Java KeyStore ({alias})")
                        yield finding
            elif tag == 2:  # trusted certificate entry
                offset, cert = _jks_cert(raw, offset)
                if cert is not None:
                    yield certificate_finding(cert, evidence, rule="jks.trusted", source=f"Java KeyStore ({alias})")
            else:
                break
        if private_entries:
            yield Finding(kind="key", identity={"file_sha256": hashlib.sha256(raw).hexdigest()},
                          name=f"Java KeyStore with {private_entries} private key{'s' if private_entries > 1 else ''}",
                          evidence=evidence, detector=DETECTOR, rule="jks.private", confidence=0.95, function="keystore",
                          properties={"format": "JKS", "private": True, "encrypted": True, "entries": count})
    except (struct.error, ValueError):
        return


def _jks_cert(raw: bytes, offset: int) -> tuple[int, x509.Certificate | None]:
    (type_len,) = struct.unpack(">H", raw[offset: offset + 2])
    offset += 2 + type_len
    (der_len,) = struct.unpack(">I", raw[offset: offset + 4])
    der = raw[offset + 4: offset + 4 + der_len]
    offset += 4 + der_len
    try:
        return offset, x509.load_der_x509_certificate(der)
    except Exception:  # noqa: BLE001
        return offset, None


# ----------------------------------------------------------------------- JWK

def _scan_jwk(text: str, file: FileInfo) -> Iterator[Finding]:
    try:
        data = json.loads(text)
    except ValueError:
        return
    keys = data.get("keys") if isinstance(data, dict) and isinstance(data.get("keys"), list) else [data] if isinstance(data, dict) and "kty" in data else []
    for index, jwk in enumerate(keys[:500]):
        if not isinstance(jwk, dict) or "kty" not in jwk:
            continue
        kty = jwk.get("kty")
        private = any(k in jwk for k in ("d", "p", "k", "priv"))
        ref: AlgorithmRef | None = None
        if kty == "RSA" and "n" in jwk:
            n = base64.urlsafe_b64decode(jwk["n"] + "=" * (-len(jwk["n"]) % 4))
            ref = AlgorithmRef("RSA", str(int.from_bytes(n, "big").bit_length()))
        elif kty == "EC":
            ref = AlgorithmRef("ECDSA", canonical_curve(jwk.get("crv", "")) or jwk.get("crv"))
        elif kty == "OKP":
            crv = jwk.get("crv", "")
            ref = {"Ed25519": AlgorithmRef("EdDSA", "Ed25519"), "Ed448": AlgorithmRef("EdDSA", "Ed448"),
                   "X25519": AlgorithmRef("X25519"), "X448": AlgorithmRef("X448")}.get(crv)
        elif kty == "oct":
            k = jwk.get("k", "")
            ref = AlgorithmRef("HMAC" if str(jwk.get("alg", "")).startswith("HS") else "AES", str(len(k) * 6 // 8 * 8) if k else None)
        elif kty == "AKP" and str(jwk.get("alg", "")).startswith("ML-DSA"):
            ref = AlgorithmRef("ML-DSA", str(jwk["alg"]).split("-")[-1])
        material = json.dumps({k: jwk.get(k) for k in ("kty", "n", "e", "crv", "x", "y", "pub", "kid")}, sort_keys=True)
        evidence = Evidence(file.rel, None, None, [(0, f'{{"kty": "{kty}", "kid": "{jwk.get("kid", "")}", "alg": "{jwk.get("alg", "")}"}}')])
        yield _key_finding(ref, hashlib.sha256(material.encode()).hexdigest(), evidence, private=private,
                           encrypted=False, fmt="JWK", rule="jwk.key",
                           extra={"kid": jwk.get("kid"), "use": jwk.get("use"), "jwk_alg": jwk.get("alg"), "index": index})


# ----------------------------------------------------------------- dispatch

def scan(file: FileInfo, raw: bytes) -> Iterator[Finding]:
    name = file.name.lower()
    if raw[:4] in (b"\xfe\xed\xfe\xed", b"\xce\xce\xce\xce"):  # JKS / JCEKS magic
        yield from _scan_jks(raw, file)
        return
    if name.endswith((".p12", ".pfx")):
        yield from _scan_pkcs12(raw, file)
        return
    if b"-----BEGIN" in raw[:1_000_000]:
        yield from _scan_pem(raw, file)
    text = raw.decode("utf-8", "ignore") if len(raw) < 4_000_000 else ""
    if name.endswith((".jwk", ".jwks")) or name == "jwks.json" or (name.endswith(".json") and '"kty"' in text):
        yield from _scan_jwk(text, file)
        return
    if name.endswith(".ppk") or text.startswith("PuTTY-User-Key-File"):
        m = re.match(r"PuTTY-User-Key-File-\d:\s*(\S+)", text)
        enc = re.search(r"Encryption:\s*(\S+)", text)
        if m:
            from .. import names

            ref = names.ssh_algorithm(m.group(1))
            yield _key_finding(ref, None, Evidence(file.rel, 1, None, [(1, text.splitlines()[0])]), private=True,
                               encrypted=bool(enc and enc.group(1) != "none"), fmt="PuTTY private key", rule="putty.key",
                               raw_digest=hashlib.sha256(raw).hexdigest())
        return
    if re.search(r"(?:ssh-(?:rsa|dss|ed25519)|ecdsa-sha2-nistp\d+) AAAA", text[:200_000]):
        yield from _scan_ssh_public_lines(text, file)
        return
    if raw[:1] == b"\x30" and b"-----BEGIN" not in raw[:100]:
        yield from _scan_der(raw, file)

