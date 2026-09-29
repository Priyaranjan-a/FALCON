"""Compiled binaries: executables, shared libraries and object files.

Three independent signals, so stripped and statically linked binaries are
still covered:

1. **Linkage** - crypto libraries a binary loads (ELF DT_NEEDED, PE imports,
   Mach-O load commands) and the crypto API functions it imports.
2. **Banners** - version strings compiled into libraries (``OpenSSL 1.1.1k``),
   the Go toolchain version and Go ``crypto/*`` package paths, .NET crypto types.
3. **Constant signatures** - tables every implementation of an algorithm must
   carry (AES S-box, SHA-256 round constants, Keccak round constants...).
"""
from __future__ import annotations

import re
import struct
from typing import Iterator

from ..catalogue import AlgorithmRef
from ..model import Evidence, Finding, algorithm_finding
from ..walker import FileInfo
from .dependencies import library_properties

DETECTOR = "binaries"


def _u32s(values: list[int], order: str) -> bytes:
    return b"".join(struct.pack(order + "I", v) for v in values)


def _u64s(values: list[int], order: str) -> bytes:
    return b"".join(struct.pack(order + "Q", v) for v in values)


# (algorithm reference, human label, byte patterns). Each pattern is long enough
# (>= 16 bytes) that an accidental match in unrelated data is negligible.
_SIGNATURES: list[tuple[AlgorithmRef, str, list[bytes]]] = [
    (AlgorithmRef("AES"), "AES S-box", [bytes.fromhex("637c777bf26b6fc53001672bfed7ab76")]),
    (AlgorithmRef("AES"), "AES inverse S-box", [bytes.fromhex("52096ad53036a538bf40a39e81f3d7fb")]),
    (AlgorithmRef("SHA-256"), "SHA-256 round constants", [_u32s([0x428A2F98, 0x71374491, 0xB5C0FBCF, 0xE9B5DBA5], o) for o in "<>"]),
    (AlgorithmRef("SHA-256"), "SHA-256 initial hash", [_u32s([0x6A09E667, 0xBB67AE85, 0x3C6EF372, 0xA54FF53A], o) for o in "<>"]),
    (AlgorithmRef("SHA-512"), "SHA-512 round constants", [_u64s([0x428A2F98D728AE22, 0x7137449123EF65CD], o) for o in "<>"]),
    (AlgorithmRef("SHA-1"), "SHA-1 initial hash", [_u32s([0x67452301, 0xEFCDAB89, 0x98BADCFE, 0x10325476, 0xC3D2E1F0], o) for o in "<>"]),
    (AlgorithmRef("MD5"), "MD5 sine table", [_u32s([0xD76AA478, 0xE8C7B756, 0x242070DB, 0xC1BDCEEE], o) for o in "<>"]),
    (AlgorithmRef("SHA3-256"), "Keccak round constants", [_u64s([0x0000000000000001, 0x0000000000008082, 0x800000000000808A], o) for o in "<>"]),
    (AlgorithmRef("Blowfish"), "Blowfish P-array", [_u32s([0x243F6A88, 0x85A308D3, 0x13198A2E, 0x03707344], o) for o in "<>"]),
    (AlgorithmRef("ChaCha20", "256"), "ChaCha/Salsa sigma constant", [b"expand 32-byte k"]),
    (AlgorithmRef("DES"), "DES S-box 1", [bytes([14, 4, 13, 1, 2, 15, 11, 8, 3, 10, 6, 12, 5, 9, 0, 7])]),
    (AlgorithmRef("ECDSA", "P-256"), "NIST P-256 prime", [_P256 := bytes.fromhex("ffffffff00000001000000000000000000000000ffffffffffffffffffffffff"), _P256[::-1]]),
    (AlgorithmRef("ECDSA", "secp256k1"), "secp256k1 prime", [bytes.fromhex("fffffffffffffffffffffffffffffffffffffffffffffffffffffffefffffc2f")]),
]

_LIBRARIES = [
    (re.compile(rb"(?i)^lib(?:ssl|crypto)(?:[.-]|$)|^(?:libssl|libcrypto)[-_\d.]*\.(?:so|dylib|dll)|^libeay32\.dll|^ssleay32\.dll"), "openssl"),
    (re.compile(rb"(?i)^libgnutls"), "gnutls"), (re.compile(rb"(?i)^libgcrypt"), "libgcrypt"), (re.compile(rb"(?i)^libsodium"), "libsodium"),
    (re.compile(rb"(?i)^libmbed(?:tls|crypto|x509)"), "mbedtls"), (re.compile(rb"(?i)^libwolfssl"), "wolfssl"),
    (re.compile(rb"(?i)^libnss3|^libssl3\.so"), "nss"), (re.compile(rb"(?i)^liboqs"), "liboqs"), (re.compile(rb"(?i)^libbotan"), "botan"),
]
_OS_CRYPTO = [
    (re.compile(rb"(?i)^bcrypt\.dll$"), "Windows CNG (bcrypt.dll)"), (re.compile(rb"(?i)^ncrypt\.dll$"), "Windows CNG key storage (ncrypt.dll)"),
    (re.compile(rb"(?i)^advapi32\.dll$"), None), (re.compile(rb"(?i)^crypt32\.dll$"), "Windows CryptoAPI (crypt32.dll)"),
    (re.compile(rb"(?i)^schannel\.dll$|^secur32\.dll$"), "Windows Schannel"),
    (re.compile(rb"Security\.framework"), "Apple Security framework"), (re.compile(rb"CryptoKit\.framework"), "Apple CryptoKit"),
]
_BANNERS = [
    (re.compile(rb"OpenSSL (\d+\.\d+\.\d+[a-z]?)(?:-fips)?\s+\d{1,2} [A-Z][a-z]{2} \d{4}"), "openssl"),
    (re.compile(rb"LibreSSL (\d+\.\d+\.\d+)"), "libressl"),
    (re.compile(rb"wolfSSL[ _v]*(\d+\.\d+\.\d+)"), "wolfssl"),
    (re.compile(rb"[Mm]bed ?TLS (\d+\.\d+\.\d+)"), "mbedtls"),
    (re.compile(rb"GnuTLS (\d+\.\d+\.\d+)"), "gnutls"),
    (re.compile(rb"liboqs (\d+\.\d+\.\d+)"), "liboqs"),
    (re.compile(rb"BoringSSL"), "boringssl"),
]
_SYMBOLS = [
    (re.compile(r"^(?:RSA_generate_key(?:_ex)?|RSA_public_encrypt|RSA_sign|EVP_RSA_gen)$"), AlgorithmRef("RSA"), "OpenSSL"),
    (re.compile(r"^(?:EC_KEY_generate_key|ECDSA_do_sign|ECDSA_sign|EVP_EC_gen)$"), AlgorithmRef("ECDSA"), "OpenSSL"),
    (re.compile(r"^(?:DES_ecb_encrypt|DES_ncbc_encrypt|DES_set_key)$"), AlgorithmRef("DES"), "OpenSSL"),
    (re.compile(r"^(?:DES_ede3_cbc_encrypt|EVP_des_ede3_cbc)$"), AlgorithmRef("3DES"), "OpenSSL"),
    (re.compile(r"^(?:MD5_Init|MD5|EVP_md5)$"), AlgorithmRef("MD5"), "OpenSSL"),
    (re.compile(r"^(?:SHA1_Init|SHA1|EVP_sha1)$"), AlgorithmRef("SHA-1"), "OpenSSL"),
    (re.compile(r"^(?:RC4|RC4_set_key|EVP_rc4)$"), AlgorithmRef("RC4"), "OpenSSL"),
    (re.compile(r"^EVP_aes_(128|192|256)_(gcm|cbc|ecb|ctr)$"), None, "OpenSSL"),
    (re.compile(r"^(?:TLSv1_method|TLSv1_client_method|TLSv1_server_method|SSLv3_method)$"), None, "OpenSSL"),
    (re.compile(r"^(?:CryptAcquireContext[AW]?|CryptCreateHash|CryptEncrypt|CryptGenKey)$"), None, "Windows CryptoAPI"),
    (re.compile(r"^(?:BCryptOpenAlgorithmProvider|BCryptEncrypt|BCryptSignHash|BCryptGenerateKeyPair)$"), None, "Windows CNG"),
    (re.compile(r"^OQS_(?:KEM|SIG)_new$"), None, "liboqs"),
]
_GO_PACKAGES = re.compile(rb"crypto/(rsa|ecdsa|ecdh|ed25519|des|rc4|md5|sha1|sha256|sha512|aes|mlkem|hmac|tls)\.[A-Z]")
_GO_VERSION = re.compile(rb"go1\.(\d+)(?:\.(\d+))?")
_DOTNET_TYPES = re.compile(rb"(MD5CryptoServiceProvider|SHA1Managed|SHA1CryptoServiceProvider|TripleDESCryptoServiceProvider|DESCryptoServiceProvider|RC2CryptoServiceProvider|RSACryptoServiceProvider|RijndaelManaged|MLKem|MLDsa)")
_DOTNET_MAP = {
    b"MD5CryptoServiceProvider": AlgorithmRef("MD5"), b"SHA1Managed": AlgorithmRef("SHA-1"), b"SHA1CryptoServiceProvider": AlgorithmRef("SHA-1"),
    b"TripleDESCryptoServiceProvider": AlgorithmRef("3DES"), b"DESCryptoServiceProvider": AlgorithmRef("DES"),
    b"RC2CryptoServiceProvider": AlgorithmRef("RC2"), b"RSACryptoServiceProvider": AlgorithmRef("RSA"), b"RijndaelManaged": AlgorithmRef("AES"),
    b"MLKem": AlgorithmRef("ML-KEM"), b"MLDsa": AlgorithmRef("ML-DSA"),
}
_GO_MAP = {
    b"rsa": AlgorithmRef("RSA"), b"ecdsa": AlgorithmRef("ECDSA"), b"ecdh": AlgorithmRef("ECDH"), b"ed25519": AlgorithmRef("EdDSA", "Ed25519"),
    b"des": AlgorithmRef("DES"), b"rc4": AlgorithmRef("RC4"), b"md5": AlgorithmRef("MD5"), b"sha1": AlgorithmRef("SHA-1"),
    b"sha256": AlgorithmRef("SHA-256"), b"sha512": AlgorithmRef("SHA-512"), b"aes": AlgorithmRef("AES"), b"mlkem": AlgorithmRef("ML-KEM"),
}


def _linkage(raw: bytes) -> tuple[str, list[str], list[str]]:
    """Returns (format, needed libraries, imported symbols)."""
    if raw.startswith(b"\x7fELF"):
        try:
            import io

            from elftools.elf.dynamic import DynamicSection
            from elftools.elf.elffile import ELFFile

            elf = ELFFile(io.BytesIO(raw))
            needed, symbols = [], []
            for section in elf.iter_sections():
                if isinstance(section, DynamicSection):
                    needed += [tag.needed for tag in section.iter_tags() if tag.entry.d_tag == "DT_NEEDED"]
                if section.name == ".dynsym":
                    symbols += [s.name for s in section.iter_symbols() if s.name and s["st_shndx"] == "SHN_UNDEF"]
            return "ELF", needed, symbols
        except Exception:  # noqa: BLE001 - malformed binaries fall back to strings
            return "ELF", [], []
    if raw.startswith(b"MZ"):
        try:
            import pefile

            pe = pefile.PE(data=raw, fast_load=True)
            pe.parse_data_directories(directories=[pefile.DIRECTORY_ENTRY["IMAGE_DIRECTORY_ENTRY_IMPORT"]])
            needed, symbols = [], []
            for entry in getattr(pe, "DIRECTORY_ENTRY_IMPORT", []):
                needed.append(entry.dll.decode("ascii", "ignore"))
                symbols += [imp.name.decode("ascii", "ignore") for imp in entry.imports if imp.name]
            clr = pe.OPTIONAL_HEADER.DATA_DIRECTORY[14].VirtualAddress != 0 if len(pe.OPTIONAL_HEADER.DATA_DIRECTORY) > 14 else False
            pe.close()
            return ("PE (.NET)" if clr else "PE"), needed, symbols
        except Exception:  # noqa: BLE001
            return "PE", [], []
    if raw[:4] in (b"\xfe\xed\xfa\xce", b"\xfe\xed\xfa\xcf", b"\xce\xfa\xed\xfe", b"\xcf\xfa\xed\xfe"):
        needed = [m.group(0).decode("ascii", "ignore") for m in re.finditer(rb"/[\w./+-]+\.(?:dylib|framework/[\w]+)", raw[:2_000_000])]
        return "Mach-O", needed, []
    return "binary", [], []


def scan(file: FileInfo, raw: bytes) -> Iterator[Finding]:
    fmt, needed, symbols = _linkage(raw)
    base = {"binary_format": fmt}
    reported_libraries: set[tuple[str, str | None]] = set()

    def evidence(detail: str | None = None) -> Evidence:
        return Evidence(file.rel, None, None, [(0, detail)] if detail else None)

    # 1. Linkage
    for lib in needed:
        raw_name = lib.encode()
        name = raw_name.rsplit(b"/", 1)[-1]
        for pattern, library_id in _LIBRARIES:
            if pattern.search(name):
                reported_libraries.add((library_id, None))
                props = library_properties(library_id, None)
                props.update(base, linked_as=lib, ecosystem="binary")
                yield Finding(kind="library", identity={"library": library_id, "version": None}, name=props["library"],
                              evidence=evidence(detail=f"links {lib}"), detector=DETECTOR, rule="binary.linkage", confidence=0.9,
                              function="dependency", properties=props)
        for pattern, label in _OS_CRYPTO:
            if label and pattern.search(name):
                yield Finding(kind="library", identity={"library": "os-crypto", "version": label}, name=label,
                              evidence=evidence(detail=f"links {lib}"), detector=DETECTOR, rule="binary.os-crypto", confidence=0.85,
                              function="dependency", properties={"library": label, "category": "platform", **base,
                                                                 "pqc": {"status": "unknown", "capable": None}})
    seen_symbols: set[str] = set()
    for symbol in symbols:
        for pattern, ref, library in _SYMBOLS:
            m = pattern.match(symbol)
            if not m or symbol in seen_symbols:
                continue
            seen_symbols.add(symbol)
            target = ref
            if target is None and symbol.startswith("EVP_aes_"):
                target = AlgorithmRef("AES", m.group(1), m.group(2).upper())
            if target is not None:
                yield algorithm_finding(target, evidence(detail=f"imports {symbol}"), detector=DETECTOR, rule="binary.import",
                                        confidence=0.85, function="linked-api", library=library, extra={**base, "symbol": symbol})

    # 2. Banners
    window = raw if len(raw) <= 64_000_000 else raw[:64_000_000]
    for pattern, library_id in _BANNERS:
        m = pattern.search(window)
        if m:
            version = m.group(1).decode() if m.groups() else None
            if (library_id, version) in reported_libraries:
                continue
            reported_libraries.add((library_id, version))
            props = library_properties(library_id, version)
            props.update(base, banner=m.group(0).decode("latin-1"), ecosystem="binary", statically_linked=True)
            yield Finding(kind="library", identity={"library": library_id, "version": version},
                          name=props["library"] + (f" {version}" if version else ""), evidence=evidence(detail=m.group(0).decode("latin-1")),
                          detector=DETECTOR, rule="binary.banner", confidence=0.95, function="dependency", properties=props)
    go = _GO_VERSION.search(window) if b"runtime.goexit" in window or b"go.buildid" in window or b"Go build" in window else None
    if go:
        version = f"1.{int(go.group(1))}" + (f".{int(go.group(2))}" if go.group(2) else "")
        props = library_properties("go-stdlib", version)
        props.update(base, ecosystem="go-toolchain")
        yield Finding(kind="library", identity={"library": "go-stdlib", "version": version}, name=f"Go standard library crypto {version}",
                      evidence=evidence(detail=f"built with go{version}"), detector=DETECTOR, rule="binary.go-version", confidence=0.9,
                      function="dependency", properties=props)
        for package in sorted(set(_GO_PACKAGES.findall(window))):
            ref = _GO_MAP.get(package)
            if ref:
                yield algorithm_finding(ref, evidence(detail=f"uses crypto/{package.decode()}"), detector=DETECTOR, rule="binary.go-package",
                                        confidence=0.75, function="linked-api", library=f"crypto/{package.decode()}", extra=base)
    if fmt == "PE (.NET)":
        for type_name in sorted(set(_DOTNET_TYPES.findall(window))):
            ref = _DOTNET_MAP.get(type_name)
            if ref:
                yield algorithm_finding(ref, evidence(detail=f"references {type_name.decode()}"), detector=DETECTOR, rule="binary.dotnet-type",
                                        confidence=0.8, function="linked-api", library=".NET", extra=base)

    # 3. Constant signatures
    for ref, label, patterns in _SIGNATURES:
        for pattern in patterns:
            offset = window.find(pattern)
            if offset >= 0:
                yield algorithm_finding(ref, evidence(detail=f"{label} at offset 0x{offset:x}"), detector=DETECTOR,
                                        rule="binary.constant", confidence=0.8, function="implementation",
                                        extra={**base, "signature": label, "offset": offset})
                break
