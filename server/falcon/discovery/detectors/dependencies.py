"""Cryptographic libraries from dependency manifests, lockfiles, OS package
databases and bundled Java archives.

Each ecosystem's files are parsed into (package, version, line) and matched
against ``knowledge/libraries.json``, which records what the library is, its
post-quantum capability and, for OpenSSL, the end-of-life date of its branch.
"""
from __future__ import annotations

import json
import re
import tomllib
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from datetime import date
from functools import lru_cache
from pathlib import Path
from typing import Any, Iterator

from ..model import Evidence, Finding, snippet
from ..walker import FileInfo

DETECTOR = "dependencies"
_KB = Path(__file__).resolve().parents[2] / "knowledge" / "libraries.json"


@dataclass
class Package:
    ecosystem: str
    name: str
    version: str | None
    line: int | None


@lru_cache
def _knowledge() -> tuple[dict[str, Any], dict[tuple[str, str], str]]:
    data = json.loads(_KB.read_text("utf-8"))
    index: dict[tuple[str, str], str] = {}
    for library_id, entry in data["libraries"].items():
        for ecosystem, names in entry.get("packages", {}).items():
            for name in names:
                index[(ecosystem, name.lower())] = library_id
    return data, index


def knowledge_version() -> str:
    return _knowledge()[0]["version"]


def _clean_version(version: str | None) -> str | None:
    if not version:
        return None
    v = version.strip().strip("\"'")
    v = re.sub(r"^[\^~>=<! ]+", "", v).split(",")[0].strip()
    v = re.sub(r"^\d+:", "", v)  # Debian epoch
    if re.match(r"^\d", v) is None:
        return None
    return v[:64]


def _upstream(version: str) -> str:
    """Strip packaging epochs and revisions: 1:8.4p1-5 -> 8.4p1, 3.0.2-0ubuntu1.10 -> 3.0.2, 1.1.1k-r0 -> 1.1.1k."""
    return re.split(r"[-+~]", re.sub(r"^\d+:", "", version), maxsplit=1)[0]


def _version_tuple(version: str) -> tuple:
    parts = re.findall(r"\d+|[a-z]+", version.lower())
    return tuple(int(p) if p.isdigit() else p for p in parts)


def _at_least(version: str, minimum: str) -> bool:
    try:
        a, b = _version_tuple(version), _version_tuple(minimum)
        return tuple(x for x in a if isinstance(x, int))[: len(b)] >= tuple(x for x in b if isinstance(x, int))
    except TypeError:
        return False


def library_properties(library_id: str, version: str | None) -> dict[str, Any]:
    entry = _knowledge()[0]["libraries"][library_id]
    props: dict[str, Any] = {"library": entry["name"], "category": entry.get("category")}
    pqc = entry.get("pqc", {"status": "unknown"})
    capable: bool | None
    if pqc.get("status") == "native" and pqc.get("since"):
        capable = _at_least(_upstream(version), pqc["since"]) if version else None
    elif pqc.get("status") == "native":
        capable = True
    elif pqc.get("status") == "none":
        capable = False
    else:
        capable = None
    props["pqc"] = {**pqc, "capable": capable}
    if entry.get("status"):
        props["status"] = entry["status"]
    if entry.get("note"):
        props["note"] = entry["note"]
    eol = entry.get("eol")
    if eol and version:
        upstream = _upstream(version)
        branch = next((b for b in sorted(eol, key=len, reverse=True) if upstream.startswith(b)), None)
        if branch:
            eol_date = date.fromisoformat(eol[branch])
            props["eol"] = {"branch": branch, "date": eol[branch], "reached": eol_date <= date.today()}
    return props


def _finding(library_id: str, package: Package, file: FileInfo, lines: list[str], rule: str) -> Finding:
    version = _upstream(package.version) if package.version and package.ecosystem in ("os",) else package.version
    props = library_properties(library_id, version)
    props.update(ecosystem=package.ecosystem, package=package.name, declared_version=package.version)
    evidence = Evidence(file.rel, package.line, None, snippet(lines, package.line - 1) if package.line and lines else None)
    name = props["library"] + (f" {version}" if version else "")
    return Finding(kind="library", identity={"library": library_id, "version": version}, name=name, evidence=evidence,
                   detector=DETECTOR, rule=rule, confidence=0.97 if version else 0.85, function="dependency", properties=props)


# ------------------------------------------------------------------ parsers

def _line_of(lines: list[str], needle: str) -> int | None:
    low = needle.lower()
    for i, line in enumerate(lines):
        if low in line.lower():
            return i + 1
    return None


def _requirements(lines: list[str]) -> Iterator[Package]:
    for i, line in enumerate(lines):
        m = re.match(r"^\s*([A-Za-z0-9_.\-\[\]]+)\s*(?:\[[^\]]*\])?\s*(?:(==|>=|~=|<=|>|<)\s*([\w.*+-]+))?", line)
        if m and not line.strip().startswith(("#", "-")):
            yield Package("pypi", m.group(1).split("[")[0].lower().replace("_", "-"), m.group(3) if m.group(2) in ("==", "~=", ">=") else None, i + 1)


def _pyproject(text: str, lines: list[str]) -> Iterator[Package]:
    try:
        data = tomllib.loads(text)
    except tomllib.TOMLDecodeError:
        return
    deps = list(data.get("project", {}).get("dependencies", []))
    for group in data.get("project", {}).get("optional-dependencies", {}).values():
        deps += group
    for spec in deps:
        m = re.match(r"^\s*([A-Za-z0-9_.\-]+)(?:\[[^\]]*\])?\s*(?:[=~><!]=?\s*([\w.*+-]+))?", spec)
        if m:
            yield Package("pypi", m.group(1).lower().replace("_", "-"), m.group(2), _line_of(lines, m.group(1)))
    poetry = data.get("tool", {}).get("poetry", {})
    for section in ("dependencies", "dev-dependencies"):
        for name, spec in poetry.get(section, {}).items():
            version = spec if isinstance(spec, str) else spec.get("version") if isinstance(spec, dict) else None
            yield Package("pypi", name.lower(), _clean_version(version), _line_of(lines, name))


def _lock_toml(text: str, ecosystem: str, lines: list[str]) -> Iterator[Package]:
    try:
        data = tomllib.loads(text)
    except tomllib.TOMLDecodeError:
        return
    for pkg in data.get("package", []):
        if isinstance(pkg, dict) and "name" in pkg:
            yield Package(ecosystem, pkg["name"].lower(), pkg.get("version"), _line_of(lines, f'name = "{pkg["name"]}"'))


def _package_json(text: str, lines: list[str]) -> Iterator[Package]:
    try:
        data = json.loads(text)
    except ValueError:
        return
    for section in ("dependencies", "devDependencies", "optionalDependencies", "peerDependencies"):
        for name, version in (data.get(section) or {}).items():
            yield Package("npm", name.lower(), _clean_version(str(version)), _line_of(lines, f'"{name}"'))


def _package_lock(text: str, lines: list[str]) -> Iterator[Package]:
    try:
        data = json.loads(text)
    except ValueError:
        return
    for path, meta in (data.get("packages") or {}).items():
        if path and isinstance(meta, dict):
            name = path.split("node_modules/")[-1]
            yield Package("npm", name.lower(), meta.get("version"), None)
    for name, meta in (data.get("dependencies") or {}).items():
        if isinstance(meta, dict):
            yield Package("npm", name.lower(), meta.get("version"), None)


def _yarn_lock(lines: list[str]) -> Iterator[Package]:
    current: tuple[str, int] | None = None
    for i, line in enumerate(lines):
        m = re.match(r'^"?(@?[^@\s"]+)@', line)
        if m and not line.startswith(" "):
            current = (m.group(1), i + 1)
            continue
        v = re.match(r'^\s+version:?\s+"?([^"\s]+)"?', line)
        if v and current:
            yield Package("npm", current[0].lower(), v.group(1), current[1])
            current = None


def _pnpm_lock(lines: list[str]) -> Iterator[Package]:
    for i, line in enumerate(lines):
        m = re.match(r"^\s+/?['\"]?(@?[\w.-]+(?:/[\w.-]+)?)@(\d[\w.+-]*)", line)
        if m:
            yield Package("npm", m.group(1).lower(), m.group(2), i + 1)


def _pom(text: str, lines: list[str]) -> Iterator[Package]:
    try:
        root = ET.fromstring(text)
    except ET.ParseError:
        return
    ns = {"m": root.tag.split("}")[0].strip("{")} if root.tag.startswith("{") else {}
    prefix = "m:" if ns else ""
    props = {}
    properties = root.find(f"{prefix}properties", ns)
    if properties is not None:
        for child in properties:
            props[child.tag.split("}")[-1]] = (child.text or "").strip()
    for dep in root.iter(f"{{{ns['m']}}}dependency" if ns else "dependency"):
        group = dep.findtext(f"{prefix}groupId", default="", namespaces=ns).strip()
        artifact = dep.findtext(f"{prefix}artifactId", default="", namespaces=ns).strip()
        version = dep.findtext(f"{prefix}version", default="", namespaces=ns).strip()
        m = re.match(r"^\$\{(.+)\}$", version)
        if m:
            version = props.get(m.group(1), "")
        if group and artifact:
            yield Package("maven", f"{group}:{artifact}".lower(), _clean_version(version), _line_of(lines, f"<artifactId>{artifact}</artifactId>"))


def _gradle(lines: list[str]) -> Iterator[Package]:
    for i, line in enumerate(lines):
        for m in re.finditer(r"""["']([\w.-]+):([\w.-]+):([\w.+-]+)["']""", line):
            yield Package("maven", f"{m.group(1)}:{m.group(2)}".lower(), m.group(3), i + 1)
        m = re.search(r"""group\s*[:=]\s*["']([\w.-]+)["']\s*,\s*name\s*[:=]\s*["']([\w.-]+)["']\s*,\s*version\s*[:=]\s*["']([\w.+-]+)["']""", line)
        if m:
            yield Package("maven", f"{m.group(1)}:{m.group(2)}".lower(), m.group(3), i + 1)


def _go_mod(lines: list[str]) -> Iterator[Package]:
    in_block = False
    for i, line in enumerate(lines):
        stripped = line.strip()
        m = re.match(r"^go\s+(\d+\.\d+(?:\.\d+)?)", stripped)
        if m:
            yield Package("go-toolchain", "go", m.group(1), i + 1)
        m = re.match(r"^toolchain\s+go(\d+\.\d+(?:\.\d+)?)", stripped)
        if m:
            yield Package("go-toolchain", "go", m.group(1), i + 1)
        if stripped.startswith("require ("):
            in_block = True
            continue
        if in_block and stripped == ")":
            in_block = False
            continue
        m = re.match(r"^(?:require\s+)?([\w.\-/]+)\s+v([\w.+-]+)", stripped) if in_block or stripped.startswith("require ") else None
        if m:
            yield Package("go", m.group(1).lower(), m.group(2), i + 1)


def _cargo_toml(text: str, lines: list[str]) -> Iterator[Package]:
    try:
        data = tomllib.loads(text)
    except tomllib.TOMLDecodeError:
        return
    for section in ("dependencies", "dev-dependencies", "build-dependencies"):
        for name, spec in (data.get(section) or {}).items():
            version = spec if isinstance(spec, str) else spec.get("version") if isinstance(spec, dict) else None
            package = spec.get("package", name) if isinstance(spec, dict) else name
            yield Package("cargo", package.lower(), _clean_version(version), _line_of(lines, name))


def _gemfile_lock(lines: list[str]) -> Iterator[Package]:
    for i, line in enumerate(lines):
        m = re.match(r"^    ([\w.-]+) \(([\w.+-]+)\)", line)
        if m:
            yield Package("rubygems", m.group(1).lower(), m.group(2), i + 1)


def _gemfile(lines: list[str]) -> Iterator[Package]:
    for i, line in enumerate(lines):
        m = re.match(r"""^\s*gem\s+["']([\w.-]+)["'](?:\s*,\s*["'][~>=<\s]*([\d.]+)["'])?""", line)
        if m:
            yield Package("rubygems", m.group(1).lower(), m.group(2), i + 1)


def _composer(text: str, lines: list[str], lock: bool) -> Iterator[Package]:
    try:
        data = json.loads(text)
    except ValueError:
        return
    if lock:
        for pkg in (data.get("packages") or []) + (data.get("packages-dev") or []):
            yield Package("composer", pkg.get("name", "").lower(), str(pkg.get("version", "")).lstrip("v") or None, _line_of(lines, f'"{pkg.get("name")}"'))
    else:
        for section in ("require", "require-dev"):
            for name, version in (data.get(section) or {}).items():
                yield Package("composer", name.lower(), _clean_version(version), _line_of(lines, f'"{name}"'))


def _dotnet(text: str, lines: list[str]) -> Iterator[Package]:
    for m in re.finditer(r'<PackageReference\s+Include="([^"]+)"(?:\s+Version="([^"]+)")?', text):
        yield Package("nuget", m.group(1).lower(), _clean_version(m.group(2)), _line_of(lines, m.group(1)))
    for m in re.finditer(r'<package\s+id="([^"]+)"\s+version="([^"]+)"', text):
        yield Package("nuget", m.group(1).lower(), m.group(2), _line_of(lines, m.group(1)))


def _swift(text: str, lines: list[str], resolved: bool) -> Iterator[Package]:
    if resolved:
        try:
            data = json.loads(text)
        except ValueError:
            return
        pins = data.get("pins") or (data.get("object") or {}).get("pins") or []
        for pin in pins:
            url = pin.get("location") or pin.get("repositoryURL") or ""
            name = url.rstrip("/").split("/")[-1].removesuffix(".git").lower()
            version = (pin.get("state") or {}).get("version")
            yield Package("swift", name, version, _line_of(lines, name))
    else:
        for m in re.finditer(r'\.package\(\s*url:\s*"([^"]+)"[^)]*?(?:from:\s*"([\d.]+)")?', text):
            name = m.group(1).rstrip("/").split("/")[-1].removesuffix(".git").lower()
            yield Package("swift", name, m.group(2), _line_of(lines, m.group(1)))


def _conan(lines: list[str]) -> Iterator[Package]:
    for i, line in enumerate(lines):
        m = re.match(r"^\s*([\w.-]+)/([\w.+-]+)", line)
        if m and "@" not in m.group(1):
            yield Package("conan", m.group(1).lower(), m.group(2), i + 1)


def _vcpkg(text: str, lines: list[str]) -> Iterator[Package]:
    try:
        data = json.loads(text)
    except ValueError:
        return
    for dep in data.get("dependencies", []):
        name = dep if isinstance(dep, str) else dep.get("name", "")
        yield Package("vcpkg", name.lower(), None if isinstance(dep, str) else dep.get("version>="), _line_of(lines, f'"{name}"'))


def _dpkg(lines: list[str]) -> Iterator[Package]:
    name = version = None
    start = 0
    for i, line in enumerate(lines + [""]):
        if line.startswith("Package: "):
            name, start = line[9:].strip(), i + 1
        elif line.startswith("Version: "):
            version = line[9:].strip()
        elif not line.strip():
            if name:
                yield Package("os", name.lower(), version, start)
            name = version = None


def _apk(lines: list[str]) -> Iterator[Package]:
    name = version = None
    start = 0
    for i, line in enumerate(lines + [""]):
        if line.startswith("P:"):
            name, start = line[2:].strip(), i + 1
        elif line.startswith("V:"):
            version = line[2:].strip()
        elif not line.strip():
            if name:
                yield Package("os", name.lower(), version, start)
            name = version = None


def packages(file: FileInfo, text: str) -> Iterator[Package]:
    name = file.name.lower()
    lines = text.splitlines()
    rel = file.rel.lower()
    if name.startswith("requirements") and name.endswith(".txt"):
        yield from _requirements(lines)
    elif name == "pyproject.toml":
        yield from _pyproject(text, lines)
    elif name == "poetry.lock":
        yield from _lock_toml(text, "pypi", lines)
    elif name == "pipfile.lock":
        try:
            data = json.loads(text)
            for section in ("default", "develop"):
                for pkg, meta in (data.get(section) or {}).items():
                    yield Package("pypi", pkg.lower(), str(meta.get("version", "")).lstrip("=") or None, _line_of(lines, f'"{pkg}"'))
        except ValueError:
            return
    elif name == "package.json":
        yield from _package_json(text, lines)
    elif name in ("package-lock.json", "npm-shrinkwrap.json"):
        yield from _package_lock(text, lines)
    elif name == "yarn.lock":
        yield from _yarn_lock(lines)
    elif name == "pnpm-lock.yaml":
        yield from _pnpm_lock(lines)
    elif name == "pom.xml":
        yield from _pom(text, lines)
    elif name in ("build.gradle", "build.gradle.kts", "gradle.lockfile"):
        yield from _gradle(lines)
    elif name == "go.mod":
        yield from _go_mod(lines)
    elif name == "cargo.toml":
        yield from _cargo_toml(text, lines)
    elif name == "cargo.lock":
        yield from _lock_toml(text, "cargo", lines)
    elif name == "gemfile.lock":
        yield from _gemfile_lock(lines)
    elif name == "gemfile":
        yield from _gemfile(lines)
    elif name in ("composer.json", "composer.lock"):
        yield from _composer(text, lines, lock=name.endswith(".lock"))
    elif name.endswith((".csproj", ".fsproj", ".vbproj")) or name == "packages.config":
        yield from _dotnet(text, lines)
    elif name in ("package.swift", "package.resolved"):
        yield from _swift(text, lines, resolved=name.endswith(".resolved"))
    elif name == "conanfile.txt":
        yield from _conan(lines)
    elif name == "vcpkg.json":
        yield from _vcpkg(text, lines)
    elif rel.endswith("var/lib/dpkg/status"):
        yield from _dpkg(lines)
    elif rel.endswith("lib/apk/db/installed"):
        yield from _apk(lines)


def scan(file: FileInfo, text: str) -> Iterator[Finding]:
    _, index = _knowledge()
    lines = text.splitlines()
    seen: set[tuple[str, str | None]] = set()
    for package in packages(file, text):
        library_id = index.get((package.ecosystem, package.name))
        if not library_id:
            continue
        key = (library_id, package.version)
        if key in seen:
            continue
        seen.add(key)
        yield _finding(library_id, package, file, lines, rule=f"manifest.{package.ecosystem}")


_JAR_NAME = re.compile(r"(?:^|/)([A-Za-z][\w.-]*?)-(\d+(?:\.\d+)+(?:[.-][\w]+)?)\.jar$")
_JAR_ARTIFACTS = {
    "bcprov-jdk18on": "bouncycastle", "bcprov-jdk15on": "bouncycastle", "bcprov-jdk15to18": "bouncycastle",
    "bcpkix-jdk18on": "bouncycastle", "bcpkix-jdk15on": "bouncycastle", "jjwt-api": "jjwt", "jjwt-impl": "jjwt",
    "nimbus-jose-jwt": "nimbus-jose", "java-jwt": "auth0-java-jwt", "xmlsec": "xmlsec", "tink": "tink",
    "conscrypt-openjdk": "conscrypt", "conscrypt-openjdk-uber": "conscrypt", "jbcrypt": "bcrypt", "liboqs-java": "liboqs",
}


def bundled_jar(entry_path: str, evidence_path: str) -> Finding | None:
    """A library jar bundled inside another archive (e.g. BOOT-INF/lib/bcprov-jdk18on-1.78.jar)."""
    m = _JAR_NAME.search(entry_path)
    if not m or m.group(1).lower() not in _JAR_ARTIFACTS:
        return None
    library_id = _JAR_ARTIFACTS[m.group(1).lower()]
    package = Package("maven", m.group(1).lower(), m.group(2), None)
    props = library_properties(library_id, package.version)
    props.update(ecosystem="maven", package=m.group(1), declared_version=package.version, bundled=True)
    return Finding(kind="library", identity={"library": library_id, "version": package.version},
                   name=f"{props['library']} {package.version}", evidence=Evidence(evidence_path),
                   detector=DETECTOR, rule="archive.bundled-jar", confidence=0.95, function="dependency", properties=props)
