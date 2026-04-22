from __future__ import annotations

import socket
import struct
import xml.etree.ElementTree as ET

import requests

from .constants import HTTP_TIMEOUT
from .models import ClientFolderEntry, LauncherError, ServerManifest, ServerProfile, ServerStatus
from .utils import join_url, parse_folder, parse_login_server


class LauncherWidgetManifestFlowMixin:
    def _fetch_server_manifest(self, server_url: str, *, timeout: int | float = HTTP_TIMEOUT) -> ServerManifest:
        url = join_url(server_url, "ServerManifest.xml")
        response = requests.get(url, timeout=timeout)
        response.raise_for_status()

        try:
            root = ET.fromstring(response.text)
            login_api_url = (root.findtext("LoginApiUrl") or "").strip()
            web_api_url = (root.findtext("WebApiUrl") or "").strip()
            if not web_api_url and login_api_url:
                web_api_url = login_api_url.rsplit("/", 1)[0] if "/" in login_api_url else login_api_url
            return ServerManifest(
                name=(root.findtext("Name") or "").strip(),
                description=(root.findtext("Description") or "").strip(),
                web_api_url=web_api_url,
                login_server=(root.findtext("LoginServer") or "").strip(),
            )
        except ET.ParseError as exc:
            raise LauncherError(f"Invalid server manifest XML: {exc}") from exc

    def _resolve_server_manifest(self, profile: ServerProfile) -> ServerManifest:
        try:
            return self._fetch_server_manifest(profile.server_url)
        except Exception:
            if profile.login_server and profile.login_api_url:
                return ServerManifest(
                    name=profile.name or profile.title,
                    description=profile.description,
                    web_api_url=profile.login_api_url.rsplit("/", 1)[0],
                    login_server=profile.login_server,
                )
            raise

    def _fetch_client_manifest(self, server_url: str) -> ClientFolderEntry:
        url = join_url(server_url, "ClientManifest.xml")
        response = requests.get(url, timeout=HTTP_TIMEOUT)
        response.raise_for_status()

        try:
            root = ET.fromstring(response.text)
            folder_node = root.find("Folder")
            if folder_node is None:
                raise LauncherError("Client manifest did not include a root folder.")
            return parse_folder(folder_node)
        except ET.ParseError as exc:
            raise LauncherError(f"Invalid client manifest XML: {exc}") from exc

    def _fetch_server_status(self, login_server: str, *, timeout: float = 5.0) -> ServerStatus:
        host, port = parse_login_server(login_server)
        if not host:
            return ServerStatus(False, False, 0)

        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
            sock.settimeout(timeout)
            try:
                sock.sendto(bytes([0x00, 32]), (host, port))
                data, _ = sock.recvfrom(64)
            except OSError:
                return ServerStatus(False, False, 0)

        if len(data) < 6:
            return ServerStatus(False, False, 0)

        is_online, is_locked, online_players = struct.unpack("<??i", data[:6])
        return ServerStatus(is_online, is_locked, online_players)
