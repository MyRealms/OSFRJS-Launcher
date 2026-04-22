# -*- mode: python ; coding: utf-8 -*-

from pathlib import Path

root = Path(SPECPATH)

datas = []
for source, target in [
    (root / "assets", "assets"),
    (root / "PDF", "PDF"),
    (root / "local_server", "local_server"),
    (root.parent / "pptx_media_extract", "pptx_media_extract"),
    (root / "launcher.ico", "."),
    (root / "FreeRealms.ttf", "."),
]:
    if source.exists():
        datas.append((str(source), target))

a = Analysis(
    ["launcher_ui.py"],
    pathex=[str(root)],
    binaries=[],
    datas=datas,
    hiddenimports=["pypresence"],
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
    name="FreeRealmsJSLauncher",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=str(root / "launcher.ico"),
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name="FreeRealmsJSLauncher",
)
