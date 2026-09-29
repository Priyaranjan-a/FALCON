"""Python: precise analysis on the syntax tree.

Imports and aliases are resolved, so ``from Crypto.Cipher import AES as C;
C.new(k, C.MODE_ECB)`` is recognised as AES in ECB mode, and arguments are
read where they are written (``key_size=3072``, ``ec.SECP384R1()``,
``hashes.SHA256()``, ``modes.GCM(iv)``).
"""
from __future__ import annotations

import ast
import re
from typing import Iterator

from .. import names
from ..catalogue import AlgorithmRef, canonical_curve
from ..model import Evidence, Finding, algorithm_finding, snippet
from ..walker import FileInfo

DETECTOR = "python-ast"
_SECURITY_NAMES = re.compile(r"(?i)token|secret|password|passwd|salt|nonce|otp|session|api_?key|reset|csrf|\biv\b|key")


class _Visitor(ast.NodeVisitor):
    def __init__(self, rel: str, lines: list[str]) -> None:
        self.rel = rel
        self.lines = lines
        self.imports: dict[str, str] = {}
        self.findings: list[Finding] = []
        self.consumed: set[int] = set()

    # ------------------------------------------------------------ plumbing
    def visit_Import(self, node: ast.Import) -> None:
        for alias in node.names:
            self.imports[alias.asname or alias.name.split(".")[0]] = alias.name if alias.asname else alias.name.split(".")[0]

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        if node.module:
            for alias in node.names:
                self.imports[alias.asname or alias.name] = f"{node.module}.{alias.name}"

    def qualname(self, node: ast.AST) -> str:
        if isinstance(node, ast.Name):
            return self.imports.get(node.id, node.id)
        if isinstance(node, ast.Attribute):
            return f"{self.qualname(node.value)}.{node.attr}"
        if isinstance(node, ast.Call):
            return self.qualname(node.func)
        return ""

    def emit(self, node: ast.AST, ref: AlgorithmRef | None, function: str, library: str, rule: str, confidence: float = 0.95, note: str | None = None) -> None:
        if not ref or not ref.algorithm:
            return
        line = getattr(node, "lineno", 1)
        evidence = Evidence(self.rel, line, getattr(node, "col_offset", 0) + 1, snippet(self.lines, line - 1))
        self.findings.append(algorithm_finding(ref, evidence, detector=DETECTOR, rule=rule, confidence=confidence,
                                               function=function, library=library, extra={"note": note} if note else None))

    @staticmethod
    def arg(node: ast.Call, position: int, keyword: str | None = None) -> ast.AST | None:
        if keyword:
            for kw in node.keywords:
                if kw.arg == keyword:
                    return kw.value
        return node.args[position] if position is not None and len(node.args) > position else None

    @staticmethod
    def const(node: ast.AST | None) -> object | None:
        return node.value if isinstance(node, ast.Constant) else None

    def hash_of(self, node: ast.AST | None) -> str | None:
        if node is None:
            return None
        value = self.const(node)
        if isinstance(value, str):
            return names.hash_name(value)
        return names.hash_name(self.qualname(node).rsplit(".", 1)[-1])

    def int_of(self, node: ast.AST | None) -> str | None:
        value = self.const(node)
        return str(value) if isinstance(value, int) and value >= 64 else None

    # --------------------------------------------------------------- calls
    def visit_Assign(self, node: ast.Assign) -> None:
        targets = " ".join(ast.unparse(t) for t in node.targets)
        if _SECURITY_NAMES.search(targets):
            for call in ast.walk(node.value):
                if isinstance(call, ast.Call) and re.match(r"^random\.(random|randint|choice|choices|getrandbits|randrange|sample|shuffle)$", self.qualname(call.func)):
                    self.emit(call, AlgorithmRef("Insecure PRNG"), "random", "random", "py.insecure-random", 0.8,
                              note="The random module is predictable; use secrets for security values")
                    self.consumed.add(id(call))
        self.generic_visit(node)

    def visit_Call(self, node: ast.Call) -> None:  # noqa: C901 - a dispatch table reads best inline
        if id(node) in self.consumed:
            self.generic_visit(node)
            return
        q = self.qualname(node.func)
        if q.split(".", 1)[0] not in _ROOTS and not q.endswith(".generate_key"):  # not a call into a cryptographic module
            self.generic_visit(node)
            return
        last = q.rsplit(".", 1)[-1]

        # ---- pyca/cryptography
        if q.endswith("asymmetric.rsa.generate_private_key"):
            self.emit(node, AlgorithmRef("RSA", self.int_of(self.arg(node, 1, "key_size"))), "keygen", "cryptography", "py.rsa-keygen")
        elif q.endswith("asymmetric.dsa.generate_private_key"):
            self.emit(node, AlgorithmRef("DSA", self.int_of(self.arg(node, 0, "key_size"))), "keygen", "cryptography", "py.dsa-keygen")
        elif q.endswith("asymmetric.dh.generate_parameters"):
            self.emit(node, AlgorithmRef("DH", self.int_of(self.arg(node, 1, "key_size"))), "key-agree", "cryptography", "py.dh-params")
        elif q.endswith("asymmetric.ec.generate_private_key") or q.endswith("asymmetric.ec.derive_private_key"):
            curve_node = self.arg(node, 0 if "generate" in q else 1, "curve")
            curve = canonical_curve(self.qualname(curve_node).rsplit(".", 1)[-1]) if curve_node is not None else None
            self.emit(node, AlgorithmRef("ECDSA", curve), "keygen", "cryptography", "py.ec-keygen")
        elif q.endswith("asymmetric.ec.ECDSA"):
            self.emit(node, AlgorithmRef("ECDSA", hash=self.hash_of(self.arg(node, 0, "algorithm"))), "sign", "cryptography", "py.ecdsa")
        elif q.endswith("asymmetric.ec.ECDH"):
            self.emit(node, AlgorithmRef("ECDH"), "key-agree", "cryptography", "py.ecdh")
        elif re.search(r"asymmetric\.(ed25519|ed448|x25519|x448)\.\w+PrivateKey\.generate$", q):
            kind = re.search(r"asymmetric\.(ed25519|ed448|x25519|x448)", q).group(1)
            ref = {"ed25519": AlgorithmRef("EdDSA", "Ed25519"), "ed448": AlgorithmRef("EdDSA", "Ed448"),
                   "x25519": AlgorithmRef("X25519"), "x448": AlgorithmRef("X448")}[kind]
            self.emit(node, ref, "keygen", "cryptography", f"py.{kind}")
        elif re.search(r"asymmetric\.(mlkem|mldsa)\.ML(KEM|DSA)(\d+)PrivateKey\.generate$", q):
            m = re.search(r"ML(KEM|DSA)(\d+)PrivateKey", q)
            self.emit(node, AlgorithmRef(f"ML-{m.group(1)}", m.group(2)), "keygen", "cryptography", "py.pqc")
        elif q.endswith("asymmetric.padding.OAEP"):
            self.emit(node, AlgorithmRef("RSA", padding="OAEP", hash=self.hash_of(self.arg(node, 1, "algorithm"))), "encrypt", "cryptography", "py.rsa-oaep")
        elif q.endswith("asymmetric.padding.PSS"):
            self.emit(node, AlgorithmRef("RSA", padding="PSS"), "sign", "cryptography", "py.rsa-pss")
        elif q.endswith("asymmetric.padding.PKCS1v15"):
            self.emit(node, AlgorithmRef("RSA", padding="PKCS1v15"), "sign", "cryptography", "py.rsa-pkcs1")
        elif re.search(r"primitives\.hashes\.(MD5|SHA1|SHA224|SHA256|SHA384|SHA512|SHA512_256|SHA3_\d+|BLAKE2[bs]|SM3|SHAKE\d+)$", q):
            self.emit(node, AlgorithmRef(names.hash_name(last) or last), "digest", "cryptography", "py.hash", 0.93)
        elif q.endswith("ciphers.Cipher"):
            algorithm = self.arg(node, 0, "algorithm")
            mode = self.arg(node, 1, "mode")
            if isinstance(algorithm, ast.Call):
                self.consumed.add(id(algorithm))
                name = self.qualname(algorithm.func).rsplit(".", 1)[-1]
                ref = names.cipher_name({"TripleDES": "des3", "ARC4": "rc4", "CAST5": "cast5"}.get(name, name.lower()))
                mode_name = self.qualname(mode.func).rsplit(".", 1)[-1] if isinstance(mode, ast.Call) else None
                if isinstance(mode, ast.Call):
                    self.consumed.add(id(mode))
                if ref:
                    self.emit(node, AlgorithmRef(ref.algorithm, ref.parameter, names._mode((mode_name or "").lower()) or ref.mode),
                              "encrypt", "cryptography", "py.cipher")
        elif re.search(r"ciphers\.algorithms\.(AES|AES128|AES256|TripleDES|ARC4|Blowfish|CAST5|IDEA|SEED|Camellia|ChaCha20|SM4)$", q):
            ref = names.cipher_name({"TripleDES": "des3", "ARC4": "rc4", "CAST5": "cast5"}.get(last, last.lower()))
            self.emit(node, ref, "encrypt", "cryptography", "py.cipher-algorithm", 0.9)
        elif re.search(r"ciphers\.aead\.(AESGCM|AESCCM|AESOCB3|AESSIV|AESGCMSIV|ChaCha20Poly1305)(\.generate_key)?$", q):
            m = re.search(r"aead\.(\w+?)(?:\.generate_key)?$", q)
            bits = self.int_of(self.arg(node, 0, "bit_length")) if q.endswith("generate_key") else None
            if m.group(1) == "ChaCha20Poly1305":
                ref = AlgorithmRef("ChaCha20-Poly1305", "256")
            else:
                ref = AlgorithmRef("AES", bits, {"AESGCM": "GCM", "AESCCM": "CCM", "AESOCB3": "OCB", "AESSIV": "SIV", "AESGCMSIV": "GCM-SIV"}[m.group(1)])
            self.emit(node, ref, "encrypt", "cryptography", "py.aead")
        elif q.endswith("fernet.Fernet") or q.endswith("fernet.MultiFernet"):
            self.emit(node, AlgorithmRef("AES", "128", "CBC"), "encrypt", "cryptography", "py.fernet", note="Fernet is AES-128-CBC with HMAC-SHA256")
            self.emit(node, AlgorithmRef("HMAC", hash="SHA-256"), "mac", "cryptography", "py.fernet")
        elif q.endswith("kdf.pbkdf2.PBKDF2HMAC"):
            self.emit(node, AlgorithmRef("PBKDF2", hash=self.hash_of(self.arg(node, 0, "algorithm"))), "derive", "cryptography", "py.pbkdf2")
        elif q.endswith("kdf.scrypt.Scrypt"):
            self.emit(node, AlgorithmRef("scrypt"), "derive", "cryptography", "py.scrypt")
        elif re.search(r"kdf\.hkdf\.HKDF(Expand)?$", q):
            self.emit(node, AlgorithmRef("HKDF", hash=self.hash_of(self.arg(node, 0, "algorithm"))), "derive", "cryptography", "py.hkdf")
        elif re.search(r"kdf\.argon2\.Argon2(id|i|d)$", q):
            self.emit(node, AlgorithmRef("Argon2"), "derive", "cryptography", "py.argon2")
        elif q.endswith("primitives.hmac.HMAC"):
            self.emit(node, AlgorithmRef("HMAC", hash=self.hash_of(self.arg(node, 1, "algorithm"))), "mac", "cryptography", "py.hmac")

        # ---- PyCryptodome / PyCrypto
        elif re.match(r"^Crypto(dome)?\.PublicKey\.RSA\.generate$", q):
            self.emit(node, AlgorithmRef("RSA", self.int_of(self.arg(node, 0, "bits"))), "keygen", "pycryptodome", "py.pcd-rsa")
        elif re.match(r"^Crypto(dome)?\.PublicKey\.ECC\.generate$", q):
            curve = self.const(self.arg(node, None, "curve"))
            self.emit(node, AlgorithmRef("ECDSA", canonical_curve(str(curve)) if curve else None), "keygen", "pycryptodome", "py.pcd-ecc")
        elif re.match(r"^Crypto(dome)?\.PublicKey\.DSA\.generate$", q):
            self.emit(node, AlgorithmRef("DSA", self.int_of(self.arg(node, 0, "bits"))), "keygen", "pycryptodome", "py.pcd-dsa")
        elif re.match(r"^Crypto(dome)?\.Cipher\.(AES|DES|DES3|ARC4|ARC2|Blowfish|CAST|ChaCha20|ChaCha20_Poly1305|Salsa20)\.new$", q):
            name = q.split(".")[-2]
            ref = names.cipher_name({"DES3": "des3", "ARC4": "rc4", "ARC2": "rc2", "CAST": "cast5", "ChaCha20_Poly1305": "chacha20-poly1305"}.get(name, name.lower()))
            mode_node = self.arg(node, 1, "mode")
            mode = self.qualname(mode_node).rsplit(".", 1)[-1].replace("MODE_", "").lower() if mode_node is not None else None
            if ref:
                self.emit(node, AlgorithmRef(ref.algorithm, ref.parameter, names._mode(mode or "") or ref.mode), "encrypt", "pycryptodome", "py.pcd-cipher")
        elif re.match(r"^Crypto(dome)?\.Cipher\.PKCS1_OAEP\.new$", q):
            self.emit(node, AlgorithmRef("RSA", padding="OAEP", hash=self.hash_of(self.arg(node, None, "hashAlgo")) or "SHA-1"), "encrypt", "pycryptodome", "py.pcd-oaep")
        elif re.match(r"^Crypto(dome)?\.Cipher\.PKCS1_v1_5\.new$", q):
            self.emit(node, AlgorithmRef("RSA", padding="PKCS1v15"), "encrypt", "pycryptodome", "py.pcd-pkcs1")
        elif re.match(r"^Crypto(dome)?\.Signature\.(pss|pkcs1_15|PKCS1_v1_5|PKCS1_PSS|DSS|eddsa)\.new$", q):
            scheme = q.split(".")[-2].lower()
            ref = {"pss": AlgorithmRef("RSA", padding="PSS"), "pkcs1_pss": AlgorithmRef("RSA", padding="PSS"),
                   "pkcs1_15": AlgorithmRef("RSA", padding="PKCS1v15"), "pkcs1_v1_5": AlgorithmRef("RSA", padding="PKCS1v15"),
                   "dss": AlgorithmRef("ECDSA"), "eddsa": AlgorithmRef("EdDSA", "Ed25519")}[scheme]
            self.emit(node, ref, "sign", "pycryptodome", "py.pcd-signature")
        elif re.match(r"^Crypto(dome)?\.Hash\.(MD5|MD4|SHA1|SHA|SHA224|SHA256|SHA384|SHA512|SHA3_256|SHA3_512|BLAKE2b|BLAKE2s|RIPEMD160|RIPEMD)\.new$", q):
            self.emit(node, AlgorithmRef(names.hash_name(q.split(".")[-2]) or "SHA-1"), "digest", "pycryptodome", "py.pcd-hash")
        elif re.match(r"^Crypto(dome)?\.Hash\.HMAC\.new$", q):
            self.emit(node, AlgorithmRef("HMAC", hash=self.hash_of(self.arg(node, 2, "digestmod")) or "MD5"), "mac", "pycryptodome", "py.pcd-hmac")
        elif re.match(r"^Crypto(dome)?\.Protocol\.KDF\.(PBKDF2|scrypt|HKDF|bcrypt)$", q):
            self.emit(node, AlgorithmRef({"PBKDF2": "PBKDF2", "scrypt": "scrypt", "HKDF": "HKDF", "bcrypt": "bcrypt"}[last]), "derive", "pycryptodome", "py.pcd-kdf")
        elif re.match(r"^Crypto(dome)?\.Random\.get_random_bytes$", q):
            self.emit(node, AlgorithmRef("CSPRNG"), "random", "pycryptodome", "py.pcd-random", 0.85)

        # ---- standard library
        elif re.match(r"^hashlib\.(md5|sha1|sha224|sha256|sha384|sha512|sha3_\d+|blake2b|blake2s)$", q):
            self.emit(node, AlgorithmRef(names.hash_name(last) or last), "digest", "hashlib", "py.hashlib")
        elif q == "hashlib.new":
            name = self.const(self.arg(node, 0, "name"))
            digest = names.hash_name(str(name)) if name else None
            self.emit(node, AlgorithmRef(digest) if digest else None, "digest", "hashlib", "py.hashlib-new")
        elif q == "hashlib.pbkdf2_hmac":
            self.emit(node, AlgorithmRef("PBKDF2", hash=self.hash_of(self.arg(node, 0, "hash_name"))), "derive", "hashlib", "py.pbkdf2-hmac")
        elif q == "hashlib.scrypt":
            self.emit(node, AlgorithmRef("scrypt"), "derive", "hashlib", "py.hashlib-scrypt")
        elif q in ("hmac.new", "hmac.digest", "hmac.HMAC"):
            self.emit(node, AlgorithmRef("HMAC", hash=self.hash_of(self.arg(node, 2, "digestmod"))), "mac", "hmac", "py.hmac-stdlib")
        elif re.match(r"^secrets\.(token_\w+|randbelow|choice|SystemRandom)$", q) or q == "os.urandom":
            self.emit(node, AlgorithmRef("CSPRNG"), "random", "secrets" if q.startswith("secrets") else "os", "py.csprng", 0.85)

        # ---- other libraries
        elif q in ("jwt.encode", "jwt.decode"):
            algorithm = self.const(self.arg(node, 2, "algorithm"))
            algorithms = self.arg(node, None, "algorithms")
            values = [algorithm] if algorithm else []
            if isinstance(algorithms, (ast.List, ast.Tuple)):
                values += [self.const(e) for e in algorithms.elts]
            for value in values:
                if isinstance(value, str):
                    self.emit(node, names.jose_alg(value), "sign", "PyJWT", "py.jwt")
            if q == "jwt.encode" and not values:
                self.emit(node, names.jose_alg("HS256"), "sign", "PyJWT", "py.jwt", 0.8, note="PyJWT defaults to HS256")
        elif re.match(r"^paramiko\.(RSAKey|DSSKey|ECDSAKey|Ed25519Key)\.generate$", q):
            kind = q.split(".")[-2]
            ref = {"RSAKey": AlgorithmRef("RSA", self.int_of(self.arg(node, 0, "bits"))), "DSSKey": AlgorithmRef("DSA", self.int_of(self.arg(node, 0, "bits"))),
                   "ECDSAKey": AlgorithmRef("ECDSA"), "Ed25519Key": AlgorithmRef("EdDSA", "Ed25519")}[kind]
            self.emit(node, ref, "keygen", "paramiko", "py.paramiko")
        elif last == "generate_key" and node.args and self.qualname(node.args[0]).endswith(("TYPE_RSA", "TYPE_DSA", "TYPE_EC")):
            kind = self.qualname(node.args[0]).rsplit("_", 1)[-1]
            self.emit(node, AlgorithmRef({"RSA": "RSA", "DSA": "DSA", "EC": "ECDSA"}[kind], self.int_of(self.arg(node, 1))), "keygen", "pyOpenSSL", "py.pyopenssl")
        elif q in ("nacl.signing.SigningKey.generate", "nacl.signing.SigningKey"):
            self.emit(node, AlgorithmRef("EdDSA", "Ed25519"), "sign", "PyNaCl", "py.nacl-sign")
        elif q in ("nacl.public.PrivateKey.generate", "nacl.public.Box", "nacl.public.SealedBox"):
            self.emit(node, AlgorithmRef("X25519"), "key-agree", "PyNaCl", "py.nacl-box")
            if q != "nacl.public.PrivateKey.generate":
                self.emit(node, AlgorithmRef("XSalsa20-Poly1305"), "encrypt", "PyNaCl", "py.nacl-box")
        elif q == "nacl.secret.SecretBox":
            self.emit(node, AlgorithmRef("XSalsa20-Poly1305"), "encrypt", "PyNaCl", "py.nacl-secretbox")
        elif q in ("oqs.KeyEncapsulation", "oqs.Signature"):
            name = self.const(self.arg(node, 0, "alg_name"))
            self.emit(node, names.pqc_name(str(name)) if name else None, "pqc", "liboqs-python", "py.oqs")
        elif q in ("bcrypt.hashpw", "bcrypt.gensalt", "bcrypt.kdf"):
            self.emit(node, AlgorithmRef("bcrypt"), "derive", "bcrypt", "py.bcrypt", 0.9)
        elif q in ("argon2.PasswordHasher", "argon2.low_level.hash_secret"):
            self.emit(node, AlgorithmRef("Argon2"), "derive", "argon2-cffi", "py.argon2-cffi", 0.9)
        elif re.match(r"^passlib\.hash\.(\w+)\.(hash|encrypt|using)$", q):
            scheme = q.split(".")[2]
            ref = {"bcrypt": AlgorithmRef("bcrypt"), "argon2": AlgorithmRef("Argon2"), "pbkdf2_sha256": AlgorithmRef("PBKDF2", hash="SHA-256"),
                   "pbkdf2_sha512": AlgorithmRef("PBKDF2", hash="SHA-512"), "pbkdf2_sha1": AlgorithmRef("PBKDF2", hash="SHA-1"),
                   "md5_crypt": AlgorithmRef("MD5"), "des_crypt": AlgorithmRef("DES"), "sha512_crypt": AlgorithmRef("SHA-512"),
                   "sha256_crypt": AlgorithmRef("SHA-256"), "scrypt": AlgorithmRef("scrypt")}.get(scheme)
            self.emit(node, ref, "derive", "passlib", "py.passlib")
        self.generic_visit(node)


# Every call the visitor recognises resolves to one of these modules, and an import
# (or the name itself) must appear in the text; files without any are not parsed at all.
_TRIGGER = re.compile(r"\b(?:cryptography|Crypto(?:dome)?|hashlib|hmac|secrets|urandom|jwt|paramiko|nacl|oqs|bcrypt|argon2|passlib|OpenSSL|TYPE_(?:RSA|DSA|EC))\b|\brandom\b")
_ROOTS = frozenset({"cryptography", "Crypto", "Cryptodome", "hashlib", "hmac", "secrets", "os", "jwt", "paramiko", "nacl", "oqs",
                    "bcrypt", "argon2", "passlib", "random"})


def scan(file: FileInfo, text: str) -> Iterator[Finding]:
    if not _TRIGGER.search(text):
        return
    try:
        tree = ast.parse(text)
    except (SyntaxError, ValueError, RecursionError):
        return
    visitor = _Visitor(file.rel, text.splitlines())
    visitor.visit(tree)
    yield from visitor.findings
