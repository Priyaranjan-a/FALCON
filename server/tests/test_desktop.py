"""The desktop engine as the Tauri shell runs it: a real process on a real port."""
from __future__ import annotations

import os
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

import pytest

SERVER_DIR = Path(__file__).resolve().parents[1]


@pytest.fixture
def shell() -> subprocess.Popen:
    """Stands in for the desktop shell: the engine follows this process."""
    process = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(120)"])
    yield process
    process.kill()


def test_desktop_engine_serves_and_follows_its_parent(tmp_path: Path, shell: subprocess.Popen) -> None:
    env = {**os.environ, "FALCON_DESKTOP": "1", "FALCON_DATA_DIR": str(tmp_path), "FALCON_PORT": "0",
           "FALCON_ENVIRONMENT": "production", "FALCON_SECURE_COOKIES": "false",
           "FALCON_CONSOLE_DIST": str(tmp_path / "no-console"), "FALCON_PARENT_PID": str(shell.pid)}
    engine = subprocess.Popen([sys.executable, "-m", "falcon", "desktop"], cwd=SERVER_DIR, env=env,
                              stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    try:
        line = ""
        deadline = time.monotonic() + 60
        while time.monotonic() < deadline and not line.startswith("FALCON_READY"):
            line = engine.stdout.readline().strip() or line
            assert engine.poll() is None, f"engine exited early: {line}"
        url = line.split()[1]
        assert url.startswith("http://127.0.0.1:") and not url.endswith(":0")
        assert (tmp_path / "engine.json").exists() and (tmp_path / "logs" / "engine.log").exists()

        with urllib.request.urlopen(f"{url}/api/v1/setup", timeout=5) as response:
            body = response.read().replace(b" ", b"")
            assert response.status == 200 and b'"initialised":false' in body and b'"desktop":true' in body
        try:
            page = urllib.request.urlopen(f"{url}/", timeout=5)
        except urllib.error.HTTPError as missing:  # no console bundle in the test: the 404 still carries the policy
            page = missing
        assert "connect-src 'self' ipc: http://ipc.localhost" in page.headers["Content-Security-Policy"]
        with pytest.raises(urllib.error.HTTPError) as denied:
            urllib.request.urlopen(f"{url}/api/v1/discovery/capabilities", timeout=5)
        assert denied.value.code == 401  # the engine enforces sign-in like any server
    finally:
        # The shell goes away: the engine must shut itself down.
        shell.kill()
        try:
            engine.wait(timeout=30)
        except subprocess.TimeoutExpired:
            engine.kill()
            raise AssertionError("the desktop engine outlived its shell")
    assert engine.returncode == 0


def test_desktop_csp_allows_the_ipc_channel_only_in_desktop_mode() -> None:
    from falcon.kernel.http import content_security_policy

    assert "ipc: http://ipc.localhost" in content_security_policy(True)
    assert "connect-src 'self';" in content_security_policy(False)
