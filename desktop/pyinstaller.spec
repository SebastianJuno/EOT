# -*- mode: python ; coding: utf-8 -*-
from pathlib import Path
import plistlib
from PyInstaller.utils.hooks import collect_submodules

ROOT = Path.cwd()
plist_path = ROOT / "desktop" / "Info.plist"
info_plist = plistlib.loads(plist_path.read_bytes())

hiddenimports = []
hiddenimports += collect_submodules("uvicorn")
hiddenimports += collect_submodules("fastapi")
hiddenimports += collect_submodules("reportlab")
hiddenimports += collect_submodules("webview")

jar_path = ROOT / "java-parser" / "target" / "mpp-extractor-1.0.0-jar-with-dependencies.jar"
if not jar_path.exists():
    raise SystemExit(
        f"Missing parser jar: {jar_path}. Run 'make build-parser' before packaging."
    )

a = Analysis(
    ["desktop/main.py"],
    pathex=[str(ROOT)],
    binaries=[],
    datas=[
        ("backend", "backend"),
        ("frontend", "frontend"),
        ("java-parser", "java-parser"),
    ],
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name="EOT Diff Tool",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
)

app = BUNDLE(
    exe,
    name="EOT Diff Tool.app",
    icon=None,
    bundle_identifier="local.eotdiff.tool",
    info_plist=info_plist,
)
