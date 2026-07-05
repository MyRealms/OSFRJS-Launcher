from __future__ import annotations

from pathlib import Path

from PySide6.QtGui import QPixmap

from .constants import APP_DIR, RESOURCE_DIR

ICON_DIR_CANDIDATES = [
    RESOURCE_DIR / "assets" / "server_icons",
    APP_DIR / "assets" / "server_icons",
    APP_DIR.parent / "assets" / "server_icons",
]


def icon_directory() -> Path | None:
    for candidate in ICON_DIR_CANDIDATES:
        if candidate.exists() and candidate.is_dir():
            return candidate
    return None


def available_icons() -> list[str]:
    """Return the list of icon file names (sorted) available in the icon folder.

    The launcher treats anything dropped into ``assets/server_icons/`` as a
    candidate icon for a custom server profile. PNG is the only supported
    format so that users can drop in their own artwork without needing to
    install codec support for DDS/TGA.
    """
    folder = icon_directory()
    if folder is None:
        return []
    return sorted(p.name for p in folder.iterdir() if p.is_file() and p.suffix.lower() == ".png")


def icon_path(name: str) -> Path | None:
    if not name:
        return None
    folder = icon_directory()
    if folder is None:
        return None
    candidate = folder / name
    if candidate.exists() and candidate.is_file():
        return candidate
    return None


def load_icon_pixmap(name: str) -> QPixmap:
    path = icon_path(name)
    if path is None:
        return QPixmap()
    return QPixmap(str(path))
