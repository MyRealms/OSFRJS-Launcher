from __future__ import annotations

import logging
import socket
import struct
import sys
import xml.etree.ElementTree as ET

import requests

from .constants import HTTP_TIMEOUT
from .models import ClientFolderEntry, LauncherError, ServerManifest, ServerProfile, ServerStatus
from .utils import join_url, parse_folder, parse_login_server

LOGGER = logging.getLogger("osfr_launcher")


class LauncherWidgetManifestFlowMixin:
    def _fetch_server_manifest(self, server_url: str, *, timeout: int | float = HTTP_TIMEOUT) -> ServerManifest:
        url = join_url(server_url, "ServerManifest.xml")
        LOGGER.info("Fetching server manifest: %s", url)
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
            LOGGER.info("Resolving server manifest for profile=%s server_url=%s", profile.key, profile.server_url)
            return self._fetch_server_manifest(profile.server_url)
        except Exception:
            if profile.login_server and profile.login_api_url:
                LOGGER.warning("Falling back to profile manifest data for profile=%s", profile.key)
                return ServerManifest(
                    name=profile.name or profile.title,
                    description=profile.description,
                    web_api_url=profile.login_api_url.rsplit("/", 1)[0],
                    login_server=profile.login_server,
                )
            raise

    def _fetch_client_manifest(self, server_url: str) -> ClientFolderEntry:
        url = join_url(server_url, "ClientManifest.xml")
        LOGGER.info("Fetching client manifest: %s", url)
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

    @staticmethod
    def _disable_udp_conn_reset(sock: socket.socket) -> None:
        """Stop Windows from raising ConnectionResetError (WSAECONNRESET / 10054) on UDP.

        On Windows, sending a UDP datagram to a closed port makes the OS deliver an
        ICMP "port unreachable", which is surfaced as a ConnectionResetError on the
        *next* send/recv. For a reused socket this would poison every later probe so
        the server appears offline even after it comes online. SIO_UDP_CONNRESET
        disables that behaviour. No-op on non-Windows platforms.
        """
        if sys.platform != "win32":
            return
        try:
            # SIO_UDP_CONNRESET = 0x9800000C
            sock.ioctl(0x9800000C, struct.pack("I", 0))
        except (OSError, AttributeError, ValueError):
            # ioctl is unavailable in some environments; the per-call OSError
            # handling below still keeps a single failed probe from crashing.
            pass

    def _fetch_server_status(
        self,
        login_server: str,
        *,
        timeout: float = 5.0,
        sock: socket.socket | None = None,
    ) -> ServerStatus:
        host, port = parse_login_server(login_server)
        if not host:
            return ServerStatus(False, False, 0)
        LOGGER.info("Fetching server status from %s:%s", host, port)

        # Reuse the caller-provided socket when polling repeatedly (e.g. the
        # server warmup loop) so we don't burn a new ephemeral port on every
        # probe. Only create/close our own socket for one-off lookups.
        owns_socket = sock is None
        if owns_socket:
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self._disable_udp_conn_reset(sock)
        try:
            sock.settimeout(timeout)
            try:
                sock.sendto(bytes([0x00, 32]), (host, port))
                data, _ = sock.recvfrom(64)
            except ConnectionResetError:
                # Windows ICMP port-unreachable for a closed server: treat as offline
                # without poisoning a reused socket for subsequent probes.
                LOGGER.info("Server status: connection reset (server offline) for %s:%s", host, port)
                return ServerStatus(False, False, 0)
            except OSError:
                LOGGER.warning("Server status fetch failed for %s:%s", host, port)
                return ServerStatus(False, False, 0)
        finally:
            if owns_socket:
                sock.close()

        if len(data) < 6:
            return ServerStatus(False, False, 0)

        is_online, is_locked, online_players = struct.unpack("<??i", data[:6])
        LOGGER.info(
            "Server status result: login_server=%s online=%s locked=%s players=%s",
            login_server,
            is_online,
            is_locked,
            online_players,
        )
        return ServerStatus(is_online, is_locked, online_players)
