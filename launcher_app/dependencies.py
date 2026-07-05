"""Runtime dependency management: DirectX 9, Node.js, AuthBridge npm deps, update checks.

These helpers let the launcher install everything the end user needs automatically,
so they never have to install .NET, Node, DirectX or run npm by hand. Works on both
Windows and Linux/macOS.
"""

from __future__ import annotations

import hashlib
import logging
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tarfile
import tempfile
import urllib.request
import zipfile

from .constants import (
    APP_DIR,
    DIRECTX9_REDIST_URL,
    GITHUB_LATEST_RELEASE_API_URL,
    LAUNCHER_VERSION,
    LEGACY_V110_NODE_DIR,
    NODE_DOWNLOAD_URL_LINUX,
    NODE_DOWNLOAD_URL_OSX,
    NODE_DOWNLOAD_URL_WINDOWS,
)

LOGGER = logging.getLogger("osfr_launcher")

# Portable: portable Node.js lives next to the launcher so the whole
# install can be copied around. v1.1.0 stored it under %LOCALAPPDATA%\OSFR
# Launcher\node; we fall back to that path for users upgrading from 1.1.0
# so they do not have to re-download ~30 MB of node.
PORTABLE_NODE_DIR = APP_DIR / "node"
_LEGACY_NODE_DIR = LEGACY_V110_NODE_DIR


# ---------------------------------------------------------------------------
# Generic helpers
# ---------------------------------------------------------------------------
def _no_window_kwargs() -> dict:
    """Avoid spawning a visible console window on Windows for child processes."""
    if sys.platform == "win32":
        return {"creationflags": getattr(subprocess, "CREATE_NO_WINDOW", 0)}
    return {}


# Default cap for any single download pulled from the network. The Node
# tarball/zip is ~30 MB; the DirectX web installer is ~1 MB; client files
# pulled from a server manifest are individually tiny. 60 MB is well above
# the largest legitimate download we trigger and well below anything that
# could be used to fill the disk via a malicious / MITM'd response.
_MAX_DOWNLOAD_BYTES = 60 * 1024 * 1024


def _download_file(url: str, destination: Path, *, progress=None, max_bytes: int = _MAX_DOWNLOAD_BYTES, expected_sha256: str | None = None) -> None:
    """Download ``url`` to ``destination`` reporting progress as (received, total) bytes.

    ``max_bytes`` caps the downloaded payload to defend against malicious
    or MITM'd responses that try to fill the disk. ``expected_sha256``,
    when provided, is checked against the downloaded bytes and the
    download is rejected on mismatch.
    """
    destination.parent.mkdir(parents=True, exist_ok=True)
    temp_path = destination.with_suffix(destination.suffix + ".part")

    request = urllib.request.Request(url, headers={"User-Agent": "OSFR-Launcher"})
    hasher = hashlib.sha256() if expected_sha256 else None
    try:
        with urllib.request.urlopen(request, timeout=60) as response:  # noqa: S310
            total = int(response.headers.get("Content-Length") or 0)
            if total and total > max_bytes:
                raise ValueError(
                    f"Refusing to download {url}: Content-Length {total} bytes exceeds the {max_bytes}-byte cap."
                )
            received = 0
            with open(temp_path, "wb") as handle:
                while True:
                    chunk = response.read(1024 * 256)
                    if not chunk:
                        break
                    received += len(chunk)
                    if received > max_bytes:
                        raise ValueError(
                            f"Aborted download from {url}: response exceeded the {max_bytes}-byte cap."
                        )
                    if hasher is not None:
                        hasher.update(chunk)
                    handle.write(chunk)
                    if progress is not None:
                        progress(received, total)
        if hasher is not None and hasher.hexdigest().lower() != expected_sha256.lower():
            raise ValueError(
                f"SHA-256 mismatch for {url}: expected {expected_sha256}, got {hasher.hexdigest()}"
            )
        temp_path.replace(destination)
    except Exception:
        if temp_path.exists():
            try:
                temp_path.unlink()
            except OSError:
                pass
        raise


def format_progress(received: int, total: int) -> str:
    """Human-readable download progress string, e.g. '12.3 MB / 30.0 MB (41%)'."""
    received_mb = received / 1024 / 1024
    if total > 0:
        total_mb = total / 1024 / 1024
        pct = received / total * 100
        return f"{received_mb:.1f} MB / {total_mb:.1f} MB ({pct:.0f}%)"
    return f"{received_mb:.1f} MB"


# ---------------------------------------------------------------------------
# DirectX 9
# ---------------------------------------------------------------------------
def directx9_available() -> bool:
    """Return True if DirectX 9 runtime DLLs are present (Windows only).

    ``d3d9.dll`` is part of every supported Windows install so it is
    only checked implicitly. The D3DX9 helper ``d3dx9_31.dll`` is the
    real dependency: it ships with the DirectX redistributable and (more
    commonly) with the Free Realms client itself. We treat the launcher
    as ready when either System32 *or* the active client directory
    contains the helper DLL, so a clean portable install with a
    pre-bundled client never triggers the DirectX installer at all.
    """
    if sys.platform != "win32":
        return True
    windows_dir = Path(os.environ.get("WINDIR", r"C:\Windows"))
    system32 = windows_dir / "System32"
    if system32.exists() and (system32 / "d3dx9_31.dll").exists():
        return True
    try:
        from .constants import APP_DIR
        client_root = APP_DIR / "Client"
    except Exception:
        client_root = None
    if client_root is not None:
        for candidate in client_root.rglob("d3dx9_31.dll"):
            if candidate.is_file():
                return True
    return False


def install_directx9(progress=None) -> bool:
    """Install DirectX 9 automatically.

    Windows: download and run the official web installer silently (/Q).
    Linux/macOS: install d3dx9 into the active Wine prefix via winetricks.
    """
    try:
        if sys.platform == "win32":
            return _install_directx9_windows(progress)
        return _install_directx9_wine()
    except Exception:  # noqa: BLE001
        LOGGER.exception("Automatic DirectX 9 installation failed.")
        return False


def _install_directx9_windows(progress=None) -> bool:
    installer = Path(tempfile.gettempdir()) / "osfr_dxwebsetup.exe"
    try:
        LOGGER.info("Downloading DirectX 9 web installer from %s", DIRECTX9_REDIST_URL)
        _download_file(DIRECTX9_REDIST_URL, installer, progress=progress)
    except Exception:
        LOGGER.exception("Failed to download DirectX 9 web installer")
        return False

    if directx9_available():
        LOGGER.info("DirectX 9 runtime already present; skipping installer run.")
        try:
            installer.unlink()
        except OSError:
            pass
        return True

    LOGGER.info("Running DirectX 9 web setup silently.")
    completed = subprocess.run(  # noqa: S603
        [str(installer), "/Q"],
        check=False,
        **_no_window_kwargs(),
    )
    try:
        installer.unlink()
    except OSError:
        pass
    LOGGER.info("DirectX 9 setup exited with code %s", completed.returncode)

    if directx9_available():
        return True

    is_admin = False
    if sys.platform == "win32":
        try:
            import ctypes
            is_admin = bool(ctypes.windll.shell32.IsUserAnAdmin())
        except OSError:
            pass
    if not is_admin:
        LOGGER.error(
            "DirectX 9 web installer ran but d3dx9_31.dll is still missing. "
            "The launcher is not running as an administrator; the DirectX "
            "installer needs elevation to write to %%WINDIR%%\\System32."
        )
    else:
        LOGGER.error(
            "DirectX 9 web installer ran but d3dx9_31.dll is still missing "
            "despite the launcher running as administrator."
        )
    return False


def _install_directx9_wine() -> bool:
    winetricks = shutil.which("winetricks")
    if not winetricks:
        LOGGER.error("winetricks is not installed; cannot install d3dx9 into the Wine prefix.")
        return False

    LOGGER.info("Installing DirectX 9 via winetricks (d3dx9).")
    completed = subprocess.run(  # noqa: S603
        [winetricks, "-q", "d3dx9", "d3dcompiler_43"],
        check=False,
    )
    if completed.returncode != 0:
        LOGGER.error("winetricks exited with code %s", completed.returncode)
        return False
    return True


# ---------------------------------------------------------------------------
# Node.js
# ---------------------------------------------------------------------------
def _node_executable_name() -> str:
    return "node.exe" if sys.platform == "win32" else "node"


def resolve_node_executable(bundled_node_dir: Path | None = None) -> Path | None:
    """Find a usable node executable: bundled copy, then portable, then legacy AppData, then system PATH."""
    exe = _node_executable_name()

    if bundled_node_dir is not None:
        for candidate in (bundled_node_dir / exe, bundled_node_dir / "bin" / exe):
            if candidate.exists():
                return candidate

    for candidate in (PORTABLE_NODE_DIR / exe, PORTABLE_NODE_DIR / "bin" / exe):
        if candidate.exists():
            return candidate

    if _LEGACY_NODE_DIR is not None:
        for candidate in (_LEGACY_NODE_DIR / exe, _LEGACY_NODE_DIR / "bin" / exe):
            if candidate.exists():
                LOGGER.info("Using legacy v1.1.0 node install at %s; consider re-running the launcher to migrate.", candidate)
                return candidate

    system = shutil.which("node")
    if system:
        return Path(system)

    return None


def node_available(bundled_node_dir: Path | None = None) -> bool:
    return resolve_node_executable(bundled_node_dir) is not None


def install_node(progress=None) -> Path | None:
    """Download and extract a portable Node.js runtime. Returns the node executable path."""
    try:
        if sys.platform == "win32":
            url = NODE_DOWNLOAD_URL_WINDOWS
        elif sys.platform == "darwin":
            url = NODE_DOWNLOAD_URL_OSX
        else:
            url = NODE_DOWNLOAD_URL_LINUX

        archive_name = url.rsplit("/", 1)[-1]
        archive_path = Path(tempfile.gettempdir()) / archive_name

        LOGGER.info("Downloading Node.js from %s", url)
        # Download FIRST so a network failure does not destroy an
        # existing working install. The previous code wiped
        # ``PORTABLE_NODE_DIR`` before the download attempt, which
        # meant an offline launch would silently destroy the user's
        # last-known-good Node install.
        _download_file(url, archive_path, progress=progress)

        # Download succeeded: now wipe any previous install and lay
        # down the new one. This makes the operation effectively
        # atomic: a half-populated tree from a previous interrupted
        # install can never coexist with the new one, and a future
        # Node version that drops a file from the v20.18.0 archive
        # will not leave a stale copy behind.
        if PORTABLE_NODE_DIR.exists():
            LOGGER.info("Removing previous Node install at %s", PORTABLE_NODE_DIR)
            shutil.rmtree(PORTABLE_NODE_DIR, ignore_errors=True)
        PORTABLE_NODE_DIR.mkdir(parents=True, exist_ok=True)

        try:
            with tempfile.TemporaryDirectory() as temp_extract_str:
                temp_extract = Path(temp_extract_str)
                if archive_name.endswith(".zip"):
                    with zipfile.ZipFile(archive_path) as archive:
                        archive.extractall(temp_extract)
                else:
                    # ``filter="data"`` is the recommended default in
                    # Python 3.12+ and the only safe default in 3.14+
                    # (it refuses to extract symlinks/hardlinks pointing
                    # outside the archive).
                    with tarfile.open(archive_path) as archive:
                        archive.extractall(temp_extract, filter="data")

                # Node archives contain a single top-level versioned
                # directory; flatten it.
                subdirs = [item for item in temp_extract.iterdir() if item.is_dir()]
                source_root = subdirs[0] if len(subdirs) == 1 else temp_extract

                for item in source_root.iterdir():
                    target = PORTABLE_NODE_DIR / item.name
                    if item.is_dir():
                        shutil.copytree(item, target, dirs_exist_ok=True)
                    else:
                        shutil.copy2(item, target)
        finally:
            # Wipe the staging tarball/zip from the OS temp directory
            # so a Node upgrade does not accumulate multiple ~30 MB
            # archives in the user's temp folder.
            try:
                archive_path.unlink()
            except OSError:
                pass

        node_path = resolve_node_executable()
        if node_path and sys.platform != "win32":
            try:
                node_path.chmod(0o755)
            except OSError:
                pass
        return node_path
    except Exception:  # noqa: BLE001
        LOGGER.exception("Failed to install Node.js.")
        return None


# ---------------------------------------------------------------------------
# AuthBridge npm dependencies
# ---------------------------------------------------------------------------
def authbridge_dependencies_installed(authbridge_dir: Path) -> bool:
    return (authbridge_dir / "node_modules").is_dir()


def install_authbridge_dependencies(authbridge_dir: Path, node_executable: Path) -> bool:
    """Run ``npm install --omit=dev`` for the AuthBridge using the resolved node."""
    if authbridge_dependencies_installed(authbridge_dir):
        return True

    if not (authbridge_dir / "package.json").exists():
        LOGGER.error("AuthBridge package.json missing in %s", authbridge_dir)
        return False

    npm_cli = _find_npm_cli(node_executable)
    try:
        if npm_cli is not None:
            command = [str(node_executable), str(npm_cli), "install", "--omit=dev"]
        else:
            npm = shutil.which("npm")
            if not npm:
                LOGGER.error("npm not found; cannot install AuthBridge dependencies.")
                return False
            command = [npm, "install", "--omit=dev"]

        LOGGER.info("Installing AuthBridge dependencies: %s", " ".join(command))
        # Capture stdout/stderr so an offline / misconfigured npm run
        # leaves a useful tail in the launcher_debug.log instead of
        # only the cryptic "Failed to install the local server's
        # AuthBridge dependencies" message.
        completed = subprocess.run(  # noqa: S603
            command,
            cwd=str(authbridge_dir),
            check=False,
            capture_output=True,
            text=True,
            timeout=300,
            **_no_window_kwargs(),
        )
        if completed.returncode != 0:
            stderr_tail = "\n".join(
                (completed.stderr or "").splitlines()[-20:]
            )
            stdout_tail = "\n".join(
                (completed.stdout or "").splitlines()[-10:]
            )
            LOGGER.error(
                "npm install failed: returncode=%s\nstderr (last 20 lines):\n%s\nstdout (last 10 lines):\n%s",
                completed.returncode,
                stderr_tail,
                stdout_tail,
            )
            return False
        return authbridge_dependencies_installed(authbridge_dir)
    except Exception:  # noqa: BLE001
        LOGGER.exception("Failed to install AuthBridge dependencies.")
        return False


def _find_npm_cli(node_executable: Path) -> Path | None:
    """Locate npm-cli.js shipped alongside a portable/bundled node."""
    node_dir = node_executable.parent
    candidates = [
        node_dir / "node_modules" / "npm" / "bin" / "npm-cli.js",
        node_dir.parent / "lib" / "node_modules" / "npm" / "bin" / "npm-cli.js",
    ]
    for candidate in candidates:
        if candidate.exists():
            return candidate
    return None


# ---------------------------------------------------------------------------
# Launcher update check
# ---------------------------------------------------------------------------
def _parse_version(value: str) -> tuple[int, ...]:
    cleaned = value.strip().lstrip("vV")
    parts: list[int] = []
    for piece in cleaned.split("."):
        number = "".join(ch for ch in piece if ch.isdigit())
        if number == "":
            break
        parts.append(int(number))
    return tuple(parts) if parts else (0,)


def check_for_update() -> tuple[bool, str | None, str | None]:
    """Check GitHub for a newer release.

    Returns (update_available, latest_version, release_url).
    Never raises; on any failure returns (False, None, None).
    """
    import json

    try:
        request = urllib.request.Request(
            GITHUB_LATEST_RELEASE_API_URL,
            headers={
                "User-Agent": "OSFR-Launcher",
                "Accept": "application/vnd.github+json",
            },
        )
        with urllib.request.urlopen(request, timeout=15) as response:  # noqa: S310
            data = json.loads(response.read().decode("utf-8"))

        if data.get("draft"):
            return (False, None, None)

        tag = data.get("tag_name")
        if not tag:
            return (False, None, None)

        latest = _parse_version(tag)
        current = _parse_version(LAUNCHER_VERSION)

        if latest > current:
            return (True, tag.lstrip("vV"), data.get("html_url"))
        return (False, None, None)
    except Exception:  # noqa: BLE001
        LOGGER.warning("Failed to check for launcher updates.", exc_info=True)
        return (False, None, None)
