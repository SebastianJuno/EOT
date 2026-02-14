# -*- mode: python ; coding: utf-8 -*-
from pathlib import Path
import plistlib
from PyInstaller.utils.hooks import collect_submodules

SPEC_DIR = Path(SPECPATH).resolve()
ROOT = SPEC_DIR.parent
plist_path = SPEC_DIR / "Info.plist"

required_paths = {
    ROOT / "backend": "Missing backend folder. Confirm repo checkout is complete.",
    ROOT / "frontend": "Missing frontend folder. Confirm repo checkout is complete.",
    ROOT / "java-parser": "Missing java-parser folder. Confirm repo checkout is complete.",
    plist_path: "Missing desktop/Info.plist. Confirm desktop packaging assets exist.",
    ROOT / "config" / "VERSION": "Missing config/VERSION file. Confirm release metadata exists.",
}
for path, hint in required_paths.items():
    if not path.exists():
        raise SystemExit(f"Missing required path: {path}\nHint: {hint}")

info_plist = plistlib.loads(plist_path.read_bytes())
version = (ROOT / "config" / "VERSION").read_text(encoding="utf-8").strip().lstrip("v")
if version.count(".") != 2:
    raise SystemExit(f"Invalid config/VERSION value: {version!r}. Expected semantic version (e.g. 0.1.0).")
info_plist["CFBundleShortVersionString"] = version
info_plist["CFBundleVersion"] = version

hiddenimports = []
hiddenimports += collect_submodules("uvicorn")
hiddenimports += collect_submodules("fastapi")
hiddenimports += collect_submodules("reportlab")
hiddenimports += collect_submodules("webview")

jar_path = ROOT / "java-parser" / "target" / "mpp-extractor-1.0.0-jar-with-dependencies.jar"
if not jar_path.exists():
    raise SystemExit(
        f"Missing parser jar: {jar_path}. Run 'make -f scripts/Makefile build-parser' before packaging."
    )

a = Analysis(
    [str(SPEC_DIR / "main.py")],
    pathex=[str(ROOT)],
    binaries=[],
    datas=[
        (str(ROOT / "backend"), "backend"),
        (str(ROOT / "frontend"), "frontend"),
        (str(ROOT / "java-parser"), "java-parser"),
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
    [],
    exclude_binaries=True,
    name="EOT Diff Tool",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name="EOT Diff Tool",
)

app = BUNDLE(
    coll,
    name="EOT Diff Tool.app",
    icon=None,
    bundle_identifier="local.eotdiff.tool",
    info_plist=info_plist,
)
