"""FALCON as desktop software: the engine behind the native app.

The desktop shell (``desktop/``, Tauri) starts this with ``falcon desktop``,
chooses the port and data folder through ``FALCON_*`` variables, waits until
the API answers, then opens the console in a native window.

* Loopback only, on the port the shell chose (``FALCON_PORT``; 0 picks one).
* Readiness is announced on stdout (``FALCON_READY <url>``) and in
  ``<data>/engine.json`` for diagnostics; the shell itself polls the API.
* The engine follows its parent: when the shell exits, however it exits, the
  engine shuts down gracefully (stopping any scan) instead of lingering.
* Logs go to ``<data>/logs/engine.log`` (rotated), since there is no console.
"""
from __future__ import annotations

import json
import logging
import logging.handlers
import os
import socket
import sys
import threading
import time

from .settings import get_settings

logger = logging.getLogger("falcon.desktop")
GRACE_SECONDS = 15


def _configure_logging() -> None:
    logs = get_settings().data_dir / "logs"
    logs.mkdir(parents=True, exist_ok=True)
    handler = logging.handlers.RotatingFileHandler(logs / "engine.log", maxBytes=2_000_000, backupCount=3, encoding="utf-8")
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)-7s %(name)s  %(message)s"))
    root = logging.getLogger()
    root.addHandler(handler)
    root.setLevel(logging.INFO)


def _wait_for_exit(pid: int) -> None:
    """Block until process ``pid`` has exited."""
    if sys.platform == "win32":
        import ctypes

        synchronize, infinite = 0x00100000, 0xFFFFFFFF
        kernel32 = ctypes.windll.kernel32
        handle = kernel32.OpenProcess(synchronize, False, pid)
        if not handle:
            return  # already gone
        try:
            kernel32.WaitForSingleObject(handle, infinite)
        finally:
            kernel32.CloseHandle(handle)
    else:
        # The shell is normally our parent (re-parenting tells us it is gone); any other
        # process is watched directly, treating a zombie as exited.
        direct_parent = os.getppid() == pid
        while _alive(pid) and not (direct_parent and os.getppid() != pid):
            time.sleep(1)


def _alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True  # exists, owned by another user
    try:
        with open(f"/proc/{pid}/stat", encoding="ascii") as stat:
            state = stat.read().rsplit(")", 1)[1].split()[0]
        return state not in ("Z", "X")  # zombie or dead: exited, not yet reaped
    except (OSError, IndexError):
        return True  # no /proc (macOS): kill(0) succeeding means it is running


def _follow_parent(pid: int, server: "uvicorn.Server") -> None:  # noqa: F821
    _wait_for_exit(pid)
    logger.info("desktop shell (pid %s) exited; shutting down", pid)
    server.should_exit = True
    time.sleep(GRACE_SECONDS)
    logger.warning("graceful shutdown overran %ss; exiting", GRACE_SECONDS)
    os._exit(0)


def _announce(url: str, server: "uvicorn.Server") -> None:  # noqa: F821
    while not server.started and not server.should_exit:
        time.sleep(0.05)
    if server.should_exit:
        return
    settings = get_settings()
    (settings.data_dir / "engine.json").write_text(json.dumps({"url": url, "pid": os.getpid()}), encoding="utf-8")
    logger.info("FALCON desktop engine ready at %s (data in %s)", url, settings.data_dir)
    if sys.stdout is not None:
        try:
            print(f"FALCON_READY {url}", flush=True)
        except OSError:
            pass


def run() -> int:
    import uvicorn

    from .app import create_app

    settings = get_settings()
    if not settings.desktop:
        raise SystemExit("falcon desktop is started by the desktop shell (FALCON_DESKTOP=1).")
    _configure_logging()

    listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    if sys.platform == "win32":
        listener.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
    try:
        listener.bind(("127.0.0.1", settings.port))
    except OSError as err:
        logger.error("cannot listen on 127.0.0.1:%s: %s", settings.port, err)
        return 3
    port = listener.getsockname()[1]
    url = f"http://127.0.0.1:{port}"

    config = uvicorn.Config(create_app(), log_level="warning", log_config=None, proxy_headers=False, server_header=False, access_log=False)
    server = uvicorn.Server(config)
    parent = os.environ.get("FALCON_PARENT_PID")
    if parent and parent.isdigit():
        threading.Thread(target=_follow_parent, args=(int(parent), server), name="falcon-parent", daemon=True).start()
    threading.Thread(target=_announce, args=(url, server), name="falcon-announce", daemon=True).start()
    server.run(sockets=[listener])
    return 0
