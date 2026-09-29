"""The scan pipeline, run inside an isolated worker process.

    acquire  -> materialise the source into a workspace (or resolve endpoints)
    enumerate -> walk and classify files; publish the coverage map
    analyse  -> dispatch each file to the detectors that understand it
    finish   -> report totals; the server consolidates the inventory

The engine never touches the database. It reports through ``emit(kind,
payload)``; the parent process persists findings and relays progress.
"""
from __future__ import annotations

import os
import shutil
import ssl
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

from . import catalogue, rules, workspace
from .detectors import binaries, dependencies, iac, java, material, python_ast, tls_config
from .model import Finding, protocol_finding
from .walker import FileInfo, read_text, walk

ENGINE_VERSION = "1.0.0"

Emit = Callable[[str, Any], None]

_PACKS = {
    "python": ("python", "universal"), "java": ("java", "universal"), "javascript": ("javascript", "universal"),
    "go": ("go", "universal"), "c": ("c", "universal"), "csharp": ("csharp", "universal"), "rust": ("rust", "universal"),
    "php": ("php", "universal"), "ruby": ("ruby", "universal"), "swift": ("swift", "universal"),
}
_IAC_SUFFIXES = (".tf", ".hcl", ".yaml", ".yml", ".json", ".template")


@dataclass
class Job:
    scan_id: str
    kind: str  # directory | archive | git | image-archive | image-registry | endpoint
    locator: str
    workdir: str
    options: dict[str, Any] = field(default_factory=dict)
    limits: dict[str, Any] = field(default_factory=dict)


class _Stream:
    """Batches findings and throttles progress so the pipe stays cheap."""

    def __init__(self, emit: Emit) -> None:
        self.emit = emit
        self.batch: list[dict[str, Any]] = []
        self.last_flush = time.monotonic()
        self.last_progress = 0.0
        self.seen: set[tuple[str, str, int | None]] = set()
        self.count = 0

    def add(self, finding: Finding) -> bool:
        key = (finding.fingerprint, finding.evidence.path, finding.evidence.line)
        if key in self.seen:
            return False
        self.seen.add(key)
        self.batch.append(finding.as_message())
        self.count += 1
        if len(self.batch) >= 200 or time.monotonic() - self.last_flush > 0.4:
            self.flush()
        return True

    def flush(self) -> None:
        if self.batch:
            self.emit("findings", self.batch)
            self.batch = []
        self.last_flush = time.monotonic()

    def progress(self, payload: dict[str, Any], force: bool = False) -> None:
        now = time.monotonic()
        if force or now - self.last_progress > 0.12:
            self.emit("progress", payload)
            self.last_progress = now


def _coverage_key(rel: str) -> str:
    parts = rel.split("/")[:-1]
    return "/".join(parts[:2]) if parts else "."


_HYBRID_GROUPS = {"X25519MLKEM768", "SecP256r1MLKEM768", "SecP384r1MLKEM1024", "X25519Kyber768Draft00", "ML-KEM"}


def _promote_hybrid(found: list[Finding]) -> list[Finding]:
    """TLS 1.3 configured alongside a hybrid key-exchange group in the same file
    negotiates post-quantum key exchange: record the protocol that way."""
    has_hybrid = any(f.kind == "algorithm" and f.identity.get("algorithm") in _HYBRID_GROUPS and f.function == "key-agree" for f in found)
    if not has_hybrid:
        return found
    out = []
    for f in found:
        if f.kind == "protocol" and f.identity.get("protocol") == "TLS" and f.identity.get("version") == "1.3" and not f.identity.get("hybrid"):
            f = protocol_finding("TLS 1.3", f.evidence, detector=f.detector, rule=f.rule, confidence=f.confidence, hybrid=True,
                                 extra={k: v for k, v in f.properties.items() if k != "assessment"})
        out.append(f)
    return out


def detect(file: FileInfo) -> list[Finding]:
    """Run every detector that applies to one file."""
    return _promote_hybrid(_detect(file))


def _detect(file: FileInfo) -> list[Finding]:
    found: list[Finding] = []
    category = file.category
    if category in ("material", "binary", "java-class", "java-archive"):
        try:
            raw = file.path.read_bytes()
        except OSError:
            return found
        if category == "material":
            found += material.scan(file, raw)
        elif category == "binary":
            found += binaries.scan(file, raw)
        elif category == "java-class":
            found += java.scan_class(file, raw)
        else:
            found += java.scan_archive(file, raw)
        return found

    text = read_text(file.path)
    if text is None:
        return found
    if category == "source":
        if file.language == "python":
            found += python_ast.scan(file, text)
        for pack in _PACKS.get(file.language or "", ("universal",)):
            found += rules.scan_text(text, file.rel, rules.load_pack(pack), detector=f"rules:{pack}")
        if "-----BEGIN" in text:
            found += material.scan(file, text.encode("utf-8", "ignore"))
    elif category == "manifest":
        found += dependencies.scan(file, text)
    elif category in ("config", "text"):
        found += tls_config.scan(file, text)
        found += rules.scan_text(text, file.rel, rules.load_pack("universal"), detector="rules:universal")
        if file.name.lower().endswith(_IAC_SUFFIXES):
            found += iac.scan(file, text)
        if "-----BEGIN" in text or '"kty"' in text:
            found += material.scan(file, text.encode("utf-8", "ignore"))
    return found


def _acquire(job: Job, emit: Emit) -> tuple[Path, dict[str, Any]]:
    limits = workspace.Limits(**{k: v for k, v in job.limits.items() if k in workspace.Limits.__dataclass_fields__})
    # Extended-length paths on Windows: unpacked images nest far beyond 260 characters.
    work = workspace.extended_path(Path(job.workdir))
    if job.kind == "directory":
        root = Path(job.locator)
        if not root.is_dir():
            raise workspace.AcquisitionError("The folder no longer exists or cannot be read.")
        return workspace.extended_path(root), {"path": str(root)}
    work.mkdir(parents=True, exist_ok=True)
    target = work / "tree"
    if job.kind == "archive":
        emit("stage", {"stage": "acquire", "detail": "Extracting archive"})
        entries = workspace.extract_archive(Path(job.locator), target, limits)
        return target, {"entries": entries}
    if job.kind == "git":
        emit("stage", {"stage": "acquire", "detail": "Cloning repository"})
        # Git takes the plain path (with core.longpaths); the walk uses the extended form.
        facts = workspace.clone(job.locator, Path(job.workdir) / "tree", job.options.get("ref"), limits)
        return target, facts
    if job.kind == "image-archive":
        emit("stage", {"stage": "acquire", "detail": "Unpacking image layers"})
        facts = workspace.unpack_image_tar(Path(job.locator), target, limits)
        return target, facts
    if job.kind == "image-registry":
        emit("stage", {"stage": "acquire", "detail": "Pulling image"})
        credentials = tuple(job.options["credentials"]) if job.options.get("credentials") else None
        facts = workspace.pull_image(job.locator, target, limits, credentials,
                                     progress=lambda d: emit("stage", {"stage": "acquire", "detail": d}))
        return target, facts
    raise workspace.AcquisitionError(f"Unsupported source type {job.kind!r}.")


def _run_endpoints(job: Job, emit: Emit, stream: _Stream) -> dict[str, Any]:
    from .endpoints import assess, parse_endpoints

    targets = parse_endpoints(job.locator)
    emit("tree", {"leaves": [{"key": f"{h}:{p}", "files": 1, "bytes": 1} for h, p in targets]})
    emit("stage", {"stage": "analyse", "detail": f"Probing {len(targets)} endpoint{'s' if len(targets) != 1 else ''}"})
    results = []
    for done, (endpoint, findings, summary) in enumerate(assess(targets, timeout=float(job.options.get("timeout", 6))), 1):
        for finding in findings or []:
            stream.add(finding)
        results.append(summary)
        stream.progress({"files_total": len(targets), "files_done": done, "current": endpoint, "findings": stream.count,
                         "coverage": {endpoint: [1, len(findings or [])]}}, force=True)
    stream.flush()
    return {"endpoints": results}


def run(job: Job, emit: Emit) -> dict[str, Any]:
    started = time.monotonic()
    stream = _Stream(emit)
    emit("stage", {"stage": "acquire", "detail": "Preparing source"})
    stats: dict[str, Any] = {"engine": ENGINE_VERSION, "knowledge": {"algorithms": catalogue.version(),
                             "libraries": dependencies.knowledge_version()}, "openssl": ssl.OPENSSL_VERSION}

    if job.kind == "endpoint":
        stats.update(_run_endpoints(job, emit, stream))
        stats["duration_seconds"] = round(time.monotonic() - started, 2)
        probed = len(stats["endpoints"])
        emit("done", {"stats": stats, "findings": stream.count, "files_total": probed, "files_done": probed})
        return stats

    try:
        root, facts = _acquire(job, emit)
        stats["source"] = facts
        emit("stage", {"stage": "enumerate", "detail": "Discovering files"})
        files, skipped = walk(root, max_file_bytes=int(job.limits.get("max_file_bytes", 16 * 1024**2)),
                              max_files=int(job.limits.get("max_files", 200_000)))
        stats["skipped"] = skipped
        leaves: dict[str, dict[str, int]] = {}
        languages: dict[str, int] = {}
        for f in files:
            leaf = leaves.setdefault(_coverage_key(f.rel), {"files": 0, "bytes": 0})
            leaf["files"] += 1
            leaf["bytes"] += f.size
            label = f.language or f.category
            languages[label] = languages.get(label, 0) + 1
        stats["composition"] = languages
        emit("tree", {"leaves": [{"key": k, **v} for k, v in leaves.items()]})
        emit("stage", {"stage": "analyse", "detail": f"Analysing {len(files):,} files"})

        coverage_delta: dict[str, list[int]] = {}
        total_bytes = 0
        for done, file in enumerate(files, 1):
            key = _coverage_key(file.rel)
            added = 0
            try:
                for finding in detect(file):
                    if stream.add(finding):
                        added += 1
            except Exception as err:  # noqa: BLE001 - one bad file must never fail the scan
                stats.setdefault("file_errors", []).append({"path": file.rel, "error": type(err).__name__})
            delta = coverage_delta.setdefault(key, [0, 0])
            delta[0] += 1
            delta[1] += added
            total_bytes += file.size
            if time.monotonic() - stream.last_progress > 0.12 or done == len(files):
                stream.progress({"files_total": len(files), "files_done": done, "bytes_done": total_bytes,
                                 "current": file.rel, "findings": stream.count, "coverage": coverage_delta}, force=True)
                coverage_delta = {}
        stream.flush()
        stats["files"] = len(files)
        stats["bytes"] = total_bytes
        stats["duration_seconds"] = round(time.monotonic() - started, 2)
        if "file_errors" in stats:
            stats["file_errors"] = stats["file_errors"][:50]
        emit("done", {"stats": stats, "findings": stream.count, "files_total": len(files), "files_done": len(files)})
        return stats
    finally:
        if job.kind != "directory":
            shutil.rmtree(workspace.extended_path(Path(job.workdir)), ignore_errors=True)


def worker_main(job: dict[str, Any], conn) -> None:  # pragma: no cover - runs in the child process
    """Entry point of the scan worker process."""
    os.environ.setdefault("PYTHONIOENCODING", "utf-8")

    def emit(kind: str, payload: Any) -> None:
        conn.send((kind, payload))

    try:
        run(Job(**job), emit)
    except workspace.AcquisitionError as err:
        emit("error", {"code": "acquisition", "message": str(err)})
    except Exception as err:  # noqa: BLE001
        import traceback

        emit("error", {"code": "engine", "message": f"The scan engine stopped unexpectedly ({type(err).__name__}).",
                       "trace": traceback.format_exc()[-2000:]})
    finally:
        conn.close()
