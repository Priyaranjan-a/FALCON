"""Scan execution.

A small pool of runner threads claims queued scans one at a time. Each scan
runs the engine in a *separate process*, so a pathological input cannot take
the API down, and the parent can enforce cancellation and time limits by
terminating the child. The parent persists findings, keeps the scan row
current and relays progress to live subscribers.
"""
from __future__ import annotations

import logging
import multiprocessing as mp
import shutil
import threading
import time
from typing import Any

from sqlalchemy import select, update

from ...kernel import audit
from ...kernel.database import get_sessionmaker, utcnow
from ...kernel.events import hub
from ...settings import get_settings
from .consolidate import Consolidator
from .models import Scan, Source

logger = logging.getLogger("falcon.discovery")
ENGINE_ACTOR = "FALCON discovery engine"


def scan_topic(scan_id: str) -> str:
    return f"scan:{scan_id}"


class ScanRunner:
    def __init__(self) -> None:
        self._wake = threading.Event()
        self._stop = threading.Event()
        self._threads: list[threading.Thread] = []
        self._cancel: set[str] = set()
        self._lock = threading.Lock()
        self._started = False
        # Live state of running scans, so a viewer who connects mid-scan gets a
        # current snapshot rather than the last (up to a second old) database write.
        self._live: dict[str, dict[str, Any]] = {}

    # ------------------------------------------------------------ lifecycle
    def start(self) -> None:
        if self._started:
            return
        self._started = True
        self._recover()
        for index in range(get_settings().scan_workers):
            thread = threading.Thread(target=self._loop, name=f"falcon-scan-{index}", daemon=True)
            thread.start()
            self._threads.append(thread)

    def stop(self) -> None:
        """Stop claiming work; running scans end as cancelled and their workers are terminated."""
        self._stop.set()
        self._wake.set()
        for thread in self._threads:
            thread.join(timeout=10)
        self._threads.clear()
        self._started = False
        self._stop.clear()

    def wake(self) -> None:
        self._wake.set()

    def cancel(self, scan_id: str) -> None:
        with self._lock:
            self._cancel.add(scan_id)

    def live(self, scan_id: str) -> dict[str, Any] | None:
        """A copy of a running scan's in-memory progress, or None."""
        with self._lock:
            live = self._live.get(scan_id)
            if live is None:
                return None
            return {**live["state"], "evidence": live["consolidator"].evidence, "new_artefacts": len(live["consolidator"].new_ids),
                    "coverage": {k: dict(v) for k, v in live["coverage"].items()}}

    def _recover(self) -> None:
        """Scans interrupted by a restart cannot resume: mark them failed."""
        with get_sessionmaker()() as db:
            db.execute(update(Scan).where(Scan.status == "running").values(
                status="failed", error="Interrupted because FALCON restarted.", finished_at=utcnow()))
            db.commit()

    # ------------------------------------------------------------- claiming
    def _claim(self) -> str | None:
        with self._lock, get_sessionmaker()() as db:
            scan_id = db.scalar(select(Scan.id).where(Scan.status == "queued").order_by(Scan.queued_at).limit(1))
            if not scan_id:
                return None
            claimed = db.execute(update(Scan).where(Scan.id == scan_id, Scan.status == "queued").values(
                status="running", started_at=utcnow(), stage="acquire")).rowcount
            db.commit()
            return scan_id if claimed else None

    def _loop(self) -> None:
        while not self._stop.is_set():
            scan_id = self._claim()
            if scan_id is None:
                self._wake.wait(timeout=2.0)
                self._wake.clear()
                continue
            try:
                self._run(scan_id)
            except Exception:  # noqa: BLE001 - a runner thread must survive any single scan
                logger.exception("scan %s crashed the runner", scan_id)
                self._finish(scan_id, "failed", "The scan stopped unexpectedly. See the server log for details.")

    # -------------------------------------------------------------- running
    def _job(self, scan: Scan, source: Source) -> dict[str, Any]:
        settings = get_settings()
        options = dict(source.options or {})
        if source.kind == "image-registry" and settings.registry_username and settings.registry_password:
            options["credentials"] = [settings.registry_username, settings.registry_password.get_secret_value()]
        return {
            "scan_id": scan.id, "kind": source.kind, "locator": source.locator, "options": options,
            "workdir": str(settings.work_dir / scan.id),
            "limits": {"max_files": settings.scan_max_files, "max_file_bytes": settings.scan_max_file_mb * 1024 * 1024},
        }

    def _run(self, scan_id: str) -> None:
        settings = get_settings()
        session_factory = get_sessionmaker()
        with session_factory() as db:
            scan = db.get(Scan, scan_id)
            source = db.get(Source, scan.source_id) if scan else None
            if scan is None or source is None:
                return
            job = self._job(scan, source)
            system_id, source_id = scan.system_id, scan.source_id
        topic = scan_topic(scan_id)
        consolidator = Consolidator(session_factory, scan_id, system_id, source_id)
        from ...discovery.engine import worker_main

        context = mp.get_context("spawn")
        receiver, sender = context.Pipe(duplex=False)
        process = context.Process(target=worker_main, args=(job, sender), name=f"falcon-scan-{scan_id[:8]}", daemon=True)
        process.start()
        sender.close()
        deadline = time.monotonic() + settings.scan_timeout_minutes * 60
        coverage: dict[str, dict[str, int]] = {}
        state: dict[str, Any] = {"stage": "acquire"}
        last_write = 0.0
        outcome: tuple[str, str | None] | None = None
        stats: dict[str, Any] = {}
        with self._lock:
            self._live[scan_id] = {"state": state, "coverage": coverage, "consolidator": consolidator}
        hub.publish("scans", {"type": "scan", "scan_id": scan_id, "status": "running"})

        try:
            while outcome is None:
                with self._lock:
                    cancelled = scan_id in self._cancel
                if cancelled:
                    outcome = ("cancelled", "Cancelled by a user.")
                    break
                if self._stop.is_set():
                    outcome = ("cancelled", "Stopped because FALCON shut down.")
                    break
                if time.monotonic() > deadline:
                    outcome = ("failed", f"Stopped after the {settings.scan_timeout_minutes}-minute time limit.")
                    break
                if not receiver.poll(0.25):
                    if not process.is_alive() and not receiver.poll(0):
                        outcome = ("failed", f"The scan worker exited unexpectedly (code {process.exitcode}).")
                    continue
                try:
                    kind, payload = receiver.recv()
                except (EOFError, OSError):
                    outcome = ("failed", "The scan worker stopped without finishing.")
                    break

                if kind == "stage":
                    with self._lock:
                        state.update(stage=payload["stage"], stage_detail=payload.get("detail"))
                    hub.publish(topic, {"type": "stage", **payload})
                elif kind == "tree":
                    with self._lock:
                        for leaf in payload["leaves"]:
                            coverage[leaf["key"]] = {"files": leaf["files"], "bytes": leaf["bytes"], "scanned": 0, "findings": 0}
                        snapshot = {k: dict(v) for k, v in coverage.items()}
                    hub.publish(topic, {"type": "tree", "coverage": snapshot})
                elif kind == "progress":
                    # The engine reports deltas; subscribers receive absolute values for the
                    # directories that changed, so a replayed or duplicated event is harmless.
                    with self._lock:
                        touched: dict[str, dict[str, int]] = {}
                        for key, (scanned, found) in (payload.get("coverage") or {}).items():
                            leaf = coverage.setdefault(key, {"files": 0, "bytes": 0, "scanned": 0, "findings": 0})
                            leaf["scanned"] += scanned
                            leaf["findings"] += found
                            touched[key] = dict(leaf)
                        state.update(files_total=payload.get("files_total", 0), files_done=payload.get("files_done", 0),
                                     bytes_done=payload.get("bytes_done", 0))
                    hub.publish(topic, {"type": "progress", **{k: v for k, v in payload.items() if k != "coverage"}, "coverage": touched,
                                        "evidence": consolidator.evidence, "artefacts": len(consolidator.new_ids)})
                elif kind == "findings":
                    discovered = consolidator.ingest(payload)
                    if discovered:
                        hub.publish(topic, {"type": "discovered", "artefacts": discovered[:25], "total_new": len(consolidator.new_ids)})
                elif kind == "done":
                    stats = payload.get("stats") or {}
                    with self._lock:
                        state.update(files_total=payload.get("files_total", 0), files_done=payload.get("files_done", 0))
                    outcome = ("succeeded", None)
                elif kind == "error":
                    if payload.get("trace"):
                        logger.error("scan %s engine error:\n%s", scan_id, payload["trace"])
                    outcome = ("failed", payload.get("message", "The scan failed."))

                if time.monotonic() - last_write > 1.0 or outcome:
                    last_write = time.monotonic()
                    with session_factory() as db:
                        db.execute(update(Scan).where(Scan.id == scan_id).values(
                            stage=state.get("stage"), stage_detail=(state.get("stage_detail") or "")[:200] or None,
                            files_total=state.get("files_total", 0), files_done=state.get("files_done", 0),
                            bytes_done=state.get("bytes_done", 0), evidence_count=consolidator.evidence, coverage=coverage))
                        db.commit()
        finally:
            if process.is_alive():
                process.terminate()
                process.join(timeout=5)
            receiver.close()
            if job["kind"] != "directory":
                shutil.rmtree(job["workdir"], ignore_errors=True)
            with self._lock:
                self._cancel.discard(scan_id)
                self._live.pop(scan_id, None)

        status, error = outcome or ("failed", "The scan ended without a result.")
        self._finish(scan_id, status, error, consolidator=consolidator, stats=stats, coverage=coverage)

    def _finish(self, scan_id: str, status: str, error: str | None, *, consolidator: Consolidator | None = None,
                stats: dict[str, Any] | None = None, coverage: dict[str, Any] | None = None) -> None:
        with get_sessionmaker()() as db:
            scan = db.get(Scan, scan_id)
            if scan is None:
                return
            scan.status = status
            scan.error = error
            scan.finished_at = utcnow()
            scan.stage = "done" if status == "succeeded" else scan.stage
            if stats:
                scan.stats = stats
            if coverage is not None:
                scan.coverage = coverage
            if consolidator is not None:
                scan.evidence_count = consolidator.evidence
            db.flush()
            if status == "succeeded" and consolidator is not None:
                scan.artefact_count, scan.new_artefacts = consolidator.finalize(db)
            source = db.get(Source, scan.source_id)
            if source is not None:
                source.last_scan_id = scan.id
            label = source.name if source else "a source"
            summary = (f"Discovery of {label} found {scan.artefact_count} artefacts ({scan.new_artefacts} new)" if status == "succeeded"
                       else f"Discovery of {label} {status}: {error}")
            audit.append(db, action=f"scan.{status}", summary=summary, actor_label=ENGINE_ACTOR, target_type="scan",
                         target_id=scan.id, detail={"files": scan.files_total, "artefacts": scan.artefact_count,
                                                    "evidence": scan.evidence_count, "system_id": scan.system_id})
            db.commit()
            payload = {"type": "finished", "status": status, "error": error, "artefacts": scan.artefact_count,
                       "new_artefacts": scan.new_artefacts, "evidence": scan.evidence_count}
        hub.publish(scan_topic(scan_id), payload)
        hub.publish("scans", {"type": "scan", "scan_id": scan_id, "status": status})


runner = ScanRunner()
