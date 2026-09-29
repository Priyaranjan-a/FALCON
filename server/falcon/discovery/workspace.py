"""Materialise a source into a local directory the detectors can read.

Everything here treats its input as hostile:

* Archives: entries may not escape the extraction root, links and device files
  are skipped, and total size, entry count and compression ratio are bounded.
* Git: shallow clone with hooks, credential prompts, symlinks, submodules and
  the ``file://`` transport disabled, under a hard timeout.
* Container images: layers are applied in order with OCI whiteouts; a registry
  pull uses the Docker Registry v2 API with bearer-token authentication.
"""
from __future__ import annotations

import io
import json
import os
import re
import shutil
import subprocess
import tarfile
import urllib.error
import urllib.parse
import urllib.request
import zipfile
from dataclasses import dataclass, field
from pathlib import Path, PurePosixPath
from typing import Any, Callable


class AcquisitionError(Exception):
    """The source could not be materialised; the message is safe to show users."""


@dataclass
class Limits:
    max_total_bytes: int = 4 * 1024**3
    max_entries: int = 250_000
    max_ratio: int = 200  # uncompressed : compressed
    git_timeout: int = 300
    registry_timeout: int = 60


@dataclass
class Workspace:
    root: Path
    facts: dict[str, Any] = field(default_factory=dict)


def extended_path(path: Path) -> Path:
    """On Windows, the extended-length form (``\\\\?\\C:\\...``) of a path.

    Unpacked images and deep repositories easily exceed Windows' historical
    260-character limit (a layer digest alone is 64 characters). The ``\\\\?\\``
    prefix lifts the limit for every file operation. Elsewhere, the path is
    returned unchanged.
    """
    if os.name != "nt":
        return path
    text = str(path)
    if text.startswith("\\\\?\\"):
        return path
    absolute = os.path.abspath(text)
    if absolute.startswith("\\\\"):  # UNC share: \\server\share -> \\?\UNC\server\share
        return Path("\\\\?\\UNC\\" + absolute[2:])
    return Path("\\\\?\\" + absolute)


def _safe_member(name: str) -> PurePosixPath | None:
    path = PurePosixPath(name.replace("\\", "/"))
    if path.is_absolute() or ".." in path.parts or not path.parts:
        return None
    if re.match(r"^[A-Za-z]:", path.parts[0]):
        return None
    return path


def extract_zip(archive: Path, dest: Path, limits: Limits) -> int:
    total = 0
    count = 0
    try:
        zf = zipfile.ZipFile(archive)
    except zipfile.BadZipFile:
        raise AcquisitionError("The archive is not a valid zip file.")
    with zf:
        for info in zf.infolist():
            if info.is_dir():
                continue
            member = _safe_member(info.filename)
            if member is None:
                continue
            # Unix mode bits in the high word: skip symbolic links.
            if (info.external_attr >> 16) & 0o170000 == 0o120000:
                continue
            count += 1
            total += info.file_size
            if count > limits.max_entries or total > limits.max_total_bytes:
                raise AcquisitionError("The archive is larger than the scan limits allow.")
            if info.compress_size and info.file_size / max(info.compress_size, 1) > limits.max_ratio:
                raise AcquisitionError("The archive has a suspicious compression ratio and was rejected.")
            target = dest.joinpath(*member.parts)
            target.parent.mkdir(parents=True, exist_ok=True)
            with zf.open(info) as src, target.open("wb") as out:
                shutil.copyfileobj(src, out, 1024 * 1024)
    return count


def extract_tar(source: Path | io.BufferedIOBase, dest: Path, limits: Limits, *, whiteouts: bool = False, budget: list[int] | None = None) -> int:
    """Extract a (possibly compressed) tar. ``budget`` carries [bytes, entries] across layers."""
    budget = budget if budget is not None else [0, 0]
    try:
        tf = tarfile.open(source, mode="r:*") if isinstance(source, Path) else tarfile.open(fileobj=source, mode="r|*")
    except tarfile.TarError:
        raise AcquisitionError("The archive is not a readable tar file.")
    count = 0
    with tf:
        for member in tf:
            path = _safe_member(member.name)
            if path is None:
                continue
            name = path.name
            if whiteouts and name.startswith(".wh."):
                target_dir = dest.joinpath(*path.parent.parts)
                if name == ".wh..wh..opq":
                    if target_dir.is_dir():
                        for child in target_dir.iterdir():
                            shutil.rmtree(child, ignore_errors=True) if child.is_dir() else child.unlink(missing_ok=True)
                else:
                    victim = target_dir / name[4:]
                    if victim.is_dir() and not victim.is_symlink():
                        shutil.rmtree(victim, ignore_errors=True)
                    else:
                        victim.unlink(missing_ok=True)
                continue
            target = dest.joinpath(*path.parts)
            if member.isdir():
                target.mkdir(parents=True, exist_ok=True)
                continue
            if not member.isfile():
                continue  # links, devices and FIFOs are never materialised
            budget[0] += member.size
            budget[1] += 1
            if budget[1] > limits.max_entries or budget[0] > limits.max_total_bytes:
                raise AcquisitionError("The archive is larger than the scan limits allow.")
            fileobj = tf.extractfile(member)
            if fileobj is None:
                continue
            target.parent.mkdir(parents=True, exist_ok=True)
            if target.is_symlink():
                target.unlink()
            with target.open("wb") as out:
                shutil.copyfileobj(fileobj, out, 1024 * 1024)
            count += 1
    return count


def extract_archive(archive: Path, dest: Path, limits: Limits) -> int:
    dest.mkdir(parents=True, exist_ok=True)
    if zipfile.is_zipfile(archive):
        return extract_zip(archive, dest, limits)
    return extract_tar(archive, dest, limits)


# ------------------------------------------------------------------------ git

_GIT_URL = re.compile(r"^(https://|ssh://|git@)[\w.@:/~+-]+?(\.git)?/?$")


def validate_git_url(url: str) -> str:
    url = url.strip()
    if not _GIT_URL.match(url):
        raise AcquisitionError("Use an https:// or ssh:// Git URL (for example https://git.example.org/team/app.git).")
    return url


def clone(url: str, dest: Path, ref: str | None, limits: Limits) -> dict[str, Any]:
    git = shutil.which("git")
    if not git:
        raise AcquisitionError("Git is not installed on the FALCON server, so repositories cannot be cloned.")
    validate_git_url(url)
    if ref and not re.match(r"^[\w./-]{1,200}$", ref):
        raise AcquisitionError("The branch or tag name contains unsupported characters.")
    templates = dest.parent / "git-template"
    templates.mkdir(parents=True, exist_ok=True)
    cmd = [
        git, "-c", "protocol.file.allow=never", "-c", "core.symlinks=false", "-c", "core.fsmonitor=false", "-c", "core.longpaths=true",
        "-c", "core.hooksPath=" + str(templates), "-c", "submodule.recurse=false", "-c", "credential.helper=",
        "clone", "--depth", "1", "--single-branch", "--no-tags", "--no-recurse-submodules",
        "--template", str(templates),
    ]
    if ref:
        cmd += ["--branch", ref]
    cmd += ["--", url, str(dest)]
    env = {**os.environ, "GIT_TERMINAL_PROMPT": "0", "GIT_ASKPASS": "", "SSH_ASKPASS": "", "GIT_CONFIG_NOSYSTEM": "1",
           "GIT_SSH_COMMAND": "ssh -o BatchMode=yes -o StrictHostKeyChecking=accept-new"}
    try:
        result = subprocess.run(cmd, env=env, capture_output=True, text=True, timeout=limits.git_timeout)
    except subprocess.TimeoutExpired:
        raise AcquisitionError(f"Cloning took longer than {limits.git_timeout} seconds and was stopped.")
    if result.returncode != 0:
        message = (result.stderr or result.stdout).strip().splitlines()
        detail = next((line for line in reversed(message) if line.startswith(("fatal:", "error:"))), message[-1] if message else "")
        raise AcquisitionError(f"Git could not clone the repository. {detail.removeprefix('fatal: ')}".strip())
    head = subprocess.run([git, "-C", str(dest), "rev-parse", "HEAD"], capture_output=True, text=True, timeout=30)
    shutil.rmtree(dest / ".git", ignore_errors=True)
    return {"commit": head.stdout.strip() or None, "ref": ref}


# --------------------------------------------------------------------- images

def unpack_image_tar(archive: Path, dest: Path, limits: Limits) -> dict[str, Any]:
    """Apply the layers of a ``docker save`` or OCI image-layout tarball."""
    staging = dest.parent / "image-staging"
    staging.mkdir(parents=True, exist_ok=True)
    extract_tar(archive, staging, limits)
    rootfs = dest
    rootfs.mkdir(parents=True, exist_ok=True)
    layers: list[Path] = []
    facts: dict[str, Any] = {}
    manifest_path = staging / "manifest.json"
    index_path = staging / "index.json"
    if manifest_path.exists():
        manifest = json.loads(manifest_path.read_text("utf-8"))[0]
        layers = [staging / p for p in manifest.get("Layers", [])]
        facts["tags"] = manifest.get("RepoTags") or []
        config = staging / manifest.get("Config", "")
        if config.is_file():
            facts.update(_image_config(json.loads(config.read_text("utf-8"))))
    elif index_path.exists():
        index = json.loads(index_path.read_text("utf-8"))
        descriptor = _pick_platform(index.get("manifests", []))
        manifest = _oci_blob_json(staging, descriptor["digest"])
        if "manifests" in manifest:
            manifest = _oci_blob_json(staging, _pick_platform(manifest["manifests"])["digest"])
        layers = [_oci_blob_path(staging, layer["digest"]) for layer in manifest.get("layers", [])]
        facts.update(_image_config(_oci_blob_json(staging, manifest["config"]["digest"])))
    else:
        raise AcquisitionError("The tarball is not a container image (no manifest.json or index.json).")
    budget = [0, 0]
    for layer in layers:
        extract_tar(layer, rootfs, limits, whiteouts=True, budget=budget)
    facts["layers"] = len(layers)
    shutil.rmtree(staging, ignore_errors=True)
    return facts


def _oci_blob_path(root: Path, digest: str) -> Path:
    algorithm, _, value = digest.partition(":")
    return root / "blobs" / algorithm / value


def _oci_blob_json(root: Path, digest: str) -> dict[str, Any]:
    return json.loads(_oci_blob_path(root, digest).read_text("utf-8"))


def _pick_platform(manifests: list[dict[str, Any]]) -> dict[str, Any]:
    for m in manifests:
        platform = m.get("platform", {})
        if platform.get("os", "linux") == "linux" and platform.get("architecture", "amd64") == "amd64":
            return m
    if not manifests:
        raise AcquisitionError("The image index lists no manifests.")
    return manifests[0]


def _image_config(config: dict[str, Any]) -> dict[str, Any]:
    cfg = config.get("config") or {}
    return {
        "os": config.get("os"), "architecture": config.get("architecture"), "created": config.get("created"),
        "labels": cfg.get("Labels") or {}, "entrypoint": cfg.get("Entrypoint"),
        "env_names": [e.split("=", 1)[0] for e in cfg.get("Env") or []],
    }


_IMAGE_REF = re.compile(r"^(?:(?P<registry>[\w.-]+(?::\d+)?)/)?(?P<repo>[a-z0-9]+(?:[._/-][a-z0-9]+)*)(?::(?P<tag>[\w][\w.-]{0,127}))?(?:@(?P<digest>sha256:[a-f0-9]{64}))?$")


def parse_image_ref(ref: str) -> tuple[str, str, str]:
    """Returns (registry host, repository, tag-or-digest)."""
    m = _IMAGE_REF.match(ref.strip())
    if not m:
        raise AcquisitionError("Use an image reference such as registry.example.org/team/app:1.4.2.")
    registry, repo = m.group("registry"), m.group("repo")
    if registry and "." not in registry and ":" not in registry and registry != "localhost":
        repo, registry = f"{registry}/{repo}", None
    registry = registry or "registry-1.docker.io"
    if registry == "registry-1.docker.io" and "/" not in repo:
        repo = f"library/{repo}"
    return registry, repo, m.group("digest") or m.group("tag") or "latest"


_ACCEPT = ", ".join([
    "application/vnd.oci.image.index.v1+json", "application/vnd.oci.image.manifest.v1+json",
    "application/vnd.docker.distribution.manifest.list.v2+json", "application/vnd.docker.distribution.manifest.v2+json",
])


class _Registry:
    def __init__(self, host: str, repo: str, timeout: int, credentials: tuple[str, str] | None) -> None:
        self.base = f"https://{host}/v2/{repo}"
        self.repo = repo
        self.timeout = timeout
        self.credentials = credentials
        self.token: str | None = None

    def _request(self, url: str, accept: str | None = None):
        headers = {"User-Agent": "FALCON-discovery"}
        if accept:
            headers["Accept"] = accept
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        try:
            return urllib.request.urlopen(urllib.request.Request(url, headers=headers), timeout=self.timeout)
        except urllib.error.HTTPError as err:
            if err.code == 401 and not self.token:
                self._authenticate(err.headers.get("WWW-Authenticate", ""))
                return self._request(url, accept)
            raise AcquisitionError(f"The registry refused the request ({err.code}).")
        except urllib.error.URLError as err:
            raise AcquisitionError(f"The registry could not be reached ({err.reason}).")

    def _authenticate(self, challenge: str) -> None:
        params = dict(re.findall(r'(\w+)="([^"]*)"', challenge))
        realm = params.pop("realm", None)
        if not realm:
            raise AcquisitionError("The registry requires authentication FALCON does not support.")
        params.setdefault("scope", f"repository:{self.repo}:pull")
        request = urllib.request.Request(f"{realm}?{urllib.parse.urlencode(params)}", headers={"User-Agent": "FALCON-discovery"})
        if self.credentials:
            import base64

            basic = base64.b64encode(f"{self.credentials[0]}:{self.credentials[1]}".encode()).decode()
            request.add_header("Authorization", f"Basic {basic}")
        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                body = json.loads(response.read())
        except (urllib.error.URLError, ValueError):
            raise AcquisitionError("The registry token service could not be reached.")
        self.token = body.get("token") or body.get("access_token")

    def manifest(self, reference: str) -> dict[str, Any]:
        with self._request(f"{self.base}/manifests/{reference}", _ACCEPT) as response:
            return json.loads(response.read())

    def blob(self, digest: str):
        return self._request(f"{self.base}/blobs/{digest}")


def pull_image(ref: str, dest: Path, limits: Limits, credentials: tuple[str, str] | None = None,
               progress: Callable[[str], None] | None = None) -> dict[str, Any]:
    host, repo, reference = parse_image_ref(ref)
    registry = _Registry(host, repo, limits.registry_timeout, credentials)
    manifest = registry.manifest(reference)
    if "manifests" in manifest:
        manifest = registry.manifest(_pick_platform(manifest["manifests"])["digest"])
    with registry.blob(manifest["config"]["digest"]) as response:
        facts = _image_config(json.loads(response.read()))
    dest.mkdir(parents=True, exist_ok=True)
    budget = [0, 0]
    layers = manifest.get("layers", [])
    for i, layer in enumerate(layers, 1):
        if progress:
            progress(f"Downloading layer {i} of {len(layers)}")
        media = layer.get("mediaType", "")
        if "zstd" in media:
            raise AcquisitionError("The image uses zstd-compressed layers, which this build cannot read.")
        with registry.blob(layer["digest"]) as response:
            # Streaming tar mode detects and decompresses gzip layers itself.
            extract_tar(response, dest, limits, whiteouts=True, budget=budget)
    facts.update(registry=host, repository=repo, reference=reference, layers=len(layers))
    return facts
