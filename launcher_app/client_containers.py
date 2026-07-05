"""Per-server client container management.

The user keeps a single golden (unedited) client tree at
``<APP_DIR>/Client/OSFR - Original/`` and the launcher copies it into
``<APP_DIR>/Client/OSFR - <server name>/`` whenever the user adds a new
server with "Create new client container" enabled. This isolates saves,
config and any per-server custom files so they never leak between
servers.

The ``Client`` folder itself is user-managed: the launcher never deletes
or moves it, never auto-seeds it from an older install, and never
overwrites ``OSFR - Original``. If the original is missing when a
container is requested, :class:`ClientContainerError` is raised so the UI
can surface a clear hint.
"""

from __future__ import annotations

import logging
import re
import shutil
from pathlib import Path

from .constants import (
    CLIENT_CONTAINER_PREFIX,
    CLIENT_STASH_DIR,
    CLIENT_STASH_ORIGINAL_DIR,
    CLIENT_STASH_ORIGINAL_NAME,
)

LOGGER = logging.getLogger("osfr_launcher")


class ClientContainerError(RuntimeError):
    """Raised when a client container cannot be created or resolved."""


# Characters Windows / macOS / Linux file systems generally refuse, plus
# the path separators. Note: '-' is a valid filename character on every
# supported OS so we do NOT list it here.
_INVALID_NAME_CHARS = re.compile(r'[<>:"/\\|?*\x00-\x1f]')
_COLLAPSE = re.compile(r"[\s_]+")


def sanitize_container_name(raw: str) -> str:
    """Return a filesystem-safe container name (no leading ``OSFR - ``)."""
    cleaned = _INVALID_NAME_CHARS.sub("-", raw).strip()
    cleaned = _COLLAPSE.sub(" ", cleaned).strip()
    return cleaned or "Server"


def build_default_container_name(server_name: str) -> str:
    """Build ``"OSFR - <server name>"`` from a user-supplied server name."""
    return f"{CLIENT_CONTAINER_PREFIX}{sanitize_container_name(server_name)}"


def suggest_next_container_name(server_name: str) -> str:
    """Pick a non-colliding container name; append ``(2)``, ``(3)``... on clash."""
    base = build_default_container_name(server_name)
    if not (CLIENT_STASH_DIR / base).exists():
        return base
    suffix = 2
    while True:
        candidate = f"{base} ({suffix})"
        if not (CLIENT_STASH_DIR / candidate).exists():
            return candidate
        suffix += 1


def list_containers() -> list[Path]:
    """Return existing container directories, sorted by name (case-insensitive)."""
    if not CLIENT_STASH_DIR.is_dir():
        return []
    return sorted(
        (p for p in CLIENT_STASH_DIR.iterdir() if p.is_dir()),
        key=lambda p: p.name.casefold(),
    )


def container_exists(name: str) -> bool:
    return (CLIENT_STASH_DIR / name).is_dir()


def resolve_container_dir(name: str) -> Path:
    """Return the absolute path of the named container under the client stash."""
    if not name:
        raise ValueError("Container name is empty.")
    if _INVALID_NAME_CHARS.search(name):
        raise ValueError(f"Container name contains invalid characters: {name!r}")
    return CLIENT_STASH_DIR / name


def is_golden_missing() -> bool:
    """Return True when the user-managed ``OSFR - Original`` tree is absent."""
    return not CLIENT_STASH_ORIGINAL_DIR.is_dir()


def create_container(server_name: str, *, copy_from: Path | None = None) -> Path:
    """Copy the golden client tree into a new container for ``server_name``.

    The returned path is the new container directory. The container name
    is auto-disambiguated (``MyServer`` -> ``OSFR - MyServer (2)`` etc.) so
    repeated calls never overwrite an existing sandbox.
    """
    source = copy_from or CLIENT_STASH_ORIGINAL_DIR
    if not source.is_dir():
        raise ClientContainerError(
            f"Golden client tree not found at {CLIENT_STASH_ORIGINAL_DIR}. "
            f"Create it first (the 'Client' folder is user-managed) and try again."
        )

    target_name = suggest_next_container_name(server_name)
    target = CLIENT_STASH_DIR / target_name

    CLIENT_STASH_DIR.mkdir(parents=True, exist_ok=True)
    LOGGER.info("Creating client container %s -> %s", source, target)
    try:
        shutil.copytree(source, target)
    except OSError as exc:
        raise ClientContainerError(f"Failed to create container {target}: {exc}") from exc
    return target


__all__ = [
    "CLIENT_CONTAINER_PREFIX",
    "CLIENT_STASH_ORIGINAL_NAME",
    "ClientContainerError",
    "build_default_container_name",
    "container_exists",
    "create_container",
    "is_golden_missing",
    "list_containers",
    "resolve_container_dir",
    "sanitize_container_name",
    "suggest_next_container_name",
]
