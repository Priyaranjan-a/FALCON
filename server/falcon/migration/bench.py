"""The benchmark lab: post-quantum and classical cryptography measured on this
host, through the same OpenSSL the platform uses.

Each operation runs for a short time budget and reports the median of several
batches in microseconds, with the sizes of what goes on the wire. The hybrid
X25519MLKEM768 is measured as its two halves together, as a TLS stack runs it.
"""
from __future__ import annotations

import json
import os
import platform
import statistics
import time
from datetime import datetime, timezone
from typing import Any, Callable

from cryptography.hazmat.backends.openssl import backend
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec, ed25519, mldsa, mlkem, padding, rsa, x25519

from ..settings import get_settings

BUDGET = 0.04  # seconds per batch
BATCHES = 5
MESSAGE = b"FALCON benchmark message: 64 bytes of representative payload...."


def _time(op: Callable[[], Any], budget: float = BUDGET) -> float:
    """Median microseconds per call over a few time-boxed batches."""
    op()  # warm up
    per_call = []
    for _ in range(BATCHES):
        n = 0
        start = time.perf_counter()
        while True:
            op()
            n += 1
            elapsed = time.perf_counter() - start
            if elapsed >= budget or (elapsed > budget / 4 and n >= 1 and elapsed / n > budget / 2):
                break
        per_call.append(elapsed / n * 1e6)
    return round(statistics.median(per_call), 2)


def _raw(public) -> int:
    try:
        return len(public.public_bytes_raw())
    except AttributeError:
        return len(public.public_bytes(serialization.Encoding.X962, serialization.PublicFormat.UncompressedPoint)) if hasattr(public, "curve") else len(
            public.public_bytes(serialization.Encoding.DER, serialization.PublicFormat.SubjectPublicKeyInfo))


def _kem(name: str, category: int | None, quantum: str, keygen, encaps, decaps, public_key: int, ciphertext: int) -> dict[str, Any]:
    return {"algorithm": name, "kind": "kem", "quantum": quantum, "category": category,
            "operations": {"keygen": _time(keygen), "encapsulate": _time(encaps), "decapsulate": _time(decaps)},
            "sizes": {"public_key": public_key, "ciphertext": ciphertext}}


def _sig(name: str, category: int | None, quantum: str, keygen, sign, verify, public_key: int, signature: int, budget: float = BUDGET) -> dict[str, Any]:
    return {"algorithm": name, "kind": "signature", "quantum": quantum, "category": category,
            "operations": {"keygen": _time(keygen, budget), "sign": _time(sign), "verify": _time(verify)},
            "sizes": {"public_key": public_key, "signature": signature}}


def run() -> dict[str, Any]:
    started = time.perf_counter()
    results: list[dict[str, Any]] = []

    # ------------------------------------------------------ key establishment
    for cls, name, cat in ((mlkem.MLKEM768PrivateKey, "ML-KEM-768", 3), (mlkem.MLKEM1024PrivateKey, "ML-KEM-1024", 5)):
        key = cls.generate()
        pub = key.public_key()
        _, ct = pub.encapsulate()
        results.append(_kem(name, cat, "pqc", cls.generate, pub.encapsulate, lambda k=key, c=ct: k.decapsulate(c), len(pub.public_bytes_raw()), len(ct)))

    xa, xb = x25519.X25519PrivateKey.generate(), x25519.X25519PrivateKey.generate()
    xb_pub = xb.public_key()
    results.append(_kem("X25519", None, "vulnerable", x25519.X25519PrivateKey.generate, lambda: xa.exchange(xb_pub), lambda: xb.exchange(xa.public_key()), 32, 32))

    pa, pb = ec.generate_private_key(ec.SECP256R1()), ec.generate_private_key(ec.SECP256R1())
    results.append(_kem("ECDH P-256", None, "vulnerable", lambda: ec.generate_private_key(ec.SECP256R1()),
                        lambda: pa.exchange(ec.ECDH(), pb.public_key()), lambda: pb.exchange(ec.ECDH(), pa.public_key()), 65, 65))

    hk = mlkem.MLKEM768PrivateKey.generate()
    hpub = hk.public_key()
    _, hct = hpub.encapsulate()
    def hybrid_keygen():
        mlkem.MLKEM768PrivateKey.generate()
        x25519.X25519PrivateKey.generate()
    def hybrid_encaps():
        hpub.encapsulate()
        xa.exchange(xb_pub)
    def hybrid_decaps():
        hk.decapsulate(hct)
        xb.exchange(xa.public_key())
    results.append(_kem("X25519MLKEM768", 3, "hybrid", hybrid_keygen, hybrid_encaps, hybrid_decaps, 1216, 1120))

    # ----------------------------------------------------------- signatures
    for cls, name, cat in ((mldsa.MLDSA44PrivateKey, "ML-DSA-44", 2), (mldsa.MLDSA65PrivateKey, "ML-DSA-65", 3), (mldsa.MLDSA87PrivateKey, "ML-DSA-87", 5)):
        key = cls.generate()
        pub = key.public_key()
        sig = key.sign(MESSAGE)
        results.append(_sig(name, cat, "pqc", cls.generate, lambda k=key: k.sign(MESSAGE), lambda p=pub, s=sig: p.verify(s, MESSAGE),
                            len(pub.public_bytes_raw()), len(sig)))

    ed = ed25519.Ed25519PrivateKey.generate()
    ed_sig = ed.sign(MESSAGE)
    results.append(_sig("Ed25519", None, "vulnerable", ed25519.Ed25519PrivateKey.generate, lambda: ed.sign(MESSAGE),
                        lambda: ed.public_key().verify(ed_sig, MESSAGE), 32, len(ed_sig)))

    for curve, name in ((ec.SECP256R1(), "ECDSA P-256"), (ec.SECP384R1(), "ECDSA P-384")):
        key = ec.generate_private_key(curve)
        algo = ec.ECDSA(hashes.SHA256() if curve.key_size == 256 else hashes.SHA384())
        sig = key.sign(MESSAGE, algo)
        results.append(_sig(name, None, "vulnerable", lambda c=curve: ec.generate_private_key(c), lambda k=key, a=algo: k.sign(MESSAGE, a),
                            lambda k=key, s=sig, a=algo: k.public_key().verify(s, MESSAGE, a), 1 + 2 * (curve.key_size // 8), len(sig)))

    pss = padding.PSS(mgf=padding.MGF1(hashes.SHA256()), salt_length=padding.PSS.DIGEST_LENGTH)
    for bits in (2048, 3072):
        key = rsa.generate_private_key(public_exponent=65537, key_size=bits)
        sig = key.sign(MESSAGE, pss, hashes.SHA256())
        results.append(_sig(f"RSA-{bits}", None, "vulnerable", lambda b=bits: rsa.generate_private_key(public_exponent=65537, key_size=b),
                            lambda k=key: k.sign(MESSAGE, pss, hashes.SHA256()), lambda k=key, s=sig: k.public_key().verify(s, MESSAGE, pss, hashes.SHA256()),
                            bits // 8, len(sig), budget=0.25))

    report = {
        "measured_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "duration_seconds": round(time.perf_counter() - started, 2),
        "host": {
            "machine": platform.machine(), "processor": platform.processor() or platform.machine(), "cpus": os.cpu_count(),
            "system": f"{platform.system()} {platform.release()}", "python": platform.python_version(),
            "openssl": backend.openssl_version_text(),
        },
        "method": f"Median of {BATCHES} time-boxed batches per operation, single thread, through pyca/cryptography on the OpenSSL above.",
        "results": results,
    }
    path = get_settings().data_dir / "benchmarks.json"
    path.write_text(json.dumps(report, indent=1), encoding="utf-8")
    return report


def latest() -> dict[str, Any] | None:
    path = get_settings().data_dir / "benchmarks.json"
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
