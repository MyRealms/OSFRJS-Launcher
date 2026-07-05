"""Reads the Free Realms client's critical-error log and turns the cryptic
"Error# G<n>" codes into in-launcher, human-friendly explanations + fixes.

The client writes a line like:
    (<time> <env> <server>) Error# G7 - <description> - ExitImmediately=1
to "#ClientCriticalError.log" (stored as ClientCriticalError.log in the
client's Logs folder) and, by default, opens ``GameCrashUrl`` in the
browser. We parse that log instead and show the user a helpful message
in the launcher. To keep the browser window that pops up from being a
scary remote crash page, we point ``GameCrashUrl=`` at a tiny in-process
HTTP server (see :mod:`launcher_app.crash_server`) so the browser always
lands on a small, local, launcher-branded "go back to the launcher" page.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from pathlib import Path

LOGGER = logging.getLogger("osfr_launcher")

# Client config files that may contain [WebResources] GameCrashUrl.
_CLIENT_CONFIG_NAMES = (
    "ClientConfig.ini",
    "ClientConfig_en_US.ini",
    "ClientConfig_sv_SE.ini",
    "ClientConfigOverride.ini",
)

# Anything that looks like a URL the client might ShellExecute on a crash
# gets blanked. ``GameCrashUrl=`` is the one we *intentionally* rewrite
# (to the local crash server), so it's handled separately by
# :func:`disable_crash_url`. The rest stay broad because the server can
# populate them via the login handshake and any of them could pop a
# real remote page.
_URL_CONFIG_KEYS_TO_BLANK = (
    "crashurl=",
    "crashreporturl=",
    "errorurl=",
    "errorwebpage=",
    "helpurl=",
    "supporturl=",
    "bugreporturl=",
    "webpage=",
    "forumurl=",
    "patchnotesurl=",
)

CRITICAL_ERROR_LOG_NAMES = (
    "ClientCriticalError.log",
    "#ClientCriticalError.log",
)

# Matches: "Error# G7 - some description -"
_ERROR_LINE_RE = re.compile(r"Error#\s*G(\d+)\s*-\s*(.*?)\s*-\s*ExitImmediately", re.IGNORECASE)
_ERROR_LINE_FALLBACK_RE = re.compile(r"Error#\s*G(\d+)\s*-\s*(.*)", re.IGNORECASE)


@dataclass(slots=True)
class ClientError:
    code: str            # e.g. "G7"
    title: str           # short human title
    detail: str          # raw description from the log
    suggestions: list[str]


# Known G-codes. The client uses G<dynamic number>, so this is a best-effort map;
# unknown codes fall back to a generic explanation.
_GENERIC_SUGGESTIONS = [
    "Make sure the server is online and reachable.",
    "Verify your internet connection.",
    "Try launching again — temporary glitches often clear on retry.",
]

# G-codes verified by tracing the client's error function sub_8EFAD0 in
# FreeRealms.exe.asm. Each entry below maps a code to the exact internal failure
# (from the log string pushed right before the error call).
_KNOWN_CODES: dict[str, tuple[str, list[str]]] = {
    "G2": (
        "Failed to load external libraries",
        [
            "The game could not load required DLLs/libraries.",
            "Make sure all client files are present (launch again to re-verify/patch).",
            "Install/repair DirectX 9 and the Visual C++ runtime if needed.",
        ],
    ),
    "G3": (
        "Display could not be created",
        [
            "The game failed to construct the display (graphics init failed).",
            "Update your GPU drivers.",
            "Try a different resolution/windowed mode, or check Display settings in ClientConfig.",
        ],
    ),
    "G4": (
        "Could not connect to the server / gateway",
        [
            "The client connected but the gateway failed, or no server could be reached.",
            "Make sure the Login AND Gateway servers are running.",
            "Verify the server IP/port are correct.",
        ],
    ),
    "G7": (
        "Failed to initialize AppServices",
        [
            "A core client service failed to start.",
            "Re-verify client files (launch again) and try once more.",
        ],
    ),
    "G12": (
        "Display reset failed",
        [
            "The game could not reset the display after several attempts.",
            "Update GPU drivers and avoid changing resolution while loading.",
            "Try windowed mode.",
        ],
    ),
    "G14": (
        "Initialization / session check failed",
        [
            "The client aborted during startup initialization.",
            "Try launching again.",
            "If it persists, re-verify client files.",
        ],
    ),
    "G15": (
        "Gateway connection failed",
        [
            "The connection to the gateway server failed.",
            "Make sure the Gateway server is running and reachable.",
        ],
    ),
    "G16": (
        "Connected but server did not respond",
        [
            "The client reached the server but it did not complete the handshake.",
            "The server may be starting up or overloaded — wait and retry.",
        ],
    ),
    "G24": (
        "Camera initialization failed",
        [
            "The game failed to initialize the camera (graphics-related).",
            "Update GPU drivers and re-verify client files.",
        ],
    ),
    "G19": (
        "Disconnected from server",
        [
            "The connection to the server was lost.",
            "Check your network and that the server is still running, then retry.",
        ],
    ),
    "G20": (
        "Disconnected from server",
        [
            "The connection to the server was lost.",
            "Check your network and that the server is still running, then retry.",
        ],
    ),
    "G21": (
        "Disconnected from server",
        [
            "The connection to the server was lost.",
            "Check your network and that the server is still running, then retry.",
        ],
    ),
    "G27": (
        "Asset delivery failed to initialize",
        [
            "The client could not set up asset/patch downloading.",
            "Check the AssetDelivery (IndirectServerAddress) URL in ClientConfig.",
            "Make sure that asset server is reachable.",
        ],
    ),
}


def describe_error(code_number: str, raw_detail: str) -> ClientError:
    code = f"G{code_number}"
    if code in _KNOWN_CODES:
        title, suggestions = _KNOWN_CODES[code]
    else:
        title = "Game client error"
        suggestions = list(_GENERIC_SUGGESTIONS)
    return ClientError(code=code, title=title, detail=raw_detail.strip(), suggestions=suggestions)


def _candidate_log_paths(client_dir: Path) -> list[Path]:
    logs_dir = client_dir / "Logs"
    paths: list[Path] = []
    for name in CRITICAL_ERROR_LOG_NAMES:
        paths.append(logs_dir / name)
        paths.append(client_dir / name)
    return paths


def find_critical_error_log(client_dir: Path) -> Path | None:
    for path in _candidate_log_paths(client_dir):
        if path.exists():
            return path
    return None


def parse_latest_error(log_path: Path) -> ClientError | None:
    """Return the most recent G-error described in the log, or None."""
    try:
        text = log_path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        LOGGER.warning("Could not read critical error log: %s", log_path)
        return None

    latest: ClientError | None = None
    for line in text.splitlines():
        match = _ERROR_LINE_RE.search(line) or _ERROR_LINE_FALLBACK_RE.search(line)
        if match:
            latest = describe_error(match.group(1), match.group(2))
    return latest


def read_error_log_mtime(client_dir: Path) -> float:
    """Modification time of the critical error log, or 0.0 if it doesn't exist.

    Used to detect whether a *new* crash happened during the last play session.
    """
    log_path = find_critical_error_log(client_dir)
    if log_path is None:
        return 0.0
    try:
        return log_path.stat().st_mtime
    except OSError:
        return 0.0


def detect_new_crash(client_dir: Path, previous_mtime: float) -> ClientError | None:
    """If the critical error log changed since previous_mtime, return the parsed error."""
    log_path = find_critical_error_log(client_dir)
    if log_path is None:
        return None
    try:
        mtime = log_path.stat().st_mtime
    except OSError:
        return None
    if mtime <= previous_mtime:
        return None
    return parse_latest_error(log_path)


def _iter_client_config_files(client_dir: Path) -> list[Path]:
    """Return all config files in the client dir we should sanitize.

    The original code only checked four hard-coded filenames, but the
    server can drop new config files at runtime (per-locale or per-build
    overrides) and may also write to ``Resources/`` or ``Servers/``
    subfolders. We walk the client directory for any ``*.ini`` or
    ``*.cfg`` to catch them all.

    The walker is hardened against symlinks (and Windows junctions):
    anything that resolves outside ``client_dir`` is dropped so a hostile
    or accidental symlink under the client tree cannot trick the
    launcher into rewriting an unrelated file (e.g. the user's
    ``%USERPROFILE%\\.gitconfig``, which matches the ``*.cfg`` glob).
    """
    seen: set[Path] = set()
    results: list[Path] = []

    def _is_under(p: Path, root: Path) -> bool:
        try:
            p_resolved = p.resolve()
            root_resolved = root.resolve()
        except OSError:
            return False
        try:
            p_resolved.relative_to(root_resolved)
        except ValueError:
            return False
        return True

    def _add(path: Path) -> None:
        if not _is_under(path, client_dir):
            # Refuse symlinks / junctions that escape the client dir.
            LOGGER.warning("Skipping config file outside client root: %s", path)
            return
        try:
            resolved = path.resolve()
        except OSError:
            resolved = path
        if resolved in seen:
            return
        seen.add(resolved)
        results.append(path)

    for name in _CLIENT_CONFIG_NAMES:
        _add(client_dir / name)
    if not client_dir.exists():
        return results
    try:
        for pattern in ("*.ini", "*.cfg"):
            for candidate in client_dir.rglob(pattern):
                # Don't recurse into the per-profile "servers/<name>/Client"
                # tree of a different profile; we'd silently rewrite siblings.
                if "servers" in candidate.parts:
                    continue
                _add(candidate)
    except OSError:
        LOGGER.warning("Could not enumerate config files under %s", client_dir)
    return results


def _strip_url_key(line: str) -> tuple[str, bool]:
    """Return (rewritten_line, changed) for any blank-on-crash URL key."""
    stripped = line.lstrip()
    lower = stripped.lower()
    for key in _URL_CONFIG_KEYS_TO_BLANK:
        if lower.startswith(key):
            # Keep the key, blank the value. The client then has nothing
            # to ShellExecute for that key.
            prefix_len = len(line) - len(stripped)
            key_part = stripped[: len(key) - 1]  # without trailing '='
            new_line = f"{' ' * prefix_len}{key_part}="
            return new_line, new_line.rstrip() != line.rstrip()
    return line, False


def _set_game_crash_url(line: str, crash_url: str) -> tuple[str, bool]:
    stripped = line.lstrip()
    if not stripped.lower().startswith("gamecrashurl="):
        return line, False
    prefix_len = len(line) - len(stripped)
    new_line = f"{' ' * prefix_len}GameCrashUrl={crash_url}"
    return new_line, new_line.rstrip() != line.rstrip()


def disable_crash_url(client_dir: Path, crash_url: str) -> None:
    """Point ``GameCrashUrl=`` at the launcher's local crash server.

    The client reads URL values (most importantly ``GameCrashUrl=``) from
    its config files at startup and ``ShellExecute``s them when a critical
    ``Error# G<n>`` happens. We:

    1. Walk *every* ``*.ini`` / ``*.cfg`` under the client directory
       (the original code only checked four hard-coded filenames).
    2. Rewrite ``GameCrashUrl=`` to ``crash_url`` so any browser window
       the client pops is the small in-launcher banner served by
       :class:`launcher_app.crash_server.CrashServer`, not whatever the
       server would otherwise push.
    3. Blank every other known web URL key (``CrashUrl=``,
       ``SupportUrl=``, ``HelpUrl=``, etc.) so a second ShellExecute
       on a related key still has nothing to open.
    4. Leave the file's structure, encoding, and trailing newline alone;
       only rewrite when something actually changed.

    Safe to call multiple times; runs cheaply (no rewriting when nothing
    changed) and is invoked both before launch and after the client
    exits, so a server that drops a fresh URL into the config during
    the login handshake cannot leak through.
    """
    if not crash_url:
        raise ValueError("crash_url is required so the client has a safe target")

    for config_path in _iter_client_config_files(client_dir):
        try:
            original = config_path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            LOGGER.debug("Skipping unreadable config: %s", config_path)
            continue

        new_lines: list[str] = []
        changed = False
        saw_game_crash_url = False
        for line in original.splitlines():
            stripped = line.lstrip()
            lower = stripped.lower()
            if lower.startswith("gamecrashurl="):
                new_line, line_changed = _set_game_crash_url(line, crash_url)
                if line_changed:
                    changed = True
                saw_game_crash_url = True
                new_lines.append(new_line)
                continue
            if any(lower.startswith(key) for key in _URL_CONFIG_KEYS_TO_BLANK):
                new_line, line_changed = _strip_url_key(line)
                if line_changed:
                    changed = True
                new_lines.append(new_line)
                continue
            new_lines.append(line)

        # If the file had no GameCrashUrl= line at all, inject one
        # under the existing [WebResources] section (or a new one) so
        # the client always has our local URL to fall back to. We
        # only do this on the main ClientConfig.ini / Override files
        # to avoid littering per-locale overrides.
        if (
            not saw_game_crash_url
            and config_path.name.lower() in {"clientconfig.ini", "clientconfigoverride.ini"}
        ):
            injected = False
            for index, line in enumerate(new_lines):
                if line.strip().lower() == "[webresources]":
                    new_lines.insert(index + 1, f"GameCrashUrl={crash_url}")
                    injected = True
                    break
            if not injected:
                if new_lines and new_lines[-1].strip():
                    new_lines.append("")
                new_lines.append("[WebResources]")
                new_lines.append(f"GameCrashUrl={crash_url}")
            changed = True

        if not changed:
            continue

        trailing_newline = "\n" if original.endswith("\n") else ""
        try:
            config_path.write_text("\n".join(new_lines) + trailing_newline, encoding="utf-8")
            LOGGER.info("Sanitized client config: %s", config_path)
        except OSError:
            LOGGER.warning("Could not rewrite %s to neutralize crash URLs", config_path)


