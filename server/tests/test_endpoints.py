"""The post-quantum TLS probe against a real TLS server running in-process."""
from __future__ import annotations

import datetime as dt
import socket
import ssl
import threading
from pathlib import Path

import pytest
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.x509.oid import NameOID

from falcon.discovery.endpoints import EndpointError, assess_endpoint, parse_endpoints, probe_hello


def _certificate(tmp_path: Path) -> tuple[Path, Path]:
    key = ec.generate_private_key(ec.SECP256R1())
    name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "probe.falcon.test")])
    now = dt.datetime.now(dt.timezone.utc)
    cert = (x509.CertificateBuilder().subject_name(name).issuer_name(name).public_key(key.public_key())
            .serial_number(x509.random_serial_number()).not_valid_before(now - dt.timedelta(days=1))
            .not_valid_after(now + dt.timedelta(days=30)).sign(key, hashes.SHA256()))
    cert_path, key_path = tmp_path / "cert.pem", tmp_path / "key.pem"
    cert_path.write_bytes(cert.public_bytes(serialization.Encoding.PEM))
    key_path.write_bytes(key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption()))
    return cert_path, key_path


@pytest.fixture
def tls_server(tmp_path):
    cert, key = _certificate(tmp_path)
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    context.load_cert_chain(cert, key)
    listener = socket.create_server(("127.0.0.1", 0))
    port = listener.getsockname()[1]
    stop = threading.Event()

    def serve() -> None:
        listener.settimeout(0.2)
        while not stop.is_set():
            try:
                conn, _ = listener.accept()
            except (TimeoutError, OSError):
                continue
            try:
                with context.wrap_socket(conn, server_side=True) as tls:
                    tls.settimeout(2)
                    tls.recv(1)
            except (ssl.SSLError, OSError, ConnectionError):
                pass

    thread = threading.Thread(target=serve, daemon=True)
    thread.start()
    yield port
    stop.set()
    thread.join(timeout=2)
    listener.close()


def test_parse_endpoints() -> None:
    assert parse_endpoints("https://portal.gov.example, 10.0.0.5:8443 [2001:db8::1]:443") == [
        ("portal.gov.example", 443), ("10.0.0.5", 8443), ("2001:db8::1", 443)]
    with pytest.raises(EndpointError):
        parse_endpoints("not a host!:99999")


def test_hand_built_client_hello_negotiates_hybrid(tls_server) -> None:
    hello = probe_hello("127.0.0.1", tls_server)
    assert hello.version == "TLS 1.3"
    if "3.5" in ssl.OPENSSL_VERSION or "4." in ssl.OPENSSL_VERSION:
        # OpenSSL 3.5+ servers prefer the hybrid group by default.
        assert hello.group == "X25519MLKEM768"


def test_classical_offer_falls_back(tls_server) -> None:
    hello = probe_hello("127.0.0.1", tls_server, offer_hybrid=False)
    assert hello.group in ("x25519", "secp256r1")


def test_full_assessment(tls_server) -> None:
    findings, summary = assess_endpoint("127.0.0.1", tls_server)
    names = {f.name for f in findings}
    assert summary["version"] == "TLS 1.3" and summary["certificates"] >= 1
    assert "probe.falcon.test" in names
    if summary["pq_probe"]["selected"] == "X25519MLKEM768":
        assert "TLS 1.3 (hybrid PQC)" in names and "X25519MLKEM768" in names
    assert not {"TLS 1.0", "TLS 1.1"} & set(summary["also_accepted"])  # modern defaults refuse them
