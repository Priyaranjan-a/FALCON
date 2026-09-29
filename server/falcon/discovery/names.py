"""The FALCON cryptographic name grammar.

Code and configuration spell the same algorithm in dozens of ways:
``"AES/GCM/NoPadding"``, ``aes-256-gcm``, ``EVP_aes_256_gcm()``, ``A256GCM``,
``aes256gcm16``, ``TLS_AES_256_GCM_SHA384``. Every function here takes one such
spelling and returns normalised :class:`AlgorithmRef` values against the
catalogue, so that all detectors feed one consistent inventory.

Each parser returns ``None`` (or an empty list) when it does not recognise its
input; callers try the grammar that fits the context they found the name in.
"""
from __future__ import annotations

import re

from .catalogue import AlgorithmRef, canonical_curve

# --------------------------------------------------------------------- hashes

_HASHES = {
    "md4": "MD4", "md5": "MD5",
    "sha": "SHA-1", "sha1": "SHA-1", "sha160": "SHA-1",
    "sha224": "SHA-224", "sha2224": "SHA-224",
    "sha256": "SHA-256", "sha2256": "SHA-256",
    "sha384": "SHA-384", "sha2384": "SHA-384",
    "sha512": "SHA-512", "sha2512": "SHA-512",
    "sha512256": "SHA-512/256",
    "sha3224": "SHA3-224", "sha3256": "SHA3-256", "sha3384": "SHA3-384", "sha3512": "SHA3-512",
    "shake128": "SHAKE128", "shake256": "SHAKE256",
    "blake2b": "BLAKE2b", "blake2b512": "BLAKE2b", "blake2s": "BLAKE2s", "blake2s256": "BLAKE2s", "blake3": "BLAKE3",
    "ripemd160": "RIPEMD-160", "rmd160": "RIPEMD-160", "sm3": "SM3", "whirlpool": "Whirlpool",
}


def _squash(text: str) -> str:
    return re.sub(r"[^a-z0-9]", "", text.lower())


def hash_name(text: str | None) -> str | None:
    if not text:
        return None
    key = _squash(text)
    if key.startswith("id"):
        key = key[2:]
    return _HASHES.get(key)


# -------------------------------------------------------------------- ciphers

_MODES = {"ecb", "cbc", "ctr", "gcm", "ccm", "ofb", "cfb", "cfb1", "cfb8", "cfb128", "xts", "ocb", "siv", "kw", "wrap", "gcmsiv", "cts"}


def _mode(token: str | None) -> str | None:
    if not token:
        return None
    t = token.lower()
    if t.startswith("cfb"):
        return "CFB"
    if t in ("wrap", "kw"):
        return "KW"
    if t == "gcmsiv":
        return "GCM-SIV"
    return t.upper() if t in _MODES else None


_CIPHER_PATTERNS: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"^(?:id-)?aes[-_ ]?(?P<bits>128|192|256)?[-_ ]?(?P<mode>gcm[-_]?siv|ecb|cbc|ctr|gcm|ccm|ofb|cfb\d*|xts|ocb|siv|wrap|kw|cts)?"), "AES"),
    (re.compile(r"^(?:des[-_]?ede3|des3|3des|tripledes|desede3?|tdea|triple[-_]?des)(?:[-_](?P<mode>cbc|ecb|cfb\d*|ofb))?"), "3DES"),
    (re.compile(r"^des(?:[-_](?P<mode>cbc|ecb|cfb\d*|ofb))?$"), "DES"),
    (re.compile(r"^(?:rc4|arcfour)(?:[-_]?(?P<bits>40|56|64|128|256))?"), "RC4"),
    (re.compile(r"^rc2(?:[-_](?P<mode>cbc|ecb|40|64))?"), "RC2"),
    (re.compile(r"^(?:bf|blowfish)(?:[-_](?P<mode>cbc|ecb|cfb\d*|ofb))?"), "Blowfish"),
    (re.compile(r"^cast5?(?:[-_](?P<mode>cbc|ecb|cfb\d*|ofb))?"), "CAST5"),
    (re.compile(r"^idea(?:[-_](?P<mode>cbc|ecb|cfb\d*|ofb))?"), "IDEA"),
    (re.compile(r"^x?chacha20[-_]?poly1305"), "ChaCha20-Poly1305"),
    (re.compile(r"^chacha20"), "ChaCha20"),
    (re.compile(r"^xsalsa20[-_]?poly1305"), "XSalsa20-Poly1305"),
    (re.compile(r"^salsa20"), "Salsa20"),
    (re.compile(r"^camellia[-_]?(?P<bits>128|192|256)?[-_]?(?P<mode>ecb|cbc|ctr|gcm|ccm|ofb|cfb\d*)?"), "Camellia"),
    (re.compile(r"^aria[-_]?(?P<bits>128|192|256)?[-_]?(?P<mode>ecb|cbc|ctr|gcm|ccm|ofb|cfb\d*)?"), "ARIA"),
    (re.compile(r"^sm4(?:[-_](?P<mode>ecb|cbc|ctr|gcm|ccm|ofb|cfb\d*))?"), "SM4"),
    (re.compile(r"^seed(?:[-_](?P<mode>cbc|ecb|cfb\d*|ofb))?"), "SEED"),
    (re.compile(r"^twofish(?P<bits>128|192|256)?"), "Twofish"),
    (re.compile(r"^serpent(?P<bits>128|192|256)?"), "Serpent"),
]


def cipher_name(text: str | None) -> AlgorithmRef | None:
    """OpenSSL, Node.js, Ruby, PHP, SSH and IPsec style cipher names."""
    if not text:
        return None
    t = text.strip().strip("\"'").lower()
    t = t.split("@", 1)[0]  # aes256-gcm@openssh.com
    for pattern, algorithm in _CIPHER_PATTERNS:
        match = pattern.match(t)
        if not match:
            continue
        groups = match.groupdict()
        bits = groups.get("bits")
        mode = _mode((groups.get("mode") or "").replace("-", "").replace("_", ""))
        if algorithm == "AES" and not bits and t.startswith("aes") and re.match(r"^aes[-_]?(?:gcm|ccm)", t):
            bits = None
        if algorithm in ("ChaCha20", "ChaCha20-Poly1305", "XSalsa20-Poly1305", "Salsa20"):
            bits = "256"
        if algorithm == "RC4":
            bits = None
        return AlgorithmRef(algorithm, bits, mode)
    return None


def evp_function(name: str) -> AlgorithmRef | None:
    """OpenSSL EVP accessor names such as ``EVP_aes_256_gcm`` or ``EVP_sha1``."""
    core = re.sub(r"^EVP_", "", name).lower()
    digest = hash_name(core)
    if digest:
        return AlgorithmRef(digest)
    return cipher_name(core.replace("_", "-"))


# ------------------------------------------------------------------------ JCA

def _pqc_or_none(text: str) -> AlgorithmRef | None:
    return pqc_name(text)


def jca_transformation(text: str) -> AlgorithmRef | None:
    """``Cipher.getInstance`` transformations, e.g. ``AES/GCM/NoPadding``."""
    parts = [p.strip() for p in text.strip().strip("\"'").split("/")]
    base = parts[0]
    mode = _mode(parts[1].lower()) if len(parts) > 1 else None
    padding_raw = parts[2] if len(parts) > 2 else ""
    b = base.lower()

    if b.startswith("pbewith"):
        return pbe_name(base)
    if b in ("rsa", "rsa/ecb") or b.startswith("rsa"):
        padding, digest = _jca_rsa_padding(padding_raw)
        return AlgorithmRef("RSA", None, None, padding, digest)
    if b in ("ecies",):
        return AlgorithmRef("ECDH")
    ref = cipher_name(re.sub(r"_(?=\d)", "-", base))
    if ref:
        bits = ref.parameter
        m = re.search(r"_(128|192|256)$", base)
        if m:
            bits = m.group(1)
        pad = None
        p = padding_raw.lower()
        if p.startswith(("pkcs5", "pkcs7")):
            pad = "PKCS7"
        # Java's bare "AES" defaults to AES/ECB/PKCS5Padding.
        if ref.algorithm in ("AES", "3DES", "DES", "Blowfish") and len(parts) == 1:
            mode = "ECB"
        return AlgorithmRef(ref.algorithm, bits, mode or ref.mode, pad)
    return _pqc_or_none(base)


def _jca_rsa_padding(padding: str) -> tuple[str | None, str | None]:
    p = padding.lower()
    if "oaep" in p:
        m = re.search(r"oaepwith(.+?)andmgf1", p)
        return "OAEP", hash_name(m.group(1)) if m else "SHA-1"
    if "pkcs1" in p:
        return "PKCS1v15", None
    if p in ("nopadding", "") and padding:
        return "None", None
    return None, None


def pbe_name(text: str) -> AlgorithmRef | None:
    """``PBEWithMD5AndDES``, ``PBEWithHmacSHA256AndAES_256``, ``PBKDF2WithHmacSHA1``."""
    t = text.lower()
    if t.startswith("pbkdf2withhmac"):
        return AlgorithmRef("PBKDF2", hash=hash_name(t.removeprefix("pbkdf2withhmac")))
    m = re.match(r"pbewith(?:hmac)?(?P<hash>[a-z0-9]+?)and(?P<cipher>.+)", t)
    if not m:
        return AlgorithmRef("PBKDF1")
    cipher = cipher_name(m.group("cipher").replace("_", "-"))
    digest = hash_name(m.group("hash"))
    if t.startswith("pbewithhmac"):
        return AlgorithmRef("PBKDF2", hash=digest)
    if cipher and cipher.algorithm in ("DES", "3DES", "RC2", "RC4"):
        return AlgorithmRef("PBKDF1", hash=digest)
    return AlgorithmRef("PBKDF2", hash=digest)


_SIG_ALGS = {"rsa": "RSA", "rsaencryption": "RSA", "rsaandmgf1": "RSA", "ecdsa": "ECDSA", "plainecdsa": "ECDSA",
             "cvcecdsa": "ECDSA", "dsa": "DSA", "sm2": "SM2", "eddsa": "EdDSA", "rsassapss": "RSA", "rsapss": "RSA"}


def signature_name(text: str) -> AlgorithmRef | None:
    """``SHA256withRSA``, ``sha256WithRSAEncryption``, ``RSA-SHA256``,
    ``ecdsa-with-SHA384``, ``RSASSA-PSS``, ``Ed25519``, ``ML-DSA-65``."""
    t = text.strip().strip("\"'")
    low = t.lower()
    pq = pqc_name(t)
    if pq:
        return pq
    if low in ("ed25519", "ed448", "eddsa", "pureeddsa", "pureed25519", "pureed448"):
        return AlgorithmRef("EdDSA", "Ed448" if "448" in low else "Ed25519")
    if low.replace("-", "").replace("_", "") in ("rsassapss", "rsapss", "pss"):
        return AlgorithmRef("RSA", padding="PSS")
    m = re.match(r"^(?P<hash>[a-z0-9-]+?)with(?P<alg>[a-z0-9-]+)$", low.replace("_", ""))
    if m:
        alg = _SIG_ALGS.get(re.sub(r"[^a-z0-9]", "", m.group("alg")))
        if alg:
            padding = "PSS" if "mgf1" in m.group("alg") or "pss" in m.group("alg") else None
            return AlgorithmRef(alg, padding=padding, hash=hash_name(m.group("hash")))
    m = re.match(r"^(?P<alg>ecdsa|dsa|rsa)[-_]?with[-_]?(?P<hash>[a-z0-9-]+)$", low)
    if m:
        return AlgorithmRef(_SIG_ALGS[m.group("alg")], hash=hash_name(m.group("hash")))
    m = re.match(r"^(?P<alg>rsa|ecdsa|dsa)[-_](?P<hash>(?:sha|md)[a-z0-9-]*)$", low)
    if m:
        return AlgorithmRef(_SIG_ALGS[m.group("alg")], hash=hash_name(m.group("hash")))
    return None


_KEYPAIR = {
    "rsa": AlgorithmRef("RSA"), "rsassapss": AlgorithmRef("RSA", padding="PSS"),
    "ec": AlgorithmRef("ECDSA"), "ecdsa": AlgorithmRef("ECDSA"), "ecdh": AlgorithmRef("ECDH"),
    "dsa": AlgorithmRef("DSA"), "dh": AlgorithmRef("DH"), "diffiehellman": AlgorithmRef("DH"),
    "x25519": AlgorithmRef("X25519"), "x448": AlgorithmRef("X448"), "xdh": AlgorithmRef("X25519"),
    "ed25519": AlgorithmRef("EdDSA", "Ed25519"), "ed448": AlgorithmRef("EdDSA", "Ed448"), "eddsa": AlgorithmRef("EdDSA", "Ed25519"),
    "elgamal": AlgorithmRef("ElGamal"), "sm2": AlgorithmRef("SM2"),
}


def key_type_name(text: str) -> AlgorithmRef | None:
    """Key-pair and key-agreement type names across ecosystems."""
    key = re.sub(r"[^a-z0-9]", "", text.lower())
    if key in _KEYPAIR:
        return _KEYPAIR[key]
    return pqc_name(text)


def mac_name(text: str) -> AlgorithmRef | None:
    """``HmacSHA256``, ``hmac-sha1``, ``HMAC-SHA3-256``, ``AESCMAC``, ``KMAC256``."""
    low = text.strip().strip("\"'").lower()
    m = re.match(r"^hmac[-_]?(.+)$", low)
    if m:
        digest = hash_name(m.group(1).split("-etm")[0].split("@")[0])
        return AlgorithmRef("HMAC", hash=digest) if digest else None
    if "cmac" in low:
        return AlgorithmRef("CMAC")
    if low.startswith("kmac"):
        return AlgorithmRef("KMAC")
    if low == "poly1305":
        return AlgorithmRef("Poly1305")
    return None


def secure_random_name(text: str) -> AlgorithmRef:
    low = text.lower()
    if "drbg" in low:
        return AlgorithmRef("DRBG")
    return AlgorithmRef("CSPRNG")


# ----------------------------------------------------------------------- JOSE

_JOSE = {
    "RS256": AlgorithmRef("RSA", hash="SHA-256"), "RS384": AlgorithmRef("RSA", hash="SHA-384"), "RS512": AlgorithmRef("RSA", hash="SHA-512"),
    "PS256": AlgorithmRef("RSA", padding="PSS", hash="SHA-256"), "PS384": AlgorithmRef("RSA", padding="PSS", hash="SHA-384"),
    "PS512": AlgorithmRef("RSA", padding="PSS", hash="SHA-512"),
    "ES256": AlgorithmRef("ECDSA", "P-256", hash="SHA-256"), "ES384": AlgorithmRef("ECDSA", "P-384", hash="SHA-384"),
    "ES512": AlgorithmRef("ECDSA", "P-521", hash="SHA-512"), "ES256K": AlgorithmRef("ECDSA", "secp256k1", hash="SHA-256"),
    "EdDSA": AlgorithmRef("EdDSA", "Ed25519"), "Ed25519": AlgorithmRef("EdDSA", "Ed25519"), "Ed448": AlgorithmRef("EdDSA", "Ed448"),
    "HS256": AlgorithmRef("HMAC", hash="SHA-256"), "HS384": AlgorithmRef("HMAC", hash="SHA-384"), "HS512": AlgorithmRef("HMAC", hash="SHA-512"),
    "RSA1_5": AlgorithmRef("RSA", padding="PKCS1v15"), "RSA-OAEP": AlgorithmRef("RSA", padding="OAEP", hash="SHA-1"),
    "RSA-OAEP-256": AlgorithmRef("RSA", padding="OAEP", hash="SHA-256"),
    "ECDH-ES": AlgorithmRef("ECDH"), "ECDH-ES+A128KW": AlgorithmRef("ECDH"), "ECDH-ES+A256KW": AlgorithmRef("ECDH"),
    "A128KW": AlgorithmRef("AES", "128", "KW"), "A192KW": AlgorithmRef("AES", "192", "KW"), "A256KW": AlgorithmRef("AES", "256", "KW"),
    "A128GCM": AlgorithmRef("AES", "128", "GCM"), "A192GCM": AlgorithmRef("AES", "192", "GCM"), "A256GCM": AlgorithmRef("AES", "256", "GCM"),
    "A128CBC-HS256": AlgorithmRef("AES", "128", "CBC"), "A256CBC-HS512": AlgorithmRef("AES", "256", "CBC"),
    "ML-DSA-44": AlgorithmRef("ML-DSA", "44"), "ML-DSA-65": AlgorithmRef("ML-DSA", "65"), "ML-DSA-87": AlgorithmRef("ML-DSA", "87"),
}


def jose_alg(text: str) -> AlgorithmRef | None:
    return _JOSE.get(text.strip().strip("\"'"))


# ------------------------------------------------------------------- versions

_VERSIONS = {
    "ssl2": "SSL 2.0", "sslv2": "SSL 2.0", "ssl3": "SSL 3.0", "sslv3": "SSL 3.0",
    "tls1": "TLS 1.0", "tlsv1": "TLS 1.0", "tls10": "TLS 1.0", "tlsv10": "TLS 1.0",
    "tls11": "TLS 1.1", "tlsv11": "TLS 1.1", "tls12": "TLS 1.2", "tlsv12": "TLS 1.2",
    "tls13": "TLS 1.3", "tlsv13": "TLS 1.3",
    "dtls1": "DTLS 1.0", "dtls10": "DTLS 1.0", "dtlsv1": "DTLS 1.0", "dtls12": "DTLS 1.2", "dtlsv12": "DTLS 1.2", "dtls13": "DTLS 1.3",
}


def tls_version(text: str) -> str | None:
    """``TLSv1.2``, ``TLS1_2_VERSION``, ``VersionTLS13``, ``PROTOCOL_TLSv1``, ``SSLv3``, ``tls1.3``."""
    key = re.sub(r"[^a-z0-9]", "", text.lower())
    for noise in ("version", "protocol", "method", "server", "client", "min", "max"):
        key = key.replace(noise, "")
    if key.endswith("0") and key[:-1] in ("tls12", "tls13", "tls11", "tlsv12", "tlsv13"):
        key = key[:-1]
    return _VERSIONS.get(key)


# ---------------------------------------------------------------- TLS groups

_GROUPS = {
    "x25519": AlgorithmRef("X25519"), "curvex25519": AlgorithmRef("X25519"), "x448": AlgorithmRef("X448"),
    "secp256r1": AlgorithmRef("ECDH", "P-256"), "prime256v1": AlgorithmRef("ECDH", "P-256"), "p256": AlgorithmRef("ECDH", "P-256"), "curvep256": AlgorithmRef("ECDH", "P-256"),
    "secp384r1": AlgorithmRef("ECDH", "P-384"), "p384": AlgorithmRef("ECDH", "P-384"), "curvep384": AlgorithmRef("ECDH", "P-384"),
    "secp521r1": AlgorithmRef("ECDH", "P-521"), "p521": AlgorithmRef("ECDH", "P-521"), "curvep521": AlgorithmRef("ECDH", "P-521"),
    "ffdhe2048": AlgorithmRef("DH", "2048"), "ffdhe3072": AlgorithmRef("DH", "3072"), "ffdhe4096": AlgorithmRef("DH", "4096"),
    "ffdhe6144": AlgorithmRef("DH", "6144"), "ffdhe8192": AlgorithmRef("DH", "8192"),
    "x25519mlkem768": AlgorithmRef("X25519MLKEM768"), "secp256r1mlkem768": AlgorithmRef("SecP256r1MLKEM768"),
    "secp384r1mlkem1024": AlgorithmRef("SecP384r1MLKEM1024"), "x25519kyber768draft00": AlgorithmRef("X25519Kyber768Draft00"),
    "x25519kyber768": AlgorithmRef("X25519Kyber768Draft00"), "p256kyber768draft00": AlgorithmRef("X25519Kyber768Draft00"),
    "mlkem512": AlgorithmRef("ML-KEM", "512"), "mlkem768": AlgorithmRef("ML-KEM", "768"), "mlkem1024": AlgorithmRef("ML-KEM", "1024"),
}

# IANA TLS supported-group code points.
GROUP_CODES = {
    0x0017: "secp256r1", 0x0018: "secp384r1", 0x0019: "secp521r1", 0x001D: "x25519", 0x001E: "x448",
    0x0100: "ffdhe2048", 0x0101: "ffdhe3072", 0x0102: "ffdhe4096", 0x0103: "ffdhe6144", 0x0104: "ffdhe8192",
    0x0200: "MLKEM512", 0x0201: "MLKEM768", 0x0202: "MLKEM1024",
    0x11EB: "SecP256r1MLKEM768", 0x11EC: "X25519MLKEM768", 0x11ED: "SecP384r1MLKEM1024", 0x6399: "X25519Kyber768Draft00",
}


def tls_group(text: str) -> AlgorithmRef | None:
    key = re.sub(r"[^a-z0-9]", "", text.lower())
    return _GROUPS.get(key.removeprefix("tls"))


# --------------------------------------------------------------- TLS suites

def _tls_enc(token: str) -> AlgorithmRef | None:
    t = token.upper().replace("-", "_")
    if t in ("NULL", ""):
        return None
    if t.startswith("3DES") or "CBC3" in t or t.startswith("DES_EDE") or t.startswith("DES192"):
        return AlgorithmRef("3DES", None, "CBC")
    if t.startswith("DES"):
        return AlgorithmRef("DES", None, "CBC")
    if t.startswith("RC4"):
        return AlgorithmRef("RC4")
    if "CHACHA20" in t:
        return AlgorithmRef("ChaCha20-Poly1305", "256")
    m = re.match(r"^(AES|CAMELLIA|ARIA|SEED|IDEA|SM4)_?(\d{3})?_?(GCM|CCM_8|CCM8|CCM|CBC)?", t)
    if m:
        algorithm = {"AES": "AES", "CAMELLIA": "Camellia", "ARIA": "ARIA", "SEED": "SEED", "IDEA": "IDEA", "SM4": "SM4"}[m.group(1)]
        mode = (m.group(3) or "CBC").replace("_8", "").replace("CCM8", "CCM")
        return AlgorithmRef(algorithm, m.group(2), mode)
    return None


def _tls_mac(token: str) -> AlgorithmRef | None:
    t = token.upper()
    digest = {"SHA": "SHA-1", "SHA1": "SHA-1", "SHA256": "SHA-256", "SHA384": "SHA-384", "MD5": "MD5"}.get(t)
    return AlgorithmRef("HMAC", hash=digest) if digest else None


_KX = {
    "ECDHE": ["ECDH"], "ECDH": ["ECDH"], "DHE": ["DH"], "EDH": ["DH"], "DH": ["DH"], "ADH": ["DH"], "AECDH": ["ECDH"],
    "RSA": ["RSA"], "PSK": [], "SRP": [], "EXP": [], "KRB5": [],
}
_AUTH = {"RSA": "RSA", "ECDSA": "ECDSA", "DSS": "DSA", "ANON": None, "PSK": None}


def tls_suite(text: str) -> tuple[list[AlgorithmRef], dict[str, object]]:
    """Parse an IANA or OpenSSL cipher-suite name into its algorithms.

    Returns ``(algorithms, facts)`` where facts note forward secrecy, export
    grade, anonymous authentication and the TLS generation of the suite.
    """
    name = text.strip().strip("\"'")
    refs: list[AlgorithmRef] = []
    facts: dict[str, object] = {}
    upper = name.upper()

    m13 = re.match(r"^TLS_(AES_128_GCM|AES_256_GCM|CHACHA20_POLY1305|AES_128_CCM_8|AES_128_CCM)_(SHA256|SHA384)$", upper)
    if m13:
        enc = _tls_enc(m13.group(1))
        facts.update(tls13=True, forward_secrecy=True)
        return ([enc] if enc else []) + [AlgorithmRef("HKDF", hash=hash_name(m13.group(2)))], facts

    m = re.match(r"^(?:TLS|SSL)_(?P<kx>.+?)_WITH_(?P<enc>.+?)(?:_(?P<mac>SHA|SHA256|SHA384|MD5))?$", upper)
    if m:
        kx_parts = m.group("kx").split("_")
        kx, auth = kx_parts[0], (kx_parts[1] if len(kx_parts) > 1 else None)
        if kx == "RSA" and auth == "EXPORT":
            auth, facts["export"] = None, True
        refs += [AlgorithmRef(a) for a in _KX.get(kx, [])]
        if auth and auth not in ("EXPORT", "ANON") and _AUTH.get(auth) and _AUTH[auth] not in [r.algorithm for r in refs]:
            refs.append(AlgorithmRef(_AUTH[auth]))
        if auth == "ANON" or kx in ("ADH", "AECDH"):
            facts["anonymous"] = True
        facts["forward_secrecy"] = kx in ("ECDHE", "DHE")
        enc = _tls_enc(m.group("enc"))
        if enc:
            refs.append(enc)
        mac = _tls_mac(m.group("mac") or "")
        if mac and enc and enc.mode not in ("GCM", "CCM") and enc.algorithm != "ChaCha20-Poly1305":
            refs.append(mac)
        return refs, facts

    # OpenSSL naming, e.g. ECDHE-RSA-AES128-GCM-SHA256, AES256-SHA, DES-CBC3-SHA.
    tokens = upper.split("-")
    if len(tokens) < 2 or not any(t.startswith(("AES", "DES", "RC4", "CHACHA", "CAMELLIA", "ARIA", "SEED", "IDEA", "NULL")) for t in tokens):
        return [], {}
    kx_tokens: list[str] = []
    while tokens and tokens[0] in ("ECDHE", "ECDH", "DHE", "EDH", "DH", "ADH", "AECDH", "RSA", "ECDSA", "DSS", "PSK", "SRP", "EXP", "KRB5"):
        kx_tokens.append(tokens.pop(0))
    if "EXP" in kx_tokens:
        facts["export"] = True
    if not kx_tokens or kx_tokens == ["EXP"]:
        kx_tokens.append("RSA")
    primary = kx_tokens[0] if kx_tokens[0] != "EXP" else kx_tokens[1]
    refs += [AlgorithmRef(a) for a in _KX.get(primary, [])]
    for token in kx_tokens[1:]:
        alg = _AUTH.get(token)
        if alg and alg not in [r.algorithm for r in refs]:
            refs.append(AlgorithmRef(alg))
    if primary == "RSA" and len(kx_tokens) == 1:
        pass  # RSA key transport doubles as authentication
    facts["forward_secrecy"] = primary in ("ECDHE", "DHE", "EDH")
    facts["anonymous"] = primary in ("ADH", "AECDH") or None
    rest = "-".join(tokens)
    mac_token = tokens[-1] if tokens and tokens[-1] in ("SHA", "SHA256", "SHA384", "MD5", "POLY1305") else None
    enc_part = rest[: -len(mac_token) - 1] if mac_token and rest.endswith(mac_token) and len(tokens) > 1 else rest
    enc = _tls_enc(re.sub(r"^(AES|CAMELLIA|ARIA)(\d{3})", r"\1_\2", enc_part).replace("-", "_"))
    if enc_part.upper().startswith("CHACHA20"):
        enc = AlgorithmRef("ChaCha20-Poly1305", "256")
    if enc:
        refs.append(enc)
    mac = _tls_mac(mac_token or "")
    if mac and enc and enc.mode not in ("GCM", "CCM") and enc.algorithm != "ChaCha20-Poly1305":
        refs.append(mac)
    facts = {k: v for k, v in facts.items() if v is not None}
    return refs, facts


# ------------------------------------------------------------------------ SSH

_SSH_KEX = {
    "curve25519-sha256": AlgorithmRef("X25519"), "curve25519-sha256@libssh.org": AlgorithmRef("X25519"),
    "curve448-sha512": AlgorithmRef("X448"),
    "ecdh-sha2-nistp256": AlgorithmRef("ECDH", "P-256"), "ecdh-sha2-nistp384": AlgorithmRef("ECDH", "P-384"),
    "ecdh-sha2-nistp521": AlgorithmRef("ECDH", "P-521"),
    "diffie-hellman-group1-sha1": AlgorithmRef("DH", "1024", hash="SHA-1"),
    "diffie-hellman-group14-sha1": AlgorithmRef("DH", "2048", hash="SHA-1"),
    "diffie-hellman-group14-sha256": AlgorithmRef("DH", "2048", hash="SHA-256"),
    "diffie-hellman-group15-sha512": AlgorithmRef("DH", "3072", hash="SHA-512"),
    "diffie-hellman-group16-sha512": AlgorithmRef("DH", "4096", hash="SHA-512"),
    "diffie-hellman-group17-sha512": AlgorithmRef("DH", "6144", hash="SHA-512"),
    "diffie-hellman-group18-sha512": AlgorithmRef("DH", "8192", hash="SHA-512"),
    "diffie-hellman-group-exchange-sha1": AlgorithmRef("DH", hash="SHA-1"),
    "diffie-hellman-group-exchange-sha256": AlgorithmRef("DH", hash="SHA-256"),
    "sntrup761x25519-sha512@openssh.com": AlgorithmRef("sntrup761x25519"), "sntrup761x25519-sha512": AlgorithmRef("sntrup761x25519"),
    "mlkem768x25519-sha256": AlgorithmRef("mlkem768x25519"),
    "mlkem768nistp256-sha256": AlgorithmRef("SecP256r1MLKEM768"), "mlkem1024nistp384-sha384": AlgorithmRef("SecP384r1MLKEM1024"),
}
_SSH_HOSTKEY = {
    "ssh-rsa": AlgorithmRef("RSA", hash="SHA-1"), "rsa-sha2-256": AlgorithmRef("RSA", hash="SHA-256"),
    "rsa-sha2-512": AlgorithmRef("RSA", hash="SHA-512"), "ssh-dss": AlgorithmRef("DSA", "1024", hash="SHA-1"),
    "ecdsa-sha2-nistp256": AlgorithmRef("ECDSA", "P-256", hash="SHA-256"), "ecdsa-sha2-nistp384": AlgorithmRef("ECDSA", "P-384", hash="SHA-384"),
    "ecdsa-sha2-nistp521": AlgorithmRef("ECDSA", "P-521", hash="SHA-512"),
    "ssh-ed25519": AlgorithmRef("EdDSA", "Ed25519"), "ssh-ed448": AlgorithmRef("EdDSA", "Ed448"),
    "sk-ssh-ed25519@openssh.com": AlgorithmRef("EdDSA", "Ed25519"), "sk-ecdsa-sha2-nistp256@openssh.com": AlgorithmRef("ECDSA", "P-256"),
}


def ssh_algorithm(text: str) -> AlgorithmRef | None:
    name = text.strip().lower()
    base = re.sub(r"-cert-v01@openssh\.com$", "", name)
    if base in _SSH_KEX:
        return _SSH_KEX[base]
    if base in _SSH_HOSTKEY:
        return _SSH_HOSTKEY[base]
    if base.startswith(("hmac-", "umac-")):
        return mac_name(base.replace("-etm@openssh.com", ""))
    return cipher_name(base)


# ---------------------------------------------------------------------- IPsec

_MODP = {"modp768": "768", "modp1024": "1024", "modp1536": "1536", "modp2048": "2048", "modp3072": "3072",
         "modp4096": "4096", "modp6144": "6144", "modp8192": "8192", "modp2048s256": "2048", "modp1024s160": "1024",
         "modp2048s224": "2048"}
_ECP = {"ecp192": "P-192", "ecp224": "P-224", "ecp256": "P-256", "ecp384": "P-384", "ecp521": "P-521",
        "ecp256bp": "brainpoolP256r1", "ecp384bp": "brainpoolP384r1", "ecp512bp": "brainpoolP512r1"}
_IKE_GROUPS = {"1": ("DH", "768"), "2": ("DH", "1024"), "5": ("DH", "1536"), "14": ("DH", "2048"), "15": ("DH", "3072"),
               "16": ("DH", "4096"), "17": ("DH", "6144"), "18": ("DH", "8192"), "19": ("ECDH", "P-256"),
               "20": ("ECDH", "P-384"), "21": ("ECDH", "P-521"), "24": ("DH", "2048"), "31": ("X25519", None), "32": ("X448", None)}


def ipsec_proposal(text: str) -> tuple[list[AlgorithmRef], bool]:
    """strongSwan-style proposals such as ``aes256gcm16-sha384-ecp384-ke1_mlkem768``.

    Returns the algorithms and whether an additional post-quantum key exchange
    (RFC 9370) is present.
    """
    refs: list[AlgorithmRef] = []
    post_quantum = False
    for raw in re.split(r"[-,;:\s]+", text.strip().strip("\"'").lower().rstrip("!")):
        token = re.sub(r"^ke\d+_", "", raw)
        if not token or token.startswith("prf"):
            continue
        if token in _MODP:
            refs.append(AlgorithmRef("DH", _MODP[token]))
        elif token in _ECP:
            refs.append(AlgorithmRef("ECDH", _ECP[token]))
        elif token in ("curve25519", "x25519"):
            refs.append(AlgorithmRef("X25519"))
        elif token in ("curve448", "x448"):
            refs.append(AlgorithmRef("X448"))
        elif (m := re.match(r"^(?:group|dh)(\d+)$", token)) and m.group(1) in _IKE_GROUPS:
            algorithm, parameter = _IKE_GROUPS[m.group(1)]
            refs.append(AlgorithmRef(algorithm, parameter))
        elif token.startswith(("mlkem", "kyber", "frodo", "hqc", "bike", "mceliece")):
            ref = pqc_name(token)
            if ref:
                refs.append(ref)
                post_quantum = True
        elif token.startswith("aes") and re.match(r"^aes(128|192|256)(gcm|ccm)\d*$", token):
            m = re.match(r"^aes(128|192|256)(gcm|ccm)", token)
            refs.append(AlgorithmRef("AES", m.group(1), m.group(2).upper()))
        elif token in ("sha1", "sha", "md5", "sha256", "sha384", "sha512", "sha2_256", "sha2_384", "sha2_512", "sha256_96"):
            refs.append(AlgorithmRef("HMAC", hash=hash_name(token.replace("_96", ""))))
        elif token in ("aesxcbc", "aescmac"):
            refs.append(AlgorithmRef("CMAC"))
        else:
            ref = cipher_name(token)
            if ref:
                refs.append(ref if ref.mode or ref.algorithm != "AES" else AlgorithmRef("AES", ref.parameter or "128", "CBC"))
    return refs, post_quantum


# ------------------------------------------------------------------------ PQC

def pqc_name(text: str | None) -> AlgorithmRef | None:
    """Post-quantum and hybrid names across libraries and standards."""
    if not text:
        return None
    raw = text.strip().strip("\"'")
    key = re.sub(r"[^a-z0-9+]", "", raw.lower())
    if not key:
        return None
    hybrid = tls_group(raw)
    if hybrid and hybrid.algorithm not in ("X25519", "X448", "ECDH", "DH"):
        return hybrid
    if key.startswith("xwing"):
        return AlgorithmRef("X-Wing")
    if key.startswith("sntrup761x25519"):
        return AlgorithmRef("sntrup761x25519")
    if key.startswith("mlkem768x25519"):
        return AlgorithmRef("mlkem768x25519")
    patterns = [
        (r"^(?:idalg)?mlkem(512|768|1024)", "ML-KEM"),
        (r"^mlkem$", "ML-KEM"),
        (r"^(?:id)?mldsa(44|65|87)", "ML-DSA"),
        (r"^mldsa$", "ML-DSA"),
        (r"^(?:id)?slhdsa(.*)$", "SLH-DSA"),
        (r"^fndsa(512|1024)", "FN-DSA"),
        (r"^kyber(512|768|1024)", "Kyber"),
        (r"^kyber$", "Kyber"),
        (r"^dilithium([235])", "Dilithium"),
        (r"^dilithium$", "Dilithium"),
        (r"^sphincs\+?(.*)$", "SPHINCS+"),
        (r"^falcon(512|1024)", "Falcon"),
        (r"^hqc(128|192|256)", "HQC"),
        (r"^hqc$", "HQC"),
        (r"^sntrup761", "NTRU Prime"),
        (r"^frodokem(\d{3,4})?", "FrodoKEM"),
        (r"^(?:classic)?mceliece(\d+)?", "Classic McEliece"),
        (r"^bike(l[135])?", "BIKE"),
        (r"^xmss(?:mt)?", "XMSS"),
        (r"^(?:lms|hsslms|hss)$", "LMS"),
    ]
    for pattern, algorithm in patterns:
        m = re.match(pattern, key)
        if m:
            parameter = m.group(1) if m.groups() else None
            if algorithm in ("SLH-DSA", "SPHINCS+"):
                parameter = _slh_parameter(raw)
            return AlgorithmRef(algorithm, parameter or None)
    return None


def _slh_parameter(raw: str) -> str | None:
    m = re.search(r"(sha2|shake)[-_]?(128|192|256)([sf])", raw.lower())
    return f"{m.group(1).upper()}-{m.group(2)}{m.group(3)}" if m else None


# -------------------------------------------------------------------- generic

def curve_ref(text: str, algorithm: str = "ECDSA") -> AlgorithmRef | None:
    curve = canonical_curve(text)
    if not curve:
        return None
    if curve == "Curve25519":
        return AlgorithmRef("X25519") if algorithm == "ECDH" else AlgorithmRef("EdDSA", "Ed25519")
    if curve == "Curve448":
        return AlgorithmRef("X448") if algorithm == "ECDH" else AlgorithmRef("EdDSA", "Ed448")
    return AlgorithmRef(algorithm, curve)


def any_name(text: str) -> AlgorithmRef | None:
    """Best-effort interpretation of an algorithm name found out of context."""
    for parser in (pqc_name, signature_name, jose_alg, mac_name, key_type_name):
        ref = parser(text)
        if ref:
            return ref
    digest = hash_name(text)
    if digest:
        return AlgorithmRef(digest)
    if "/" in text:
        return jca_transformation(text)
    return cipher_name(text)
