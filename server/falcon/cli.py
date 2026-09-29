"""Offline command line for pipelines: scan, attest and verify without a server.

    falcon scan PATH [--format sarif|cyclonedx|cyclonedx-xml|spdx|csv|json|table]
                     [--output FILE] [--fail-on critical|high|medium|low|hndl|broken|never]
                     [--sign-key KEY.pem] [--criticality ...] [--scenario ...]
    falcon keygen --out DIR            # an ML-DSA-65 key pair for signing CBOMs in CI
    falcon verify ENVELOPE --key PUB.pem

``PATH`` is a folder, an archive (zip, tar, tar.gz), a saved container image
(``docker save`` or OCI layout tarball), a git URL, or with ``--endpoint`` a
list of ``host:port`` TLS endpoints. The scan runs the same engine, risk model
and recommendation engine as the platform, consolidated in memory; nothing is
written except the report.

Exit codes: 0 clean, 1 the ``--fail-on`` gate tripped, 2 usage or scan error,
3 verification failed.
"""
from __future__ import annotations

import argparse
import json
import sys
import tarfile
import tempfile
import time
from pathlib import Path
from typing import Any

EXIT_OK, EXIT_GATE, EXIT_ERROR, EXIT_INVALID = 0, 1, 2, 3
_BANDS = ["low", "medium", "high", "critical"]
_FORMATS = ("table", "sarif", "cyclonedx", "cyclonedx-xml", "spdx", "csv", "json")


def _utf8_streams() -> None:
    """Windows consoles default to a legacy code page; reports and symbols are UTF-8."""
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure:
            try:
                reconfigure(encoding="utf-8", errors="replace")
            except (ValueError, OSError):
                pass


def _source_kind(target: str, endpoint: bool) -> tuple[str, str]:
    if endpoint:
        return "endpoint", target
    if target.startswith(("https://", "http://", "git@", "ssh://")) or target.endswith(".git"):
        return "git", target
    path = Path(target).expanduser().resolve()
    if path.is_dir():
        return "directory", str(path)
    if not path.is_file():
        raise SystemExit(f"falcon: {target}: no such file or folder")
    if tarfile.is_tarfile(path):
        with tarfile.open(path) as tf:
            names = {m.name.lstrip("./") for m in tf.getmembers()[:2000]}
        if "manifest.json" in names or "oci-layout" in names:
            return "image-archive", str(path)
    return "archive", str(path)


def _progress(enabled: bool):
    state = {"last": 0.0}

    def emit(kind: str, payload: Any, sink: list[dict[str, Any]]) -> None:
        if kind == "findings":
            sink.extend(payload)
        elif enabled and kind == "stage":
            print(f"  {payload.get('detail') or payload.get('stage')}", file=sys.stderr)
        elif enabled and kind == "progress" and time.monotonic() - state["last"] > 1.0:
            state["last"] = time.monotonic()
            total, done = payload.get("files_total") or 0, payload.get("files_done") or 0
            if total:
                print(f"  {done:,}/{total:,} files · {payload.get('findings', 0):,} findings", file=sys.stderr)
    return emit


def _table(report, limit: int = 25) -> str:
    from .reporting.tabular import summary

    s = summary(report)
    lines = [f"FALCON · {report.scope}", f"{s['artefacts']} cryptographic artefacts · threat model {report.model.scenario}", ""]
    bands = s["bands"]
    lines.append("Risk     " + "  ".join(f"{b} {bands[b]}" for b in ("critical", "high", "medium", "low")))
    lines.append(f"Quantum  " + "  ".join(f"{k} {v}" for k, v in sorted(s["quantum"].items())))
    lines.append(f"Harvest-now-decrypt-later exposed: {s['hndl_exposed']} · broken or weak today: {s['broken_or_weak']}")
    lines.append("")
    rows = sorted(report.items, key=lambda i: (-i.risk.score, i.facts.name))[:limit]
    width = max((len(i.facts.name) for i in rows), default=10)
    width = min(max(width, 10), 42)
    lines.append(f"{'SCORE':>5}  {'BAND':<8}  {'ARTEFACT':<{width}}  {'QUANTUM':<10}  WHERE / REPLACE WITH")
    for i in rows:
        where = f"{i.occurrences[0].path}:{i.occurrences[0].line}" if i.occurrences and i.occurrences[0].line else (
            i.occurrences[0].path if i.occurrences else "")
        rec = i.recommendation or {}
        fix = f" → {rec['primary']['name']}" if rec.get("primary") and rec.get("action") != "keep" else ""
        lines.append(f"{i.risk.score:>5}  {i.risk.band:<8}  {i.facts.name[:width]:<{width}}  {(i.facts.quantum or '-'):<10}  {where}{fix}")
    if len(report.items) > limit:
        lines.append(f"… and {len(report.items) - limit} more (use --format csv or json for all).")
    return "\n".join(lines) + "\n"


def _gate(report, fail_on: str) -> tuple[bool, str]:
    if fail_on == "never":
        return False, ""
    if fail_on == "hndl":
        hits = [i for i in report.items if i.risk.hndl.get("exposed")]
        return bool(hits), f"{len(hits)} artefacts exposed to harvest now, decrypt later"
    if fail_on == "broken":
        hits = [i for i in report.items if i.facts.classical in ("broken", "weak")]
        return bool(hits), f"{len(hits)} artefacts broken or weak against classical attack"
    floor = _BANDS.index(fail_on)
    hits = [i for i in report.items if i.risk.band in _BANDS and _BANDS.index(i.risk.band) >= floor]
    return bool(hits), f"{len(hits)} artefacts at {fail_on} risk or above"


def cmd_scan(args: argparse.Namespace) -> int:
    _utf8_streams()
    from .discovery import engine
    from .domains.horizon.model import ThreatModel
    from .reporting import attest, cbom, sarif, spdx, tabular
    from .reporting.inventory import OfflineInventory
    from .risk.facts import SystemFacts

    kind, locator = _source_kind(args.path, args.endpoint)
    quiet = args.quiet or not sys.stderr.isatty()
    if not quiet:
        print(f"FALCON scanning {locator}", file=sys.stderr)
    findings: list[dict[str, Any]] = []
    emit = _progress(not quiet)
    started = time.monotonic()
    with tempfile.TemporaryDirectory(prefix="falcon-") as work:
        job = engine.Job(scan_id="cli", kind=kind, locator=locator, workdir=str(Path(work) / "job"),
                         options={"timeout": 6} if kind == "endpoint" else {})
        try:
            stats = engine.run(job, lambda k, p: emit(k, p, findings))
        except Exception as err:  # noqa: BLE001 - reported, not raised, for pipelines
            print(f"falcon: scan failed: {err}", file=sys.stderr)
            return EXIT_ERROR

    inventory = OfflineInventory()
    inventory.ingest(findings)
    name = args.name or Path(locator).name or locator
    system = SystemFacts("cli", args.code or "SCAN", name, "application", args.criticality, args.exposure,
                         args.classification, float(args.shelf_life), float(args.migration_years))
    model = ThreatModel.build(args.scenario, None, None, args.tolerance)
    report = inventory.report(system, model, organisation=args.organisation, scope=name,
                              origin={"mode": "offline", "path": locator, "kind": kind})

    fmt = args.format
    if fmt == "table":
        content = _table(report)
    elif fmt == "sarif":
        content = json.dumps(sarif.build(report), indent=2, ensure_ascii=False)
    elif fmt in ("cyclonedx", "cyclonedx-xml"):
        doc = cbom.build(report)
        content = cbom.to_json(doc) if fmt == "cyclonedx" else cbom.to_xml(doc)
    elif fmt == "spdx":
        content = json.dumps(spdx.build(report), indent=2, ensure_ascii=False)
    elif fmt == "csv":
        content = tabular.to_csv(report)
    else:
        content = json.dumps(tabular.to_native(report), indent=2, ensure_ascii=False, default=str)

    if args.output:
        Path(args.output).write_text(content, encoding="utf-8", newline="" if fmt == "csv" else None)
    else:
        sys.stdout.write(content)

    if args.sign_key:
        key = _load_key(Path(args.sign_key))
        doc = cbom.build(report)
        digest = cbom.digest(doc)
        envelope = attest.sign(key, attest.statement(doc, name=f"{name}.cdx.json", digest=digest))
        target = Path(args.attestation or (f"{args.output}.dsse.json" if args.output else "falcon-cbom.dsse.json"))
        target.write_text(json.dumps(envelope, indent=2), encoding="utf-8")
        if not quiet:
            print(f"Signed CBOM attestation (ML-DSA-65, key {key.id[:16]}…) → {target}", file=sys.stderr)

    tripped, reason = _gate(report, args.fail_on)
    if not quiet:
        s = tabular.summary(report)
        print(f"{s['artefacts']} artefacts in {stats.get('files', stats.get('endpoints') and len(stats['endpoints']) or 0)} "
              f"{'endpoints' if kind == 'endpoint' else 'files'} · {time.monotonic() - started:.1f}s", file=sys.stderr)
    if tripped:
        print(f"falcon: gate failed (--fail-on {args.fail_on}): {reason}", file=sys.stderr)
        return EXIT_GATE
    return EXIT_OK


def _load_key(path: Path):
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric import mldsa

    from .reporting.attest import SigningKey

    private = serialization.load_pem_private_key(path.read_bytes(), password=None)
    if not isinstance(private, mldsa.MLDSA65PrivateKey):
        raise SystemExit("falcon: the signing key is not an ML-DSA-65 private key (create one with `falcon keygen`)")
    return SigningKey(private, "")


def cmd_keygen(args: argparse.Namespace) -> int:
    _utf8_streams()
    from .reporting.attest import KeyStore

    store = KeyStore(Path(args.out))
    if (Path(args.out) / "attestation-mldsa65.pem").exists() and not args.force:
        print(f"falcon: a key already exists in {args.out} (use --force to replace it)", file=sys.stderr)
        return EXIT_ERROR
    key = store.rotate() if args.force else store.signing_key()
    info = key.describe()
    public = Path(args.out) / "falcon-attestation.pub.pem"
    public.write_text(info["public_key_pem"], encoding="ascii")
    print(f"ML-DSA-65 key {info['fingerprint']}")
    print(f"  private: {Path(args.out) / 'attestation-mldsa65.pem'}  (keep secret; store as a CI secret)")
    print(f"  public:  {public}")
    return EXIT_OK


def cmd_verify(args: argparse.Namespace) -> int:
    _utf8_streams()
    from .reporting.attest import verify

    envelope = Path(args.envelope).read_text(encoding="utf-8")
    keys = [Path(k).read_text(encoding="ascii") for k in args.key]
    result = verify(envelope, keys)
    for c in result["checks"]:
        print(f"  {'✓' if c['ok'] else '✗'} {c['check']:<10} {c['detail']}")
    if result["valid"]:
        subject = result["subject"]
        print(f"Verified: {subject['name']} sha256:{subject['sha256'][:16]}… · {result.get('components', 0)} components · signed {result.get('timestamp')}")
        if args.extract:
            Path(args.extract).write_text(json.dumps(result["cbom"], indent=2, ensure_ascii=False), encoding="utf-8")
            print(f"CBOM written to {args.extract}")
        return EXIT_OK
    print("Verification FAILED", file=sys.stderr)
    return EXIT_INVALID


def add_commands(sub: argparse._SubParsersAction) -> None:
    scan = sub.add_parser("scan", help="scan a folder, archive, image, repository or endpoints offline and write a report")
    scan.add_argument("path", help="folder, archive, saved image, git URL, or host:port list with --endpoint")
    scan.add_argument("--endpoint", action="store_true", help="treat PATH as comma-separated host:port TLS endpoints")
    scan.add_argument("-f", "--format", choices=_FORMATS, default="table")
    scan.add_argument("-o", "--output", help="write the report here instead of standard output")
    scan.add_argument("--fail-on", choices=["critical", "high", "medium", "low", "hndl", "broken", "never"], default="never",
                      help="exit 1 when any artefact reaches this risk band (or is HNDL-exposed, or broken)")
    scan.add_argument("--sign-key", help="ML-DSA-65 private key (PEM) to sign the CBOM as a DSSE attestation")
    scan.add_argument("--attestation", help="where to write the signed attestation")
    scan.add_argument("--name", help="system name (default: the folder or file name)")
    scan.add_argument("--code", help="system code, used in stable CBOM references")
    scan.add_argument("--organisation", default="Unspecified organisation")
    scan.add_argument("--criticality", choices=["critical", "high", "moderate", "low"], default="high")
    scan.add_argument("--exposure", choices=["external", "partner", "internal", "isolated"], default="external")
    scan.add_argument("--classification", choices=["secret", "restricted", "confidential", "internal", "public"], default="confidential")
    scan.add_argument("--shelf-life", type=float, default=10.0, help="years the data must stay confidential (Mosca X)")
    scan.add_argument("--migration-years", type=float, default=3.0, help="years the system needs to migrate")
    scan.add_argument("--scenario", choices=["aggressive", "moderate", "conservative"], default="moderate",
                      help="CRQC arrival scenario (Mosca Z)")
    scan.add_argument("--tolerance", type=float, default=0.05, help="acceptable chance a CRQC arrives first")
    scan.add_argument("-q", "--quiet", action="store_true")
    scan.set_defaults(handler=cmd_scan)

    keygen = sub.add_parser("keygen", help="create an ML-DSA-65 key pair for signing CBOMs")
    keygen.add_argument("--out", default="falcon-keys")
    keygen.add_argument("--force", action="store_true")
    keygen.set_defaults(handler=cmd_keygen)

    verify = sub.add_parser("verify", help="verify a signed CBOM attestation (DSSE, ML-DSA-65)")
    verify.add_argument("envelope")
    verify.add_argument("--key", action="append", required=True, help="public key PEM (repeatable)")
    verify.add_argument("--extract", help="write the verified CBOM to this file")
    verify.set_defaults(handler=cmd_verify)
