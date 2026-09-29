"""Generates the binary fixtures FALCON's tests and demo scan.

    server/.venv/Scripts/python fixtures/tools/build_fixtures.py

Everything produced here is test material: keys are freshly generated, never
used for anything, and the "binaries" are synthetic files that carry the
byte patterns real ones contain.
"""
from __future__ import annotations

import base64
import datetime as dt
import hashlib
import io
import json
import struct
import tarfile
import zipfile
from pathlib import Path

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec, ed25519, rsa
from cryptography.x509.oid import NameOID

ROOT = Path(__file__).resolve().parents[1] / "estates"
PAY = ROOT / "payments-platform"
IDN = ROOT / "identity-service"


def name(cn: str) -> x509.Name:
    return x509.Name([x509.NameAttribute(NameOID.COUNTRY_NAME, "IN"), x509.NameAttribute(NameOID.ORGANIZATION_NAME, "Example Payments Authority"),
                      x509.NameAttribute(NameOID.COMMON_NAME, cn)])


def certificate(subject: str, key, issuer_key, issuer_name: str, *, days: int, start_offset: int = -30, hash_alg=hashes.SHA256(),
                ca: bool = False, dns: list[str] | None = None) -> x509.Certificate:
    now = dt.datetime.now(dt.timezone.utc)
    builder = (x509.CertificateBuilder().subject_name(name(subject)).issuer_name(name(issuer_name)).public_key(key.public_key())
               .serial_number(x509.random_serial_number()).not_valid_before(now + dt.timedelta(days=start_offset))
               .not_valid_after(now + dt.timedelta(days=start_offset + days))
               .add_extension(x509.BasicConstraints(ca=ca, path_length=None), critical=True))
    if dns:
        builder = builder.add_extension(x509.SubjectAlternativeName([x509.DNSName(d) for d in dns]), critical=False)
    return builder.sign(issuer_key, None if isinstance(issuer_key, ed25519.Ed25519PrivateKey) else hash_alg)


def pem(cert: x509.Certificate) -> bytes:
    return cert.public_bytes(serialization.Encoding.PEM)


def write(path: Path, data: bytes | str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data.encode() if isinstance(data, str) else data)
    print("wrote", path.relative_to(ROOT.parent))


def ssh_rsa_line(key: rsa.RSAPrivateKey, comment: str) -> str:
    return key.public_key().public_bytes(serialization.Encoding.OpenSSH, serialization.PublicFormat.OpenSSH).decode() + f" {comment}\n"


def class_file(strings: list[str], classes: list[str]) -> bytes:
    """A minimal, valid Java class whose constant pool references ``classes``
    and holds ``strings`` as string literals."""
    pool: list[bytes] = []

    def utf8(text: str) -> int:
        data = text.encode()
        pool.append(b"\x01" + struct.pack(">H", len(data)) + data)
        return len(pool)

    def klass(text: str) -> int:
        index = utf8(text)
        pool.append(b"\x07" + struct.pack(">H", index))
        return len(pool)

    this_class = klass("in/gov/pay/settlement/BatchSigner")
    super_class = klass("java/lang/Object")
    for c in classes:
        klass(c)
    for s in strings:
        index = utf8(s)
        pool.append(b"\x08" + struct.pack(">H", index))
    header = b"\xca\xfe\xba\xbe" + struct.pack(">HHH", 0, 52, len(pool) + 1)
    body = struct.pack(">HHHHHHH", 0x0021, this_class, super_class, 0, 0, 0, 0)
    return header + b"".join(pool) + body


def elf_blob() -> bytes:
    header = b"\x7fELF\x02\x01\x01" + b"\x00" * 9 + b"\x03\x00\x3e\x00"  # ET_DYN, x86-64 (headers truncated: synthetic)
    banner = b"OpenSSL 1.1.1k  25 Mar 2021\x00"
    aes_sbox = bytes.fromhex("637c777bf26b6fc53001672bfed7ab76ca82c97dfa5947f0add4a2af9ca472c0")
    sha256_k = b"".join(struct.pack("<I", v) for v in (0x428A2F98, 0x71374491, 0xB5C0FBCF, 0xE9B5DBA5))
    return header + b"\x00" * 200 + banner + b"\x00" * 64 + aes_sbox + b"\x00" * 64 + sha256_k + b"\x00" * 128


def image_tar(layer_files: dict[str, bytes], tag: str) -> bytes:
    layer = io.BytesIO()
    with tarfile.open(fileobj=layer, mode="w") as tf:
        for path, data in layer_files.items():
            info = tarfile.TarInfo(path)
            info.size = len(data)
            info.mode = 0o644
            tf.addfile(info, io.BytesIO(data))
    layer_bytes = layer.getvalue()
    layer_digest = hashlib.sha256(layer_bytes).hexdigest()
    config = json.dumps({"architecture": "amd64", "os": "linux", "created": "2026-03-02T09:00:00Z",
                         "config": {"Env": ["PATH=/usr/bin", "JAVA_HOME=/opt/java"], "Labels": {"org.opencontainers.image.title": "payments-api"},
                                    "Entrypoint": ["/app/payments-api"]},
                         "rootfs": {"type": "layers", "diff_ids": [f"sha256:{layer_digest}"]}}).encode()
    config_name = hashlib.sha256(config).hexdigest() + ".json"
    manifest = json.dumps([{"Config": config_name, "RepoTags": [tag], "Layers": [f"{layer_digest}/layer.tar"]}]).encode()
    out = io.BytesIO()
    with tarfile.open(fileobj=out, mode="w") as tf:
        for path, data in ((config_name, config), (f"{layer_digest}/layer.tar", layer_bytes), ("manifest.json", manifest)):
            info = tarfile.TarInfo(path)
            info.size = len(data)
            tf.addfile(info, io.BytesIO(data))
    return out.getvalue()


def main() -> None:
    # ---------------------------------------------------- payments platform
    ca_key = rsa.generate_private_key(public_exponent=65537, key_size=4096)
    ca = certificate("Example Payments Root CA", ca_key, ca_key, "Example Payments Root CA", days=3650, start_offset=-400, ca=True)
    gw_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    gateway = certificate("payments.gov.example", gw_key, ca_key, "Example Payments Root CA", days=398, dns=["payments.gov.example", "api.payments.gov.example"])
    write(PAY / "deploy/pki/gateway.pem", pem(gateway) + pem(ca))
    legacy_key = rsa.generate_private_key(public_exponent=65537, key_size=1024)
    # Modern libraries refuse to create SHA-1 signatures, so the legacy certificate
    # carries its other faults instead: a 1024-bit key, self-signed, long expired.
    legacy = certificate("settlement-legacy.gov.example", legacy_key, legacy_key, "settlement-legacy.gov.example", days=730,
                         start_offset=-1500)
    write(PAY / "deploy/pki/legacy-settlement.crt", legacy.public_bytes(serialization.Encoding.DER))
    exposed = ec.generate_private_key(ec.SECP256R1())
    write(PAY / "deploy/keys/service.key", exposed.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8,
                                                                 serialization.NoEncryption()))
    ops1 = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    ops2 = ed25519.Ed25519PrivateKey.generate()
    ed_line = ops2.public_key().public_bytes(serialization.Encoding.OpenSSH, serialization.PublicFormat.OpenSSH).decode() + " oncall@settlement\n"
    write(PAY / "deploy/ssh/authorized_keys", ssh_rsa_line(ops1, "ops@settlement") + ed_line)
    jwk_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    n = jwk_key.public_key().public_numbers().n
    jwks = {"keys": [
        {"kty": "RSA", "kid": "receipts-2026", "use": "sig", "alg": "RS256", "e": "AQAB",
         "n": base64.urlsafe_b64encode(n.to_bytes((n.bit_length() + 7) // 8, "big")).rstrip(b"=").decode()},
        {"kty": "EC", "kid": "device-2026", "use": "sig", "alg": "ES256", "crv": "P-256",
         "x": "f83OJ3D2xF1Bg8vub9tLe1gHMzV76e8Tus9uPHvRVEU", "y": "x_FEzRu9m36HLN_tue659LNpXW6pCyStikYjKIWI5a0"},
    ]}
    write(PAY / "deploy/jwks.json", json.dumps(jwks, indent=2))

    jar = io.BytesIO()
    with zipfile.ZipFile(jar, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("META-INF/MANIFEST.MF", "Manifest-Version: 1.0\nMain-Class: in.gov.pay.settlement.Main\n")
        zf.writestr("BOOT-INF/classes/in/gov/pay/settlement/BatchSigner.class",
                    class_file(["DESede/CBC/PKCS5Padding", "SHA256withECDSA", "settlement-batch", "TLSv1"],
                               ["javax/crypto/Cipher", "java/security/Signature", "javax/net/ssl/SSLContext"]))
        zf.writestr("BOOT-INF/lib/bcprov-jdk18on-1.78.jar", b"PK\x05\x06" + b"\x00" * 18)
        zf.writestr("META-INF/maven/org.bouncycastle/bcprov-jdk18on/pom.properties",
                    "groupId=org.bouncycastle\nartifactId=bcprov-jdk18on\nversion=1.78\n")
    write(PAY / "services/settlement/settlement-batch.jar", jar.getvalue())
    write(PAY / "native/lib/libsettle.so", elf_blob())

    dpkg = ("Package: libssl1.1\nStatus: install ok installed\nVersion: 1.1.1n-0+deb11u5\n\n"
            "Package: openssh-server\nStatus: install ok installed\nVersion: 1:8.4p1-5+deb11u3\n\n"
            "Package: libgnutls30\nStatus: install ok installed\nVersion: 3.7.1-5+deb11u4\n\n")
    openssl_cnf = "[system_default_sect]\nMinProtocol = TLSv1\nCipherString = DEFAULT@SECLEVEL=1\n"
    write(ROOT.parent / "images/payments-api-3.8.1.tar", image_tar({
        "var/lib/dpkg/status": dpkg.encode(), "etc/ssl/openssl.cnf": openssl_cnf.encode(),
        "app/config/application.properties": b"server.ssl.enabled-protocols=TLSv1.1,TLSv1.2\nserver.ssl.ciphers=TLS_RSA_WITH_AES_128_CBC_SHA,TLS_ECDHE_RSA_WITH_AES_256_GCM_SHA384\njwt.signing.algorithm=RS256\n",
        "app/payments-api": elf_blob(),
    }, "registry.pay.gov.example/payments-api:3.8.1"))

    # ------------------------------------------------ identity service (PQC-ready)
    root_key = ec.generate_private_key(ec.SECP384R1())
    root = certificate("Identity Root CA P-384", root_key, root_key, "Identity Root CA P-384", days=3650, start_offset=-100,
                       hash_alg=hashes.SHA384(), ca=True)
    leaf_key = ec.generate_private_key(ec.SECP384R1())
    leaf = certificate("id.gov.example", leaf_key, root_key, "Identity Root CA P-384", days=200, hash_alg=hashes.SHA384(), dns=["id.gov.example"])
    write(IDN / "deploy/pki/id-chain.pem", pem(leaf) + pem(root))


if __name__ == "__main__":
    main()
