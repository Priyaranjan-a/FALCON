"""Deep workspaces: unpacked container images nest past Windows' historical
260-character path limit (a layer digest alone is 64 characters)."""
from __future__ import annotations

import io
import tarfile
from pathlib import Path

from falcon.discovery import engine, workspace

IMAGE = Path(__file__).resolve().parents[2] / "fixtures" / "images" / "payments-api-3.8.1.tar"


def _run(job: engine.Job) -> tuple[dict, list[dict]]:
    findings: list[dict] = []
    stats = engine.run(job, lambda kind, payload: findings.extend(payload) if kind == "findings" else None)
    return stats, findings


def test_image_scan_in_a_deep_workspace(tmp_path: Path) -> None:
    # A data folder deep in a user profile, plus the scan id: the layer paths pass 260 characters.
    deep = tmp_path / ("falcon-data-" + "d" * 140)
    deep.mkdir()
    job = engine.Job(scan_id="t", kind="image-archive", locator=str(IMAGE), workdir=str(deep / "work" / ("0" * 36)))
    stats, findings = _run(job)
    assert stats["files"] > 0 and findings, "the image must be unpacked and analysed"
    assert all(not f["evidence"]["path"].startswith(("\\\\?\\", "/", "C:")) for f in findings), "evidence stays relative"
    assert not Path(job.workdir).exists(), "the workspace is removed afterwards"


def test_archive_with_very_long_member_paths(tmp_path: Path) -> None:
    nested = "/".join(["component-" + str(i) * 12 for i in range(14)])  # about 330 characters
    buffer = io.BytesIO()
    with tarfile.open(fileobj=buffer, mode="w") as tf:
        body = b"import hashlib\nhashlib.md5(b'x').hexdigest()\n"
        info = tarfile.TarInfo(f"{nested}/legacy.py")
        info.size = len(body)
        tf.addfile(info, io.BytesIO(body))
    archive = tmp_path / "deep.tar"
    archive.write_bytes(buffer.getvalue())
    stats, findings = _run(engine.Job(scan_id="t", kind="archive", locator=str(archive), workdir=str(tmp_path / "work")))
    assert stats["files"] == 1
    assert any(f["name"] == "MD5" and f["evidence"]["path"].endswith("legacy.py") for f in findings)


def test_extended_path_is_a_windows_only_prefix(tmp_path: Path) -> None:
    extended = workspace.extended_path(tmp_path)
    if str(extended).startswith("\\\\?\\"):
        assert str(extended).endswith(str(tmp_path).lstrip("\\"))
        assert workspace.extended_path(extended) == extended  # idempotent
    else:
        assert extended == tmp_path
