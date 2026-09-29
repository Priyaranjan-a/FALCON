"""Post-quantum signed attestations of a CBOM.

A snapshot is attested as an in-toto Statement (v1) whose predicate is the
CycloneDX document and whose subject is the SHA-256 of its canonical form,
wrapped in a DSSE envelope and signed with ML-DSA-65 (FIPS 204). The
signature covers the DSSE pre-authentication encoding

    PAE(type, body) = "DSSEv1" SP LEN(type) SP type SP LEN(body) SP body

so it can be checked by anyone holding the organisation's public key, with
FALCON (``falcon verify``) or with OpenSSL 3.5 or later::

    openssl pkeyutl -verify -pubin -inkey falcon-attestation.pub.pem \\
        -rawin -in pae.bin -sigfile signature.bin

The key lives in the data directory (``keys/``). Rotating it keeps the old
public key, so earlier snapshots remain verifiable.
"""
from __future__ import annotations

import base64
import hashlib
import json
import os
import threading
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import mldsa

PAYLOAD_TYPE = "application/vnd.in-toto+json"
STATEMENT_TYPE = "https://in-toto.io/Statement/v1"
PREDICATE_TYPE = "https://cyclonedx.org/bom/v1.6"
ALGORITHM = "ML-DSA-65"

_lock = threading.Lock()


class AttestationError(ValueError):
    pass


def pae(payload_type: str, body: bytes) -> bytes:
    kind = payload_type.encode("utf-8")
    return b"DSSEv1 %d %s %d %s" % (len(kind), kind, len(body), body)


def canonical(data: Any) -> bytes:
    return json.dumps(data, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def key_id(public: mldsa.MLDSA65PublicKey) -> str:
    return hashlib.sha256(public.public_bytes_raw()).hexdigest()


def public_pem(public: mldsa.MLDSA65PublicKey) -> str:
    return public.public_bytes(serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo).decode("ascii")


@dataclass
class SigningKey:
    private: mldsa.MLDSA65PrivateKey
    created_at: str

    @property
    def public(self) -> mldsa.MLDSA65PublicKey:
        return self.private.public_key()

    @property
    def id(self) -> str:
        return key_id(self.public)

    def describe(self) -> dict[str, Any]:
        raw = self.public.public_bytes_raw()
        return {
            "key_id": self.id, "algorithm": ALGORITHM, "standard": "FIPS 204", "nist_category": 3,
            "created_at": self.created_at, "public_key_bytes": len(raw), "signature_bytes": 3309,
            "public_key_pem": public_pem(self.public),
            "fingerprint": ":".join(self.id[i:i + 4] for i in range(0, 32, 4)).upper(),
        }


class KeyStore:
    """The organisation's attestation keys under ``<data>/keys``."""

    def __init__(self, directory: Path) -> None:
        self.directory = directory

    @property
    def _active(self) -> Path:
        return self.directory / "attestation-mldsa65.pem"

    @property
    def _meta(self) -> Path:
        return self.directory / "attestation.json"

    def _write_private(self, path: Path, data: bytes) -> None:
        tmp = path.with_suffix(".tmp")
        flags = os.O_WRONLY | os.O_CREAT | os.O_TRUNC | getattr(os, "O_BINARY", 0)
        fd = os.open(tmp, flags, 0o600)
        with os.fdopen(fd, "wb") as fh:
            fh.write(data)
        os.replace(tmp, path)

    def _create(self) -> SigningKey:
        private = mldsa.MLDSA65PrivateKey.generate()
        created = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
        self.directory.mkdir(parents=True, exist_ok=True)
        pem = private.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption())
        self._write_private(self._active, pem)
        key = SigningKey(private, created)
        (self.directory / f"{key.id[:16]}.pub.pem").write_text(public_pem(key.public), encoding="ascii")
        self._meta.write_text(json.dumps({"active": key.id, "created_at": created}, indent=2), encoding="utf-8")
        return key

    def signing_key(self) -> SigningKey:
        with _lock:
            if not self._active.exists():
                return self._create()
            private = serialization.load_pem_private_key(self._active.read_bytes(), password=None)
            if not isinstance(private, mldsa.MLDSA65PrivateKey):
                raise AttestationError("The attestation key is not an ML-DSA-65 key.")
            meta = json.loads(self._meta.read_text(encoding="utf-8")) if self._meta.exists() else {}
            return SigningKey(private, meta.get("created_at", ""))

    def rotate(self) -> SigningKey:
        with _lock:
            if self._active.exists():
                self._active.unlink()
            return self._create()

    def public_keys(self) -> dict[str, mldsa.MLDSA65PublicKey]:
        """Every key this installation has signed with, active and retired."""
        self.signing_key()
        keys: dict[str, mldsa.MLDSA65PublicKey] = {}
        for path in self.directory.glob("*.pub.pem"):
            try:
                public = serialization.load_pem_public_key(path.read_bytes())
            except ValueError:
                continue
            if isinstance(public, mldsa.MLDSA65PublicKey):
                keys[key_id(public)] = public
        return keys


# ------------------------------------------------------------------ envelopes

def statement(cbom: dict[str, Any], *, name: str, digest: str) -> dict[str, Any]:
    return {"_type": STATEMENT_TYPE, "subject": [{"name": name, "digest": {"sha256": digest}}],
            "predicateType": PREDICATE_TYPE, "predicate": cbom}


def sign(key: SigningKey, payload: dict[str, Any]) -> dict[str, Any]:
    body = canonical(payload)
    signature = key.private.sign(pae(PAYLOAD_TYPE, body))
    return {
        "payloadType": PAYLOAD_TYPE,
        "payload": base64.b64encode(body).decode("ascii"),
        "signatures": [{"keyid": key.id, "sig": base64.b64encode(signature).decode("ascii")}],
    }


def _load_public(value: str | bytes | mldsa.MLDSA65PublicKey) -> mldsa.MLDSA65PublicKey:
    if isinstance(value, mldsa.MLDSA65PublicKey):
        return value
    data = value.encode("ascii") if isinstance(value, str) else value
    public = serialization.load_pem_public_key(data)
    if not isinstance(public, mldsa.MLDSA65PublicKey):
        raise AttestationError("The public key is not an ML-DSA-65 key.")
    return public


def verify(envelope: dict[str, Any] | str, keys: dict[str, Any] | list[Any]) -> dict[str, Any]:
    """Checks the signature, the statement and the subject digest.

    ``keys`` maps key ids to public keys (or is a list of PEM keys). Returns a
    verdict with each check and the statement's subject; never raises for a bad
    envelope, so callers can show why it failed.
    """
    from .cbom import digest as cbom_digest

    checks: list[dict[str, Any]] = []

    def check(name: str, ok: bool, detail: str) -> bool:
        checks.append({"check": name, "ok": ok, "detail": detail})
        return ok

    result: dict[str, Any] = {"valid": False, "algorithm": ALGORITHM, "key_id": None, "subject": None, "checks": checks}
    try:
        env = json.loads(envelope) if isinstance(envelope, str) else envelope
        payload_type = env["payloadType"]
        body = base64.b64decode(env["payload"], validate=True)
        signatures = env["signatures"]
    except (ValueError, KeyError, TypeError):
        check("envelope", False, "Not a DSSE envelope.")
        return result
    if not check("envelope", payload_type == PAYLOAD_TYPE and bool(signatures), f"DSSE envelope carrying {payload_type}."):
        return result

    pool: dict[str, mldsa.MLDSA65PublicKey] = {}
    try:
        if isinstance(keys, dict):
            pool = {k: _load_public(v) for k, v in keys.items()}
        else:
            for value in keys:
                public = _load_public(value)
                pool[key_id(public)] = public
    except (ValueError, AttestationError):
        check("key", False, "The public key could not be read.")
        return result

    message = pae(payload_type, body)
    signed = False
    for sig in signatures:
        public = pool.get(sig.get("keyid", ""))
        if public is None:
            continue
        result["key_id"] = sig["keyid"]
        try:
            public.verify(base64.b64decode(sig["sig"]), message)
            signed = True
            break
        except (InvalidSignature, ValueError):
            continue
    if not check("signature", signed, f"{ALGORITHM} signature by key {result['key_id'][:16]}…" if signed
                 else "No signature verifies with a known key." if result["key_id"] else "Signed by a key this installation does not know."):
        return result

    try:
        st = json.loads(body)
        subject = st["subject"][0]
        expected = subject["digest"]["sha256"]
        predicate = st["predicate"]
    except (ValueError, KeyError, IndexError, TypeError):
        check("statement", False, "The payload is not an in-toto statement.")
        return result
    check("statement", st.get("_type") == STATEMENT_TYPE and st.get("predicateType") == PREDICATE_TYPE,
          "in-toto Statement v1 with a CycloneDX 1.6 predicate.")
    actual = cbom_digest(predicate)
    check("digest", actual == expected, "The CBOM matches the signed digest." if actual == expected else "The CBOM does not match the signed digest.")
    result.update(valid=all(c["ok"] for c in checks), subject={"name": subject.get("name"), "sha256": expected},
                  components=len(predicate.get("components", [])), timestamp=predicate.get("metadata", {}).get("timestamp"))
    result["cbom"] = predicate
    return result
