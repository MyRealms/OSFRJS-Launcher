from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(slots=True)
class MenuProfileMeta:
    key: str
    title: str
    subtitle: str


MENU_ITEMS = [
    MenuProfileMeta("offline_mode", "Offline Mode", "Local Server"),
    MenuProfileMeta("osfr_server", "OSFR Server", "Multiplayer"),
    MenuProfileMeta("freerealmsjs", "FreeRealmsJS", "Browser"),
]


@dataclass(slots=True)
class ServerProfile:
    key: str
    title: str
    subtitle: str
    name: str = ""
    description: str = ""
    server_url: str = ""
    login_server: str = ""
    login_api_url: str = ""
    save_path: str = ""
    username: str = ""
    password: str = ""
    remember_username: bool = False
    remember_password: bool = False

    @classmethod
    def from_mapping(cls, key: str, meta: MenuProfileMeta, payload: dict[str, Any]) -> ServerProfile:
        return cls(
            key=key,
            title=meta.title,
            subtitle=meta.subtitle,
            name=str(payload.get("name", meta.title)).strip(),
            description=str(payload.get("description", "")).strip(),
            server_url=str(payload.get("server_url", "")).strip(),
            login_server=str(payload.get("login_server", "")).strip(),
            login_api_url=str(payload.get("login_api_url", "")).strip(),
            save_path=str(payload.get("save_path", "")).strip(),
            username=str(payload.get("username", "")),
            password=str(payload.get("password", "")),
            remember_username=bool(payload.get("remember_username", False)),
            remember_password=bool(payload.get("remember_password", False)),
        )


@dataclass(slots=True)
class ServerManifest:
    name: str
    description: str
    web_api_url: str
    login_server: str


@dataclass(slots=True)
class ClientFileEntry:
    name: str
    size: int
    hash_value: int


@dataclass(slots=True)
class ClientFolderEntry:
    name: str
    files: list[ClientFileEntry]
    folders: list["ClientFolderEntry"]


@dataclass(slots=True)
class LoginResult:
    session_id: str
    launch_arguments: str = ""


@dataclass(slots=True)
class ServerStatus:
    is_online: bool
    is_locked: bool
    online_players: int


class LauncherError(Exception):
    pass
