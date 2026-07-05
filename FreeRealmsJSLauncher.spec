# -*- mode: python ; coding: utf-8 -*-
#
# Build mode is selected by the ``OSFR_BUILD_MODE`` environment variable
# (default: ``onedir``). ``build_launcher_onedir.bat`` and
# ``build_launcher_onefile.bat`` set this variable before invoking
# PyInstaller, so a single spec file produces both layouts without
# duplicating the Analysis / PYZ / data / icon configuration.
#
#   set OSFR_BUILD_MODE=onedir  -> dist\FreeRealmsJSLauncher\FreeRealmsJSLauncher.exe
#   set OSFR_BUILD_MODE=onefile -> dist\FreeRealmsJSLauncher.exe (single file)

import os
from pathlib import Path

from PyInstaller.utils.hooks import collect_all

root = Path(SPECPATH)
build_mode = os.environ.get("OSFR_BUILD_MODE", "onedir").strip().lower()
if build_mode not in {"onedir", "onefile"}:
    raise SystemExit(f"OSFR_BUILD_MODE must be 'onedir' or 'onefile' (got {build_mode!r})")
is_onefile = build_mode == "onefile"

datas = []
binaries = []
# ``pypresence`` is imported optionally in ``discord_presence.py`` (the
# import is wrapped in a try/except). Listing it under hiddenimports
# would force PyInstaller to bundle a module that may not actually be
# installed; a missing module then generates a confusing
# "Hidden import pypresence not found!" build warning. Skip it.
hiddenimports = []

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

for package_name in ("PySide6", "shiboken6"):
    package_datas, package_binaries, package_hiddenimports = collect_all(package_name)
    datas += package_datas
    binaries += package_binaries
    hiddenimports += package_hiddenimports

a = Analysis(
    ["launcher_ui.py"],
    pathex=[str(root)],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    # The launcher is a pure-QWidget app: it does not use QtWebEngine,
    # QtQml, QtMultimedia, QtNetwork or any of the heavier Qt
    # submodules. Excluding them drops ~50 MB of bundled translations
    # and QML from the build output.
    excludes=[
        "PySide6.QtWebEngineCore",
        "PySide6.QtWebEngineWidgets",
        "PySide6.QtWebEngineQuick",
        "PySide6.QtQml",
        "PySide6.QtQuick",
        "PySide6.QtQuickWidgets",
        "PySide6.Qt3DCore",
        "PySide6.Qt3DRender",
        "PySide6.Qt3DExtras",
        "PySide6.QtMultimedia",
        "PySide6.QtMultimediaWidgets",
        "PySide6.QtNetwork",
        "PySide6.QtBluetooth",
        "PySide6.QtNfc",
        "PySide6.QtPositioning",
        "PySide6.QtSensors",
        "PySide6.QtSerialPort",
        "PySide6.QtSql",
        "PySide6.QtTest",
        "PySide6.QtWebChannel",
        "PySide6.QtWebSockets",
        "PySide6.QtXml",
    ],
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

if is_onefile:
    # Single-file .exe: all binaries, datas, and the bootloader
    # compressed into one binary that extracts at startup.
    # No COLLECT step; nothing is left in dist\ except the .exe.
    pass
else:
    # Onedir layout: a directory containing FreeRealmsJSLauncher.exe
    # plus an _internal\ subdirectory with the bundled libraries and
    # data files. Easier to patch and debug.
    coll = COLLECT(
        exe,
        a.binaries,
        a.datas,
        strip=False,
        upx=False,
        upx_exclude=[],
        name="FreeRealmsJSLauncher",
    )
