from __future__ import annotations

from urllib.parse import quote
import re
import xml.etree.ElementTree as ET

from .models import ClientFileEntry, ClientFolderEntry


def slugify(value: str) -> str:
    clean = re.sub(r"[^a-zA-Z0-9]+", "_", value).strip("_").lower()
    return clean or "server"


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
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def parse_int(value: str | None, default: int) -> int:
    try:
        return int((value or "").strip())
    except ValueError:
        return default
