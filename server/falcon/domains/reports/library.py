"""Where exported files go.

* **Desktop app.** Files are written straight to a folder on the user's own
  machine: by default ``Downloads\\FALCON Exports``, or wherever they choose.
  FALCON can reveal a file in Explorer (Finder on macOS). The webview never
  has to handle a download.
* **Server.** Files are kept in FALCON's own library (``<data>/exports``) and
  downloaded by the browser, so every export can be fetched again later, byte
  for byte. The folder cannot be changed from the console, so a web user can
  never make the server write elsewhere.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import threading
from pathlib import Path

from ...kernel.problems import Problem
from ...settings import get_settings

_lock = threading.Lock()
_ILLEGAL = str.maketrans({c: "-" for c in '<>:"/\\|?*'})


def _preferences_path() -> Path:
    return get_settings().data_dir / "preferences.json"


def _preferences() -> dict:
    try:
        return json.loads(_preferences_path().read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def _downloads_dir() -> Path:
    """The user's Downloads folder, honouring Windows folder redirection."""
    if sys.platform == "win32":
        try:
            import ctypes
            from ctypes import wintypes

            class GUID(ctypes.Structure):
                _fields_ = [("Data1", wintypes.DWORD), ("Data2", wintypes.WORD), ("Data3", wintypes.WORD), ("Data4", ctypes.c_ubyte * 8)]

            # FOLDERID_Downloads {374DE290-123F-4565-9164-39C4925E467B}
            fid = GUID(0x374DE290, 0x123F, 0x4565, (ctypes.c_ubyte * 8)(0x91, 0x64, 0x39, 0xC4, 0x92, 0x5E, 0x46, 0x7B))
            out = ctypes.c_wchar_p()
            if ctypes.windll.shell32.SHGetKnownFolderPath(ctypes.byref(fid), 0, None, ctypes.byref(out)) == 0:
                path = Path(out.value)
                ctypes.windll.ole32.CoTaskMemFree(out)
                return path
        except (OSError, AttributeError):  # pragma: no cover - platform dependent
            pass
    return Path.home() / "Downloads"


def default_location() -> Path:
    settings = get_settings()
    if settings.desktop:
        return _downloads_dir() / "FALCON Exports"
    return settings.data_dir / "exports"


def location() -> Path:
    if get_settings().desktop:
        chosen = _preferences().get("export_dir")
        if chosen:
            return Path(chosen)
    return default_location()


def describe() -> dict:
    here = location()
    return {
        "path": str(here),
        "default": str(default_location()),
        "custom": here != default_location(),
        "desktop": get_settings().desktop,
        "exists": here.is_dir(),
    }


def require_desktop() -> None:
    if not get_settings().desktop:
        raise Problem(409, "Choosing a folder and showing files in it are available in the FALCON desktop app. "
                           "On a server, exports download through your browser.", code="desktop_only")


def set_location(path: str) -> dict:
    require_desktop()
    target = Path(path).expanduser()
    if not target.is_absolute():
        raise Problem(422, "Choose a full folder path.", code="location_invalid",
                      errors=[{"field": "path", "message": "Not an absolute path"}])
    try:
        target.mkdir(parents=True, exist_ok=True)
        probe = target / ".falcon-write-test"
        probe.write_bytes(b"")
        probe.unlink()
    except OSError:
        raise Problem(422, "FALCON cannot write to that folder. Choose another one.", code="location_unwritable",
                      errors=[{"field": "path", "message": "Not writable"}]) from None
    with _lock:
        prefs = _preferences()
        prefs["export_dir"] = str(target)
        _preferences_path().write_text(json.dumps(prefs, indent=2), encoding="utf-8")
    return describe()


def reset_location() -> dict:
    require_desktop()
    with _lock:
        prefs = _preferences()
        prefs.pop("export_dir", None)
        _preferences_path().write_text(json.dumps(prefs, indent=2), encoding="utf-8")
    return describe()


def _unique(folder: Path, filename: str) -> Path:
    """``name.ext``, then ``name (2).ext``, as Finder and Explorer do."""
    filename = filename.translate(_ILLEGAL).strip(" .") or "falcon-export"
    candidate = folder / filename
    stem, dot, ext = filename.partition(".")
    n = 2
    while candidate.exists():
        candidate = folder / f"{stem} ({n}){dot}{ext}"
        n += 1
    return candidate


def write(filename: str, data: bytes) -> Path:
    folder = location()
    try:
        folder.mkdir(parents=True, exist_ok=True)
    except OSError:
        raise Problem(422, f"The export folder {folder} cannot be created. Choose another folder.", code="location_unwritable") from None
    with _lock:
        target = _unique(folder, filename)
        tmp = target.with_name(target.name + ".partial")
        try:
            tmp.write_bytes(data)
            os.replace(tmp, target)
        except OSError:
            tmp.unlink(missing_ok=True)
            raise Problem(422, f"FALCON could not write to {folder}. Check the folder, or choose another.", code="location_unwritable") from None
    return target


def _launch(args: list[str]) -> None:
    flags = getattr(subprocess, "CREATE_NO_WINDOW", 0) if sys.platform == "win32" and args[0] != "explorer.exe" else 0
    subprocess.Popen(args, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                     close_fds=True, creationflags=flags)


def reveal(path: Path) -> None:
    """Shows a file in Explorer or Finder, selected."""
    require_desktop()
    if not path.exists():
        raise Problem(404, "The file is no longer there. It may have been moved or deleted.", code="export_missing")
    if sys.platform == "win32":
        _launch(["explorer.exe", f"/select,{path}"])
    elif sys.platform == "darwin":
        _launch(["open", "-R", str(path)])
    elif shutil.which("dbus-send"):
        # The freedesktop file-manager interface (Nautilus, Dolphin, Nemo, Caja) selects the file.
        _launch(["dbus-send", "--session", "--dest=org.freedesktop.FileManager1", "--type=method_call",
                 "/org/freedesktop/FileManager1", "org.freedesktop.FileManager1.ShowItems",
                 f"array:string:{path.as_uri()}", "string:"])
    else:
        _launch(["xdg-open", str(path.parent)])


def open_folder() -> dict:
    require_desktop()
    folder = location()
    folder.mkdir(parents=True, exist_ok=True)
    if sys.platform == "win32":
        _launch(["explorer.exe", str(folder)])
    elif sys.platform == "darwin":
        _launch(["open", str(folder)])
    else:
        _launch(["xdg-open", str(folder)])
    return describe()
