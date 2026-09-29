"""Compiled Java: ``.class`` files and archives (JAR, WAR, EAR, AAR).

The constant pool of a class names every class it references and holds every
string literal it uses. A literal is interpreted only through the API the class
actually references, e.g. ``"AES/CBC/PKCS5Padding"`` counts as a cipher only if
the class uses ``javax/crypto/Cipher``. Library internals (a shaded Bouncy
Castle, for instance) are skipped so an application is credited with what it
uses, not with everything its libraries implement.
"""
from __future__ import annotations

import io
import re
import struct
import zipfile
from typing import Callable, Iterator

from .. import names
from ..catalogue import AlgorithmRef
from ..model import Evidence, Finding, algorithm_finding, protocol_finding
from ..walker import FileInfo
from .dependencies import bundled_jar, library_properties

DETECTOR = "java-bytecode"
MAX_CLASSES = 25_000

_LIBRARY_PACKAGES = (
    "org/bouncycastle/", "com/google/crypto/tink/", "com/nimbusds/", "io/jsonwebtoken/", "org/apache/xml/security/",
    "org/conscrypt/", "com/auth0/jwt/", "java/", "javax/", "jdk/", "sun/", "kotlin/", "scala/", "org/springframework/security/crypto/",
    "org/apache/commons/codec/", "com/google/common/hash/", "org/mindrot/",
)

_INTERPRETERS: list[tuple[str, Callable[[str], AlgorithmRef | None], str]] = [
    ("javax/crypto/Cipher", names.jca_transformation, "encrypt"),
    ("java/security/Signature", names.signature_name, "sign"),
    ("java/security/MessageDigest", lambda s: AlgorithmRef(h) if (h := names.hash_name(s)) else None, "digest"),
    ("javax/crypto/Mac", names.mac_name, "mac"),
    ("java/security/KeyPairGenerator", names.key_type_name, "keygen"),
    ("javax/crypto/KeyAgreement", names.key_type_name, "key-agree"),
    ("javax/crypto/SecretKeyFactory", names.pbe_name, "derive"),
    ("java/security/spec/ECGenParameterSpec", lambda s: names.curve_ref(s, "ECDSA"), "keygen"),
]
_PQC_CLASS = re.compile(r"(MLKEM|MLDSA|SLHDSA|Kyber|Dilithium|Falcon|SPHINCSPlus)(?:Parameters|KeyPairGenerator|Signer|KEMGenerator)")


def constant_pool(data: bytes) -> tuple[set[str], list[str]]:
    """Returns (referenced class names, string literals)."""
    if data[:4] != b"\xca\xfe\xba\xbe":
        return set(), []
    count = struct.unpack(">H", data[8:10])[0]
    offset = 10
    utf8: dict[int, str] = {}
    class_refs: list[int] = []
    string_refs: list[int] = []
    index = 1
    while index < count:
        tag = data[offset]
        offset += 1
        if tag == 1:
            length = struct.unpack(">H", data[offset: offset + 2])[0]
            utf8[index] = data[offset + 2: offset + 2 + length].decode("utf-8", "replace")
            offset += 2 + length
        elif tag in (3, 4):
            offset += 4
        elif tag in (5, 6):
            offset += 8
            index += 1  # long and double take two slots
        elif tag == 7:
            class_refs.append(struct.unpack(">H", data[offset: offset + 2])[0])
            offset += 2
        elif tag == 8:
            string_refs.append(struct.unpack(">H", data[offset: offset + 2])[0])
            offset += 2
        elif tag in (9, 10, 11, 12, 17, 18):
            offset += 4
        elif tag == 15:
            offset += 3
        elif tag in (16, 19, 20):
            offset += 2
        else:
            break  # unknown tag: stop rather than misparse
        index += 1
    return {utf8.get(i, "") for i in class_refs}, [utf8[i] for i in string_refs if i in utf8]


def _scan_class(data: bytes, evidence_path: str) -> Iterator[Finding]:
    try:
        classes, strings = constant_pool(data)
    except (struct.error, IndexError):
        return
    evidence = Evidence(evidence_path)
    emitted: set[tuple] = set()
    for class_name, interpreter, function in _INTERPRETERS:
        if class_name not in classes:
            continue
        for literal in strings:
            if len(literal) > 80:
                continue
            try:
                ref = interpreter(literal)
            except Exception:  # noqa: BLE001
                ref = None
            if ref and ref.algorithm and (ref, function) not in emitted:
                emitted.add((ref, function))
                yield algorithm_finding(ref, Evidence(evidence_path, None, None, [(0, f'"{literal}"')]), detector=DETECTOR,
                                        rule=f"bytecode.{class_name.rsplit('/', 1)[-1]}", confidence=0.88, function=function,
                                        library="JCA")
    if "javax/net/ssl/SSLContext" in classes or "javax/net/ssl/SSLSocket" in classes:
        for literal in strings:
            version = names.tls_version(literal) if len(literal) < 12 else None
            if version:
                yield protocol_finding(version, Evidence(evidence_path, None, None, [(0, f'"{literal}"')]), detector=DETECTOR,
                                       rule="bytecode.SSLContext", confidence=0.85, extra={"library": "JSSE"})
    for class_name in classes:
        m = _PQC_CLASS.search(class_name)
        if m:
            ref = names.pqc_name(m.group(1))
            if ref and (ref, "pqc") not in emitted:
                emitted.add((ref, "pqc"))
                yield algorithm_finding(ref, evidence, detector=DETECTOR, rule="bytecode.pqc-class", confidence=0.85,
                                        function="pqc", library="Bouncy Castle", extra={"class": class_name})
    if "java/security/SecureRandom" in classes and (AlgorithmRef("CSPRNG"), "random") not in emitted:
        yield algorithm_finding(AlgorithmRef("CSPRNG"), evidence, detector=DETECTOR, rule="bytecode.SecureRandom",
                                confidence=0.75, function="random", library="JCA")


def _pom_properties(text: str, evidence_path: str) -> Finding | None:
    props = dict(line.split("=", 1) for line in text.splitlines() if "=" in line and not line.startswith("#"))
    group, artifact, version = props.get("groupId", "").strip(), props.get("artifactId", "").strip(), props.get("version", "").strip()
    from .dependencies import _knowledge

    library_id = _knowledge()[1].get(("maven", f"{group}:{artifact}".lower()))
    if not library_id:
        return None
    details = library_properties(library_id, version or None)
    details.update(ecosystem="maven", package=f"{group}:{artifact}", declared_version=version, bundled=True)
    return Finding(kind="library", identity={"library": library_id, "version": version or None},
                   name=details["library"] + (f" {version}" if version else ""), evidence=Evidence(evidence_path),
                   detector=DETECTOR, rule="archive.pom-properties", confidence=0.95, function="dependency", properties=details)


def scan_archive(file: FileInfo, raw: bytes) -> Iterator[Finding]:
    try:
        archive = zipfile.ZipFile(io.BytesIO(raw))
    except zipfile.BadZipFile:
        return
    classes = 0
    with archive:
        for info in archive.infolist():
            name = info.filename
            inner = f"{file.rel}!/{name}"
            if name.endswith(".jar"):
                finding = bundled_jar(name, inner)
                if finding:
                    yield finding
                continue
            if name.startswith("META-INF/maven/") and name.endswith("pom.properties"):
                try:
                    finding = _pom_properties(archive.read(info).decode("utf-8", "replace"), inner)
                except (KeyError, zipfile.BadZipFile, RuntimeError):
                    finding = None
                if finding:
                    yield finding
                continue
            if not name.endswith(".class") or info.file_size > 2_000_000:
                continue
            path = name.removeprefix("BOOT-INF/classes/").removeprefix("WEB-INF/classes/")
            if path.startswith(_LIBRARY_PACKAGES):
                continue
            classes += 1
            if classes > MAX_CLASSES:
                break
            try:
                data = archive.read(info)
            except (KeyError, zipfile.BadZipFile, RuntimeError):
                continue
            yield from _scan_class(data, inner)


def scan_class(file: FileInfo, raw: bytes) -> Iterator[Finding]:
    yield from _scan_class(raw, file.rel)
