# PyInstaller build of the FALCON engine for the desktop app.
#   pyinstaller desktop/engine/falcon-engine.spec --distpath server/dist --workpath server/build/pyinstaller
# Produces server/dist/falcon-engine/ (one folder), which the Tauri bundle ships as resources/engine.
from pathlib import Path

from PyInstaller.utils.hooks import collect_submodules

ROOT = Path(SPECPATH).resolve().parents[1]
SERVER = ROOT / "server"
PACKAGE = SERVER / "falcon"

# Data read from disk at run time: the algorithm and library knowledge base, rule
# packs, and the migration scripts Alembic loads by path.
datas = [
    (str(PACKAGE / "knowledge"), "falcon/knowledge"),
    (str(PACKAGE / "migrations"), "falcon/migrations"),
]

hiddenimports = (
    collect_submodules("falcon")
    + collect_submodules("uvicorn")
    + ["_argon2_cffi_bindings", "_cffi_backend", "sqlalchemy.dialects.sqlite"]
)

a = Analysis(
    [str(Path(SPECPATH) / "entry.py")],
    pathex=[str(SERVER)],
    datas=datas,
    hiddenimports=hiddenimports,
    excludes=["tkinter", "pytest", "_pytest", "httpx2", "IPython", "matplotlib", "numpy"],
    noarchive=False,
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="falcon-engine",
    icon=str(ROOT / "desktop" / "src-tauri" / "icons" / "icon.ico"),
    console=False,  # no console window for the engine or its scan workers
    disable_windowed_traceback=True,
    upx=False,
)
coll = COLLECT(exe, a.binaries, a.datas, name="falcon-engine", upx=False)
