"""The name grammar is the foundation of the inventory: pin it exhaustively."""
from __future__ import annotations

import pytest

from falcon.discovery import names
from falcon.discovery.catalogue import AlgorithmRef, assess, display_name


def ref(algorithm, parameter=None, mode=None, padding=None, hash=None):
    return AlgorithmRef(algorithm, parameter, mode, padding, hash)


@pytest.mark.parametrize("text,expected", [
    ("aes-256-gcm", ref("AES", "256", "GCM")),
    ("AES-128-CBC", ref("AES", "128", "CBC")),
    ("aes128", ref("AES", "128")),
    ("aes256-gcm@openssh.com", ref("AES", "256", "GCM")),
    ("aes128-ctr", ref("AES", "128", "CTR")),
    ("id-aes256-wrap", ref("AES", "256", "KW")),
    ("des-ede3-cbc", ref("3DES", None, "CBC")),
    ("des3", ref("3DES")),
    ("des-cbc", ref("DES", None, "CBC")),
    ("rc4", ref("RC4")),
    ("arcfour256", ref("RC4")),
    ("bf-cbc", ref("Blowfish", None, "CBC")),
    ("chacha20-poly1305", ref("ChaCha20-Poly1305", "256")),
    ("chacha20-poly1305@openssh.com", ref("ChaCha20-Poly1305", "256")),
    ("camellia-256-cbc", ref("Camellia", "256", "CBC")),
    ("sm4-cbc", ref("SM4", None, "CBC")),
])
def test_cipher_names(text, expected):
    assert names.cipher_name(text) == expected


@pytest.mark.parametrize("text,expected", [
    ("AES/GCM/NoPadding", ref("AES", None, "GCM")),
    ("AES", ref("AES", None, "ECB")),  # Java's default transformation is ECB
    ("AES_256/GCM/NoPadding", ref("AES", "256", "GCM")),
    ("DESede/CBC/PKCS5Padding", ref("3DES", None, "CBC", "PKCS7")),
    ("RSA/ECB/PKCS1Padding", ref("RSA", padding="PKCS1v15")),
    ("RSA/ECB/OAEPWithSHA-256AndMGF1Padding", ref("RSA", padding="OAEP", hash="SHA-256")),
    ("RSA/None/OAEPPadding", ref("RSA", padding="OAEP", hash="SHA-1")),
    ("PBEWithMD5AndDES", ref("PBKDF1", hash="MD5")),
    ("PBEWithHmacSHA256AndAES_256", ref("PBKDF2", hash="SHA-256")),
])
def test_jca_transformations(text, expected):
    assert names.jca_transformation(text) == expected


@pytest.mark.parametrize("text,expected", [
    ("SHA256withRSA", ref("RSA", hash="SHA-256")),
    ("SHA1withDSA", ref("DSA", hash="SHA-1")),
    ("SHA384withECDSA", ref("ECDSA", hash="SHA-384")),
    ("sha256WithRSAEncryption", ref("RSA", hash="SHA-256")),
    ("ecdsa-with-SHA384", ref("ECDSA", hash="SHA-384")),
    ("RSA-SHA256", ref("RSA", hash="SHA-256")),
    ("RSASSA-PSS", ref("RSA", padding="PSS")),
    ("SHA256withRSAandMGF1", ref("RSA", padding="PSS", hash="SHA-256")),
    ("Ed25519", ref("EdDSA", "Ed25519")),
    ("ML-DSA-65", ref("ML-DSA", "65")),
])
def test_signature_names(text, expected):
    assert names.signature_name(text) == expected


@pytest.mark.parametrize("text,expected", [
    ("sha256", "SHA-256"), ("SHA-256", "SHA-256"), ("SHA256", "SHA-256"), ("sha1", "SHA-1"), ("SHA", "SHA-1"),
    ("md5", "MD5"), ("sha3-256", "SHA3-256"), ("SHA3_512", "SHA3-512"), ("blake2b512", "BLAKE2b"),
    ("ripemd160", "RIPEMD-160"), ("sha512-256", "SHA-512/256"), ("md2", None), ("sha512-224", None),
])
def test_hash_names(text, expected):
    assert names.hash_name(text) == expected


@pytest.mark.parametrize("text,expected", [
    ("TLSv1.2", "TLS 1.2"), ("TLSv1", "TLS 1.0"), ("TLS1_2_VERSION", "TLS 1.2"), ("VersionTLS13", "TLS 1.3"),
    ("PROTOCOL_TLSv1", "TLS 1.0"), ("SSLv3", "SSL 3.0"), ("tls1.3", "TLS 1.3"), ("TLSv1_1", "TLS 1.1"),
    ("SSLv23_method", None), ("TLS_method", None),
])
def test_tls_versions(text, expected):
    assert names.tls_version(text) == expected


def test_tls13_suite():
    refs, facts = names.tls_suite("TLS_AES_256_GCM_SHA384")
    assert refs == [ref("AES", "256", "GCM"), ref("HKDF", hash="SHA-384")]
    assert facts["forward_secrecy"] is True


def test_iana_suite():
    refs, facts = names.tls_suite("TLS_ECDHE_RSA_WITH_AES_128_GCM_SHA256")
    assert refs == [ref("ECDH"), ref("RSA"), ref("AES", "128", "GCM")]
    assert facts["forward_secrecy"] is True


def test_iana_rsa_key_transport_suite():
    refs, facts = names.tls_suite("TLS_RSA_WITH_3DES_EDE_CBC_SHA")
    assert refs == [ref("RSA"), ref("3DES", None, "CBC"), ref("HMAC", hash="SHA-1")]
    assert facts["forward_secrecy"] is False


@pytest.mark.parametrize("text,algorithms,fs", [
    ("ECDHE-RSA-AES128-GCM-SHA256", ["ECDH", "RSA", "AES"], True),
    ("ECDHE-ECDSA-CHACHA20-POLY1305", ["ECDH", "ECDSA", "ChaCha20-Poly1305"], True),
    ("DHE-RSA-AES256-SHA", ["DH", "RSA", "AES", "HMAC"], True),
    ("AES128-SHA", ["RSA", "AES", "HMAC"], False),
    ("DES-CBC3-SHA", ["RSA", "3DES", "HMAC"], False),
    ("RC4-MD5", ["RSA", "RC4", "HMAC"], False),
])
def test_openssl_suites(text, algorithms, fs):
    refs, facts = names.tls_suite(text)
    assert [r.algorithm for r in refs] == algorithms
    assert facts["forward_secrecy"] is fs


def test_openssl_suite_parameters():
    refs, _ = names.tls_suite("ECDHE-RSA-AES256-GCM-SHA384")
    assert ref("AES", "256", "GCM") in refs
    refs, _ = names.tls_suite("DES-CBC3-SHA")
    assert ref("3DES", None, "CBC") in refs


def test_not_a_suite():
    assert names.tls_suite("HIGH:!aNULL:!MD5") == ([], {})


@pytest.mark.parametrize("text,expected", [
    ("X25519MLKEM768", ref("X25519MLKEM768")), ("x25519", ref("X25519")), ("prime256v1", ref("ECDH", "P-256")),
    ("secp384r1", ref("ECDH", "P-384")), ("ffdhe2048", ref("DH", "2048")), ("SecP256r1MLKEM768", ref("SecP256r1MLKEM768")),
    ("X25519Kyber768Draft00", ref("X25519Kyber768Draft00")), ("MLKEM1024", ref("ML-KEM", "1024")),
])
def test_tls_groups(text, expected):
    assert names.tls_group(text) == expected


@pytest.mark.parametrize("text,expected", [
    ("curve25519-sha256", ref("X25519")),
    ("sntrup761x25519-sha512@openssh.com", ref("sntrup761x25519")),
    ("mlkem768x25519-sha256", ref("mlkem768x25519")),
    ("diffie-hellman-group1-sha1", ref("DH", "1024", hash="SHA-1")),
    ("ssh-rsa", ref("RSA", hash="SHA-1")),
    ("rsa-sha2-512", ref("RSA", hash="SHA-512")),
    ("ssh-ed25519", ref("EdDSA", "Ed25519")),
    ("ecdsa-sha2-nistp256", ref("ECDSA", "P-256", hash="SHA-256")),
    ("aes256-gcm@openssh.com", ref("AES", "256", "GCM")),
    ("hmac-sha2-256-etm@openssh.com", ref("HMAC", hash="SHA-256")),
    ("hmac-md5", ref("HMAC", hash="MD5")),
    ("3des-cbc", ref("3DES", None, "CBC")),
])
def test_ssh_algorithms(text, expected):
    assert names.ssh_algorithm(text) == expected


def test_ipsec_classical_proposal():
    refs, pq = names.ipsec_proposal("aes256-sha256-modp2048!")
    assert refs == [ref("AES", "256", "CBC"), ref("HMAC", hash="SHA-256"), ref("DH", "2048")]
    assert pq is False


def test_ipsec_hybrid_proposal():
    refs, pq = names.ipsec_proposal("aes256gcm16-prfsha384-ecp384-ke1_mlkem768")
    assert ref("AES", "256", "GCM") in refs and ref("ECDH", "P-384") in refs and ref("ML-KEM", "768") in refs
    assert pq is True


def test_ipsec_group_numbers():
    refs, _ = names.ipsec_proposal("3des-md5-group2")
    assert refs == [ref("3DES"), ref("HMAC", hash="MD5"), ref("DH", "1024")]


@pytest.mark.parametrize("text,expected", [
    ("ML-KEM-768", ref("ML-KEM", "768")), ("MLKEM768", ref("ML-KEM", "768")), ("ml_kem_1024", ref("ML-KEM", "1024")),
    ("Kyber768", ref("Kyber", "768")), ("ML-DSA-87", ref("ML-DSA", "87")), ("Dilithium3", ref("Dilithium", "3")),
    ("SLH-DSA-SHA2-128s", ref("SLH-DSA", "SHA2-128s")), ("SPHINCS+-SHAKE-256f", ref("SPHINCS+", "SHAKE-256f")),
    ("Falcon-512", ref("Falcon", "512")), ("FN-DSA-1024", ref("FN-DSA", "1024")), ("HQC-192", ref("HQC", "192")),
    ("sntrup761", ref("NTRU Prime")), ("FrodoKEM-640-AES", ref("FrodoKEM", "640")), ("X25519MLKEM768", ref("X25519MLKEM768")),
    ("AES-256", None), ("RSA", None),
])
def test_pqc_names(text, expected):
    assert names.pqc_name(text) == expected


@pytest.mark.parametrize("text,expected", [
    ("RS256", ref("RSA", hash="SHA-256")), ("ES384", ref("ECDSA", "P-384", hash="SHA-384")),
    ("PS512", ref("RSA", padding="PSS", hash="SHA-512")), ("HS256", ref("HMAC", hash="SHA-256")),
    ("RSA-OAEP-256", ref("RSA", padding="OAEP", hash="SHA-256")), ("A256GCM", ref("AES", "256", "GCM")),
    ("none", None),
])
def test_jose(text, expected):
    assert names.jose_alg(text) == expected


@pytest.mark.parametrize("name,expected", [
    ("EVP_aes_256_gcm", ref("AES", "256", "GCM")), ("EVP_des_ede3_cbc", ref("3DES", None, "CBC")),
    ("EVP_sha1", ref("SHA-1")), ("EVP_md5", ref("MD5")), ("EVP_chacha20_poly1305", ref("ChaCha20-Poly1305", "256")),
])
def test_evp_functions(name, expected):
    assert names.evp_function(name) == expected


# ----------------------------------------------------------------- assessment

@pytest.mark.parametrize("r,quantum,classical,bits", [
    (ref("RSA", "2048"), "vulnerable", "acceptable", 112),
    (ref("RSA", "1024"), "vulnerable", "weak", 80),
    (ref("RSA", "4096"), "vulnerable", "strong", 128),
    (ref("ECDSA", "P-256"), "vulnerable", "strong", 128),
    (ref("ECDSA", "P-384"), "vulnerable", "strong", 192),
    (ref("AES", "128", "GCM"), "weakened", "strong", 128),
    (ref("AES", "256", "GCM"), "resistant", "strong", 256),
    (ref("AES", "256", "ECB"), "resistant", "weak", 256),
    (ref("3DES"), "weakened", "weak", 112),
    (ref("DES"), "weakened", "broken", 56),
    (ref("MD5"), "weakened", "broken", 0),
    (ref("SHA-1"), "weakened", "broken", 63),
    (ref("SHA-256"), "resistant", "strong", 128),
    (ref("SHA-384"), "resistant", "strong", 192),
    (ref("ML-KEM", "768"), "pqc", "strong", 192),
    (ref("ML-DSA", "44"), "pqc", "strong", 128),
    (ref("X25519MLKEM768"), "hybrid", "strong", 128),
    (ref("Kyber", "768"), "pqc", "legacy", 128),
    (ref("RSA", "2048", hash="SHA-1"), "vulnerable", "broken", 112),
])
def test_assessment(r, quantum, classical, bits):
    result = assess(r)
    assert (result.quantum, result.classical, result.classical_bits) == (quantum, classical, bits)


def test_unknown_algorithm():
    assert assess(ref("Enigma")).quantum == "unknown"


@pytest.mark.parametrize("r,text", [
    (ref("RSA", "2048"), "RSA-2048"), (ref("RSA", "3072", padding="OAEP", hash="SHA-256"), "RSA-3072-OAEP"),
    (ref("ECDSA", "P-256", hash="SHA-256"), "ECDSA P-256 with SHA-256"), (ref("AES", "256", "GCM"), "AES-256-GCM"),
    (ref("ChaCha20-Poly1305", "256"), "ChaCha20-Poly1305"), (ref("HMAC", hash="SHA-256"), "HMAC-SHA256"),
    (ref("ML-KEM", "768"), "ML-KEM-768"), (ref("EdDSA", "Ed25519"), "Ed25519"), (ref("3DES", None, "CBC"), "3DES-CBC"),
])
def test_display_names(r, text):
    assert display_name(r) == text


@pytest.mark.parametrize("text,expected", [
    ("ECDSAWithSHA256", ref("ECDSA", hash="SHA-256")), ("PureEd25519", ref("EdDSA", "Ed25519")),
    ("SHA256WithRSAPSS", ref("RSA", padding="PSS", hash="SHA-256")), ("MD5WithRSA", ref("RSA", hash="MD5")),
])
def test_go_x509_signature_constants(text, expected):
    assert names.signature_name(text) == expected
