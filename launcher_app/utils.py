from __future__ import annotations

import hashlib
from urllib.parse import quote
import re
import unicodedata
import xml.etree.ElementTree as ET

from .models import ClientFileEntry, ClientFolderEntry


def slugify(value: str) -> str:
    """Return a filesystem-safe slug for ``value``.

    Non-ASCII characters (accented Latin, CJK, Cyrillic, emoji, etc.)
    are kept as word characters via ``re.UNICODE`` so e.g. ``"Türkçe"``
    becomes ``"türkçe"`` instead of the all-underscore ``"t_rk_e"``.
    The remaining unsafe characters are collapsed to ``_``. When the
    resulting slug would be empty (e.g. emoji-only input) or collide
    between visually-different names, a short hash of the original
    UTF-8 bytes is appended so two unrelated users with two unrelated
    non-ASCII profiles no longer silently share a save directory.
    """
    if not value:
        return "server"
    # Normalise accents so "Türkçe" and "Turkce" produce the same key.
    normalized = unicodedata.normalize("NFKD", value)
    ascii_only = normalized.encode("ascii", "ignore").decode("ascii")
    base = re.sub(r"[^a-zA-Z0-9]+", "_", ascii_only, flags=re.UNICODE).strip("_").lower()
    if not base:
        # All non-ASCII (or all-stripped). Use a short hash of the
        # original UTF-8 bytes as the slug so the result is unique per
        # input and contains only ASCII.
        digest = hashlib.sha1(value.encode("utf-8")).hexdigest()[:8]
        base = f"server_{digest}"
    return base or "server"


def normalize_server_url(value: str) -> str | None:
    """Return a usable http(s) URL or ``None`` for any non-conforming input.

    Examples:
        "192.168.1.50"        -> "http://192.168.1.50"
        "192.168.1.50:3000"   -> "http://192.168.1.50:3000"
        "play.example.com"    -> "http://play.example.com"
        "https://play.x.com"  -> "https://play.x.com"  (left as-is)
        ""                    -> None
        "javascript:alert(1)" -> None   (rejected: not http/https)
        "data:text/html,foo"  -> None   (rejected: not http/https)
        "://"                 -> None   (rejected: empty netloc)
        "http://"             -> None   (rejected: empty netloc)

    The caller is expected to handle ``None`` by showing a user-facing
    error and leaving the original input in the URL field for
    correction.
    """
    from urllib.parse import urlsplit
    text = value.strip()
    if not text:
        return None
    if "://" in text:
        try:
            split = urlsplit(text)
        except ValueError:
            return None
        if split.scheme.lower() not in {"http", "https"}:
            return None
        if not split.netloc:
            return None
        return text.rstrip("/")
    # Bare host or IP: prepend http:// and re-parse to make sure the
    # result is a well-formed URL with a non-empty netloc. We also
    # reject inputs that look like a non-http scheme (contain a ``:``
    # before any ``/`` but no ``://``), so ``javascript:alert(1)`` and
    # ``data:text/html,foo`` do not silently become
    # ``http://javascript:alert(1)``. The exception is the
    # ``host:port`` form, where the part after the ``:`` is a numeric
    # port (e.g. ``192.168.1.5:3000``).
    host_part = text.split("/", 1)[0]
    if ":" in host_part:
        maybe_port = host_part.rsplit(":", 1)[1]
        if not maybe_port.isdigit():
            return None
    candidate = "http://" + text.rstrip("/")
    try:
        split = urlsplit(candidate)
    except ValueError:
        return None
    if not split.netloc:
        return None
    return candidate


def join_url(base: str, *parts: str) -> str:
    clean_base = base.rstrip("/")
    clean_parts = [quote(part.strip("/"), safe="._-") for part in parts if part]
    if clean_parts:
        return f"{clean_base}/{'/'.join(clean_parts)}"
    return clean_base


def parse_folder(node: ET.Element) -> ClientFolderEntry:
    return ClientFolderEntry(
        name=node.get("name", ""),
        files=[
            ClientFileEntry(
                name=child.get("name", ""),
                size=int(child.get("size", "0")),
                hash_value=int(child.get("hash", "0")),
            )
            for child in node.findall("File")
        ],
        folders=[parse_folder(child) for child in node.findall("Folder")],
    )


def parse_login_server(value: str) -> tuple[str, int]:
    host = value.strip()
    port = 20042
    if ":" in host:
        maybe_host, maybe_port = host.rsplit(":", 1)
        if maybe_host:
            host = maybe_host
        try:
            port = int(maybe_port)
        except ValueError:
            port = 20042
    return host, port


def parse_bool(value: str | None, default: bool) -> bool:
    # Treat ``None`` and empty / whitespace-only text the same: the field
    # is unset, so fall back to the caller's default. Without this, an
    # empty <ParallelDownload></ParallelDownload> would silently disable
    # parallel downloads even when the default is True.
    if value is None:
        return default
    text = value.strip().lower()
    if not text:
        return default
    return text in {"1", "true", "yes", "on"}


def parse_int(value: str | None, default: int) -> int:
    if value is None:
        return default
    text = value.strip()
    if not text:
        return default
    try:
        return int(text)
    except ValueError:
        return default
