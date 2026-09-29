"""File enumeration and classification.

The walker decides *what* each file is (source language, configuration,
dependency manifest, certificate or key material, binary, Java archive) from
its name first and its leading bytes second, so detectors only see files they
understand. Build output, dependency caches and VCS metadata are skipped;
symbolic links are never followed.
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

SKIP_DIRS = {
    ".git", ".hg", ".svn", ".idea", ".vscode", "__pycache__", ".mypy_cache", ".pytest_cache", ".ruff_cache",
    "node_modules", "bower_components", ".venv", "venv", "env", ".tox", ".nox", "site-packages", "dist-packages",
    ".gradle", ".m2", "target", "build", "dist", "out", "obj", "bin/Debug", ".next", ".nuxt", ".turbo", "coverage",
    ".terraform", ".serverless", "vendor/bundle", "Pods", "DerivedData",
}

LANGUAGES = {
    ".py": "python", ".pyi": "python",
    ".java": "java", ".kt": "java", ".kts": "java", ".scala": "java", ".groovy": "java",
    ".js": "javascript", ".jsx": "javascript", ".mjs": "javascript", ".cjs": "javascript", ".ts": "javascript", ".tsx": "javascript",
    ".go": "go",
    ".c": "c", ".h": "c", ".cc": "c", ".cpp": "c", ".cxx": "c", ".hpp": "c", ".hh": "c", ".hxx": "c", ".m": "c", ".mm": "c",
    ".cs": "csharp", ".vb": "csharp",
    ".rs": "rust",
    ".php": "php",
    ".rb": "ruby",
    ".swift": "swift",
}

CONFIG_EXTENSIONS = {
    ".conf", ".cnf", ".cfg", ".ini", ".yaml", ".yml", ".json", ".xml", ".properties", ".toml", ".env",
    ".tf", ".tfvars", ".hcl", ".bicep", ".template", ".config", ".policy", ".security", ".plist",
}
CONFIG_NAMES = {
    "sshd_config", "ssh_config", "nginx.conf", "httpd.conf", "apache2.conf", "ssl.conf", "haproxy.cfg", "ipsec.conf",
    "swanctl.conf", "strongswan.conf", "openssl.cnf", "java.security", "dockerfile", "containerfile", "main.cf",
    "stunnel.conf", "krb5.conf", "wg0.conf", "default.conf", "postgresql.conf", "my.cnf", "redis.conf", "mongod.conf",
    "server.xml", "standalone.xml", "application.properties", "application.yml", "application.yaml",
}
MANIFESTS = {
    "requirements.txt", "pyproject.toml", "pipfile", "pipfile.lock", "poetry.lock", "setup.cfg", "setup.py",
    "package.json", "package-lock.json", "npm-shrinkwrap.json", "yarn.lock", "pnpm-lock.yaml",
    "pom.xml", "build.gradle", "build.gradle.kts", "gradle.lockfile",
    "go.mod", "go.sum", "cargo.toml", "cargo.lock", "gemfile", "gemfile.lock", "composer.json", "composer.lock",
    "packages.config", "package.swift", "package.resolved", "conanfile.txt", "vcpkg.json",
    "status", "installed",  # dpkg and apk databases (validated by path)
}
CRYPTO_MATERIAL = {
    ".pem", ".crt", ".cer", ".der", ".key", ".pub", ".p12", ".pfx", ".jks", ".keystore", ".bks", ".p7b", ".p7c",
    ".csr", ".jwk", ".jwks", ".ppk", ".asc", ".gpg", ".cert",
}
CRYPTO_MATERIAL_NAMES = {
    "id_rsa", "id_dsa", "id_ecdsa", "id_ed25519", "id_rsa.pub", "id_dsa.pub", "id_ecdsa.pub", "id_ed25519.pub",
    "authorized_keys", "known_hosts", "ssh_host_rsa_key", "ssh_host_ecdsa_key", "ssh_host_ed25519_key", "jwks.json", "cacerts",
}
JAVA_ARCHIVES = {".jar", ".war", ".ear", ".aar"}
BINARY_EXTENSIONS = {".so", ".dll", ".exe", ".dylib", ".node", ".a", ".lib", ".sys", ".bin", ".elf", ".o", ".ko"}
SKIP_EXTENSIONS = {
    ".png", ".jpg", ".jpeg", ".gif", ".webp", ".ico", ".svg", ".bmp", ".tiff", ".mp3", ".mp4", ".mov", ".avi", ".wav",
    ".woff", ".woff2", ".ttf", ".otf", ".eot", ".pdf", ".doc", ".docx", ".xls", ".xlsx", ".ppt", ".pptx", ".psd",
    ".min.js.map", ".map", ".lock.json", ".svgz", ".gz", ".bz2", ".xz", ".zst", ".7z", ".rar", ".iso", ".dmg", ".class.map",
    ".sqlite", ".db", ".parquet", ".csv", ".tsv", ".md", ".rst", ".txt.map",
}


@dataclass
class FileInfo:
    path: Path  # absolute
    rel: str  # POSIX-style path relative to the scan root
    size: int
    category: str  # source | config | manifest | material | binary | java-class | java-archive | text
    language: str | None = None

    @property
    def name(self) -> str:
        return self.path.name


def _magic(path: Path) -> bytes:
    try:
        with path.open("rb") as fh:
            return fh.read(8)
    except OSError:
        return b""


def _is_text(path: Path) -> bool:
    try:
        with path.open("rb") as fh:
            chunk = fh.read(4096)
    except OSError:
        return False
    return b"\x00" not in chunk


def classify(path: Path, rel: str, size: int) -> FileInfo | None:
    name = path.name.lower()
    suffix = path.suffix.lower()
    if suffix in SKIP_EXTENSIONS or name.endswith((".min.js.map", ".js.map")):
        return None
    rel_lower = rel.lower()
    if name in ("status",) and not rel_lower.endswith("var/lib/dpkg/status"):
        return FileInfo(path, rel, size, "text") if _is_text(path) else None
    if name in ("installed",) and not rel_lower.endswith("lib/apk/db/installed"):
        return None
    if name in MANIFESTS or name.endswith((".csproj", ".fsproj", ".vbproj")) or (name.startswith("requirements") and suffix == ".txt"):
        return FileInfo(path, rel, size, "manifest")
    if suffix in CRYPTO_MATERIAL or name in CRYPTO_MATERIAL_NAMES or name.startswith(("ssh_host_", "id_")):
        return FileInfo(path, rel, size, "material")
    if suffix in LANGUAGES:
        return FileInfo(path, rel, size, "source", LANGUAGES[suffix])
    if suffix == ".class":
        return FileInfo(path, rel, size, "java-class")
    if suffix in JAVA_ARCHIVES:
        return FileInfo(path, rel, size, "java-archive")
    if name in CONFIG_NAMES or suffix in CONFIG_EXTENSIONS or name.endswith(("_config", ".conf.d")) or name.startswith("dockerfile"):
        return FileInfo(path, rel, size, "config")
    magic = _magic(path)
    if magic.startswith(b"\x7fELF") or magic.startswith(b"MZ") or magic[:4] in (
        b"\xfe\xed\xfa\xce", b"\xfe\xed\xfa\xcf", b"\xce\xfa\xed\xfe", b"\xcf\xfa\xed\xfe", b"\xca\xfe\xba\xbe",
    ) or suffix in BINARY_EXTENSIONS:
        return FileInfo(path, rel, size, "binary")
    if magic.startswith(b"-----BEGIN") or magic.startswith(b"ssh-") or magic.startswith(b"\x30\x82"):
        return FileInfo(path, rel, size, "material")
    if _is_text(path):
        return FileInfo(path, rel, size, "text")
    return None


def walk(root: Path, *, max_file_bytes: int, max_files: int) -> tuple[list[FileInfo], dict[str, int]]:
    """Enumerate and classify files under ``root``.

    Returns the classified files and counters for what was skipped and why.
    """
    files: list[FileInfo] = []
    skipped = {"directories": 0, "too_large": 0, "unrecognised": 0, "links": 0, "limit": 0}
    # resolve() would strip a Windows extended-length prefix (\\?\) and bring back the 260-character limit.
    if not str(root).startswith("\\\\?\\"):
        root = root.resolve()
    for current, dirnames, filenames in os.walk(root, followlinks=False):
        kept = []
        for d in dirnames:
            full = os.path.join(current, d)
            if d in SKIP_DIRS or d.startswith(".") and d not in (".github", ".gitlab", ".circleci", ".ssh", ".config", ".well-known"):
                skipped["directories"] += 1
            elif os.path.islink(full):
                skipped["links"] += 1
            else:
                kept.append(d)
        dirnames[:] = sorted(kept)
        for filename in sorted(filenames):
            full = Path(current) / filename
            if full.is_symlink():
                skipped["links"] += 1
                continue
            try:
                size = full.stat().st_size
            except OSError:
                continue
            if size > max_file_bytes:
                skipped["too_large"] += 1
                continue
            rel = full.relative_to(root).as_posix()
            info = classify(full, rel, size)
            if info is None:
                skipped["unrecognised"] += 1
                continue
            if len(files) >= max_files:
                skipped["limit"] += 1
                continue
            files.append(info)
    return files, skipped


def read_text(path: Path, limit: int = 4_000_000) -> str | None:
    try:
        with path.open("rb") as fh:
            data = fh.read(limit)
    except OSError:
        return None
    for encoding in ("utf-8", "latin-1"):
        try:
            return data.decode(encoding)
        except UnicodeDecodeError:
            continue
    return None
