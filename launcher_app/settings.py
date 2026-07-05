from __future__ import annotations

import logging
import os
import shutil
import time
import xml.etree.ElementTree as ET

from .constants import (
    APP_DIR,
    LEGACY_SETTINGS_PATH,
    LEGACY_V110_SERVERS_ROOT,
    LEGACY_V110_SETTINGS_PATH,
    SERVERS_ROOT,
    SETTINGS_PATH,
)
from .credential_store import delete_password as _delete_password, init as _cred_init, load_password as _load_password, save_password as _save_password
from .models import MENU_ITEMS, MenuProfileMeta, ServerProfile
from .utils import parse_bool, parse_int, slugify

LOGGER = logging.getLogger("osfr_launcher")


class LauncherSettings:
    def __init__(self) -> None:
        self.display_name = ""
        self.game_path = ""
        self.locale = "en_US"
        self.parallel_download = True
        self.download_threads = 4
        self.discord_activity = True
        self.profiles: dict[str, ServerProfile] = {}
        self.profile_order: list[str] = [meta.key for meta in MENU_ITEMS]
        for meta in MENU_ITEMS:
            self.profiles[meta.key] = ServerProfile(
                key=meta.key,
                title=meta.title,
                subtitle=meta.subtitle,
                name=meta.title,
                save_path=meta.key,
            )

        self.profiles["offline_mode"] = ServerProfile(
            key="offline_mode",
            title="Offline Mode",
            subtitle="Local Server",
            name="Local",
            description="Local Hosting Server",
            server_url="http://localhost:3000",
            login_server="127.0.0.1:20042",
            login_api_url="http://127.0.0.1:3000/login",
            save_path="Local",
            username="test",
            password="test",
            remember_username=True,
            remember_password=True,
        )

        self.profiles["osfr_server"] = ServerProfile(
            key="osfr_server",
            title="OSFR Server",
            subtitle="Multiplayer",
            name="OSFR Server",
            description="Please register at www.osfrealms.com if you do not have an account.",
            server_url="https://play.osfrealms.com",
            save_path="osfr_server",
        )

    @classmethod
    def load(cls) -> LauncherSettings:
        _cred_init(APP_DIR)
        settings = cls()
        LOGGER.info("Loading launcher settings from %s", SETTINGS_PATH)
        if not SETTINGS_PATH.exists():
            settings._migrate_v110_appdata_settings()
            if LEGACY_SETTINGS_PATH.exists():
                settings._load_legacy_json()
            if not SETTINGS_PATH.exists():
                LOGGER.info("No settings file found; using defaults")
                return settings

        try:
            root = ET.fromstring(SETTINGS_PATH.read_text(encoding="utf-8"))
        except (OSError, ET.ParseError, UnicodeDecodeError):
            LOGGER.exception("Failed to read settings XML; using defaults")
            return settings

        settings.locale = (root.findtext("Locale") or settings.locale).strip() or settings.locale
        settings.display_name = (root.findtext("DisplayName") or settings.display_name).strip()
        settings.game_path = (root.findtext("GamePath") or settings.game_path).strip()
        settings.parallel_download = parse_bool(root.findtext("ParallelDownload"), settings.parallel_download)
        settings.download_threads = max(1, parse_int(root.findtext("DownloadThreads"), settings.download_threads))
        settings.discord_activity = parse_bool(root.findtext("DiscordActivity"), settings.discord_activity)

        server_nodes = root.findall("./ServerInfoList/ServerInfo")
        used_keys: set[str] = set()
        _migrated = False  # track whether any plaintext passwords were moved to secure storage
        for node in server_nodes:
            mapping = {
                "name": (node.findtext("Name") or "").strip(),
                "description": (node.findtext("Description") or "").strip(),
                "server_url": (node.findtext("Url") or "").strip(),
                "login_server": (node.findtext("LoginServer") or "").strip(),
                "login_api_url": (node.findtext("LoginApiUrl") or "").strip(),
                "save_path": (node.findtext("SavePath") or "").strip(),
                "username": (node.findtext("Username") or "").strip(),
                "password": (node.findtext("Password") or "").strip(),
                "remember_username": parse_bool(node.findtext("RememberUsername"), False),
                "remember_password": parse_bool(node.findtext("RememberPassword"), False),
                "icon_name": (node.findtext("IconName") or "").strip(),
                "client_container": (node.findtext("ClientContainer") or "").strip(),
            }
            key = settings._match_profile_key(mapping, used_keys)
            if key is None:
                continue
            used_keys.add(key)
            if key in {meta.key for meta in MENU_ITEMS}:
                meta = next(item for item in MENU_ITEMS if item.key == key)
                settings.profiles[key] = ServerProfile.from_mapping(key, meta, mapping)
            else:
                settings.profiles[key] = ServerProfile(
                    key=key,
                    title=str(mapping.get("name", "") or "Custom Server").strip() or "Custom Server",
                    subtitle="Custom Server",
                    name=str(mapping.get("name", "") or "Custom Server").strip() or "Custom Server",
                    description=str(mapping.get("description", "") or "").strip(),
                    server_url=str(mapping.get("server_url", "") or "").strip(),
                    login_server=str(mapping.get("login_server", "") or "").strip(),
                    login_api_url=str(mapping.get("login_api_url", "") or "").strip(),
                    save_path=str(mapping.get("save_path", "") or key).strip(),
                    username=str(mapping.get("username", "") or ""),
                    password=str(mapping.get("password", "") or ""),
                    remember_username=bool(mapping.get("remember_username", False)),
                    remember_password=bool(mapping.get("remember_password", False)),
                    icon_name=str(mapping.get("icon_name", "") or "").strip(),
                    client_container=str(mapping.get("client_container", "") or "").strip(),
                )
            profile = settings.profiles[key]
            xml_password = str(mapping.get("password", "") or "")
            if profile.remember_password:
                stored = _load_password(key)
                if stored is not None:
                    profile.password = stored
                elif xml_password:
                    # Migration: XML has a plaintext password from a previous
                    # launcher version. Move it to the Credential Manager so
                    # the next save() clears it from XML.
                    _save_password(key, profile.username or "", xml_password)
                    _migrated = True
            if key not in settings.profile_order:
                settings.profile_order.append(key)
        if _migrated:
            LOGGER.info("Plaintext passwords migrated to secure storage; rewriting Launcher.xml without them.")
            settings.save()

        LOGGER.info(
            "Loaded settings: display_name=%r game_path=%r profiles=%d",
            settings.display_name,
            settings.game_path,
            len(settings.profile_order),
        )
        return settings

    def save(self) -> bool:
        """Persist the in-memory settings to ``SETTINGS_PATH``.

        Returns ``True`` on success and ``False`` on any I/O failure. The
        return value exists so callers performing two-phase operations
        (e.g. registering a profile, then cloning a multi-GB client
        container) can detect save failures and roll back the in-memory
        state instead of leaking an orphaned container.
        """
        try:
            SETTINGS_PATH.parent.mkdir(parents=True, exist_ok=True)
        except (OSError, PermissionError):
            LOGGER.exception("Failed to create settings directory %s", SETTINGS_PATH.parent)
            return False
        # Clamp here too so the on-disk value matches what ``load`` would
        # compute. Otherwise a ``download_threads=0`` written by a config
        # tool would round-trip as ``1`` on the next load with no
        # signal to the user.
        self.download_threads = max(1, int(self.download_threads))
        root = ET.Element("Settings")
        ET.SubElement(root, "DiscordActivity").text = "true" if self.discord_activity else "false"
        ET.SubElement(root, "ParallelDownload").text = "true" if self.parallel_download else "false"
        ET.SubElement(root, "DownloadThreads").text = str(self.download_threads)
        ET.SubElement(root, "Locale").text = self.locale
        ET.SubElement(root, "DisplayName").text = self.display_name
        ET.SubElement(root, "GamePath").text = self.game_path

        server_info_list = ET.SubElement(root, "ServerInfoList")
        for key in self.profile_order:
            profile = self.profiles[key]
            node = ET.SubElement(server_info_list, "ServerInfo")
            ET.SubElement(node, "Url").text = profile.server_url
            ET.SubElement(node, "Name").text = profile.name or profile.title
            ET.SubElement(node, "Description").text = profile.description
            ET.SubElement(node, "LoginServer").text = profile.login_server
            ET.SubElement(node, "LoginApiUrl").text = profile.login_api_url
            ET.SubElement(node, "SavePath").text = profile.save_path
            ET.SubElement(node, "Username").text = (profile.username or "").strip() if profile.remember_username else ""
            ET.SubElement(node, "RememberUsername").text = "true" if profile.remember_username else "false"
            # Password is stored in Windows Credential Manager, never in XML.
            # The XML <Password> element is written as empty for backward
            # compatibility (older launcher versions that still expect it).
            ET.SubElement(node, "Password").text = ""
            ET.SubElement(node, "RememberPassword").text = "true" if profile.remember_password else "false"
            if profile.remember_password:
                _save_password(key, profile.username or "", profile.password or "")
            else:
                _delete_password(key)
            ET.SubElement(node, "IconName").text = profile.icon_name
            ET.SubElement(node, "ClientContainer").text = profile.client_container

        ET.indent(root)
        xml_text = ET.tostring(root, encoding="unicode", xml_declaration=True)

        # Write atomically (temp file + fsync + replace + dir-fsync) so a
        # crash or power loss while saving cannot leave Launcher.xml empty
        # or pointing at unflushed data. ``os.replace`` is atomic at the
        # directory-entry level on NTFS and on POSIX; FAT32 / exFAT (the
        # common portable-USB target) does not guarantee atomicity, so
        # the fsync dance is the closest portable approximation to a
        # crash-safe write.
        temp_path = SETTINGS_PATH.with_suffix(SETTINGS_PATH.suffix + ".tmp")
        try:
            with open(temp_path, "wb") as handle:
                handle.write(xml_text.encode("utf-8"))
                handle.flush()
                try:
                    os.fsync(handle.fileno())
                except (OSError, AttributeError):
                    # Some filesystems (notably some Windows network
                    # shares) do not implement fsync; fall through.
                    pass
            os.replace(temp_path, SETTINGS_PATH)
            try:
                dir_fd = os.open(str(SETTINGS_PATH.parent), os.O_RDONLY)
            except OSError:
                dir_fd = -1
            if dir_fd != -1:
                try:
                    os.fsync(dir_fd)
                except OSError:
                    pass
                finally:
                    os.close(dir_fd)
        except (OSError, UnicodeEncodeError):
            LOGGER.exception("Failed to save launcher settings to %s", SETTINGS_PATH)
            if temp_path.exists():
                try:
                    temp_path.unlink()
                except OSError:
                    pass
            return False
        LOGGER.info("Saved launcher settings to %s", SETTINGS_PATH)
        return True

    def profile_for_index(self, index: int) -> ServerProfile:
        key = self.profile_order[index]
        return self.profiles[key]

    def all_profiles(self) -> list[ServerProfile]:
        return [self.profiles[key] for key in self.profile_order if key in self.profiles]

    def update_profile(self, profile: ServerProfile) -> None:
        self.profiles[profile.key] = profile
        if profile.key not in self.profile_order:
            self.profile_order.append(profile.key)

    def add_custom_profile(self, server_url: str, name: str = "", *, client_container: str = "") -> ServerProfile:
        # The submit UI guarantees a non-empty ``name``; the ``"Custom
        # Server"`` fallback is defence-in-depth for direct programmatic
        # callers, and ``server_url`` is never used as the slug source.
        base_name = name.strip() or "Custom Server"
        clean_url = server_url.strip()
        if not clean_url:
            raise ValueError("Cannot add a custom server profile with an empty server_url.")
        if client_container and ("/" in client_container or "\\" in client_container or ".." in client_container):
            raise ValueError(f"client_container must be a folder name, not a path: {client_container!r}")
        host_key = slugify(base_name)
        key = f"custom_{host_key}"
        suffix = 2
        while key in self.profiles:
            key = f"custom_{host_key}_{suffix}"
            suffix += 1
        profile = ServerProfile(
            key=key,
            title=base_name,
            subtitle="Custom Server",
            name=base_name,
            description="Custom launcher server",
            server_url=clean_url,
            save_path=key,
            client_container=client_container,
        )
        self.update_profile(profile)
        return profile

    def can_delete_profile(self, key: str) -> bool:
        return key not in {meta.key for meta in MENU_ITEMS}

    def delete_profile(self, key: str) -> None:
        if not self.can_delete_profile(key):
            raise ValueError(f"Profile '{key}' is required and cannot be deleted.")
        self.profiles.pop(key, None)
        if key in self.profile_order:
            self.profile_order.remove(key)

    def _match_profile_key(self, payload: dict[str, str | bool], used_keys: set[str]) -> str | None:
        # Built-in identity is decided by ``save_path`` (the *path the server
        # stores its per-profile data in*), NOT by the user-editable display
        # name. Using ``name`` here caused custom servers named "Local" or
        # containing the substring "osfr" to silently hijack the offline /
        # OSFR built-in profiles. The name "OSFR Server" lives in the
        # default save_path of ``osfr_server`` ("osfr_server") and the
        # default save_path of ``offline_mode`` ("Local" -> normalised to
        # "local"), so the built-in detection is exact and stable.
        save_path = str(payload.get("save_path", "")).strip().lower()
        # Default save_paths that the LauncherSettings constructor assigns
        # to the built-ins when no XML row exists yet. If the XML row uses
        # one of these (or a historically-equivalent string), it is a
        # built-in profile row.
        offline_known_save_paths = {"local", "offline_mode", "offline mode"}
        osfr_known_save_paths = {"osfr_server", "osfr", "osfr server"}
        if save_path in offline_known_save_paths and "offline_mode" not in used_keys:
            return "offline_mode"
        if save_path in osfr_known_save_paths and "osfr_server" not in used_keys:
            return "osfr_server"
        # The legacy "FreeRealmsJS" (browser) entry was removed; drop it from
        # saved settings.
        if save_path == "freerealmsjs":
            return None
        # Custom key derivation: slugify the *display name* (not the
        # save_path, which is already ``"custom_<slug>"`` for custom rows
        # and would produce ``"custom_custom_<slug>"`` on every reload).
        custom_base = slugify(
            str(
                payload.get("name", "")
                or payload.get("server_url", "")
            ).strip()
        )
        if custom_base:
            custom_key = f"custom_{custom_base}"
            suffix = 2
            while custom_key in used_keys:
                custom_key = f"custom_{custom_base}_{suffix}"
                suffix += 1
            return custom_key
        return None

    def _load_legacy_json(self) -> None:
        try:
            import json

            payload = json.loads(LEGACY_SETTINGS_PATH.read_text(encoding="utf-8"))
        except Exception:  # noqa: BLE001
            LOGGER.exception("Failed to load legacy JSON settings from %s", LEGACY_SETTINGS_PATH)
            return

        self.locale = str(payload.get("locale", self.locale))
        self.game_path = str(payload.get("game_path", self.game_path))
        self.parallel_download = bool(payload.get("parallel_download", self.parallel_download))
        self.download_threads = max(1, int(payload.get("download_threads", self.download_threads)))
        profiles_payload = payload.get("profiles", {})
        if isinstance(profiles_payload, dict):
            for meta in MENU_ITEMS:
                profile_payload = profiles_payload.get(meta.key, {})
                if isinstance(profile_payload, dict):
                    # ``from_mapping`` defaults ``save_path`` to ``""`` when
                    # the JSON row omits it; fall back to the built-in
                    # default save_path so the offline mode and OSFR server
                    # continue to find their per-profile data.
                    from_mapping = ServerProfile.from_mapping(meta.key, meta, profile_payload)
                    if not from_mapping.save_path:
                        from_mapping = ServerProfile(
                            key=from_mapping.key,
                            title=from_mapping.title,
                            subtitle=from_mapping.subtitle,
                            name=from_mapping.name,
                            description=from_mapping.description,
                            server_url=from_mapping.server_url,
                            login_server=from_mapping.login_server,
                            login_api_url=from_mapping.login_api_url,
                            save_path=meta.key,
                            username=from_mapping.username,
                            password=from_mapping.password,
                            remember_username=from_mapping.remember_username,
                            remember_password=from_mapping.remember_password,
                            icon_name=from_mapping.icon_name,
                            client_container=from_mapping.client_container,
                        )
                    self.profiles[meta.key] = from_mapping
            # Custom profiles that were stored in the v1.0.0 JSON under any
            # key other than the two built-in menu items were silently
            # dropped. Walk them here and re-attach them under a stable
            # ``custom_<slug>`` key so the user does not lose servers.
            builtin_keys = {meta.key for meta in MENU_ITEMS}
            used_keys = set(self.profile_order)
            for raw_key, profile_payload in profiles_payload.items():
                if raw_key in builtin_keys or not isinstance(profile_payload, dict):
                    continue
                if raw_key in used_keys:
                    continue
                # Build a stable key from the display name (fall back to
                # the URL if the name is empty, which is the v1.0.0
                # convention).
                custom_base = slugify(
                    str(
                        profile_payload.get("name", "")
                        or profile_payload.get("server_url", "")
                        or raw_key
                    ).strip()
                )
                if not custom_base:
                    continue
                custom_key = f"custom_{custom_base}"
                suffix = 2
                while custom_key in used_keys or custom_key in self.profiles:
                    custom_key = f"custom_{custom_base}_{suffix}"
                    suffix += 1
                used_keys.add(custom_key)
                profile = ServerProfile.from_mapping(custom_key, MenuProfileMeta(custom_key, str(profile_payload.get("name", raw_key)).strip() or "Custom Server", "Custom Server"), profile_payload)
                self.profiles[custom_key] = profile
                if custom_key not in self.profile_order:
                    self.profile_order.append(custom_key)
        self.save()
        LOGGER.info("Migrated legacy JSON settings from %s", LEGACY_SETTINGS_PATH)

    def _migrate_v110_appdata_settings(self) -> None:
        """Migrate v1.1.0 AppData state to the portable layout.

        v1.1.0 stored settings, per-profile clients and downloaded Node under
        ``%LOCALAPPDATA%\\OSFR Launcher\\``. v1.1.1 moved everything next to
        the launcher binary so the install is portable. To avoid dropping
        user data on upgrade, copy the v1.1.0 ``Launcher.xml`` and the
        per-profile ``servers\\`` tree into the new portable locations.
        """
        if LEGACY_V110_SETTINGS_PATH is None:
            return
        if not LEGACY_V110_SETTINGS_PATH.exists():
            return
        # Validate the source XML before copying: a broken v1.1.0 file used
        # to be copied verbatim, after which every subsequent ``load()``
        # would fail to parse the new portable copy. If the v1.1.0 file is
        # unparseable, leave it in place so the user can recover it.
        try:
            source_text = LEGACY_V110_SETTINGS_PATH.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            LOGGER.exception("Failed to read v1.1.0 settings from %s; leaving in place for recovery.", LEGACY_V110_SETTINGS_PATH)
            return
        try:
            ET.fromstring(source_text)
        except ET.ParseError:
            corrupt_marker = LEGACY_V110_SETTINGS_PATH.with_suffix(
                f".corrupt-{int(time.time())}.xml"
            )
            try:
                LEGACY_V110_SETTINGS_PATH.rename(corrupt_marker)
                LOGGER.error(
                    "v1.1.0 settings at %s are unparseable; renamed to %s. "
                    "Launcher will start with defaults.",
                    LEGACY_V110_SETTINGS_PATH,
                    corrupt_marker,
                )
            except OSError:
                LOGGER.exception("v1.1.0 settings at %s are unparseable and could not be renamed.", LEGACY_V110_SETTINGS_PATH)
            return
        try:
            SETTINGS_PATH.parent.mkdir(parents=True, exist_ok=True)
            SETTINGS_PATH.write_text(source_text, encoding="utf-8")
            LOGGER.info("Migrated v1.1.0 settings from %s -> %s", LEGACY_V110_SETTINGS_PATH, SETTINGS_PATH)
        except OSError:
            LOGGER.exception("Failed to migrate v1.1.0 settings from %s", LEGACY_V110_SETTINGS_PATH)
            return

        if LEGACY_V110_SERVERS_ROOT is None or not LEGACY_V110_SERVERS_ROOT.exists():
            return
        if SERVERS_ROOT.exists() and any(SERVERS_ROOT.iterdir()):
            LOGGER.info("Portable servers root %s already populated; skipping v1.1.0 client migration.", SERVERS_ROOT)
            return
        try:
            SERVERS_ROOT.parent.mkdir(parents=True, exist_ok=True)
            # ``dirs_exist_ok=True`` so the migration works when an empty
            # ``Servers/`` directory was left behind by a half-completed
            # previous launch.
            shutil.copytree(LEGACY_V110_SERVERS_ROOT, SERVERS_ROOT, dirs_exist_ok=True)
            LOGGER.info("Migrated v1.1.0 per-profile clients from %s -> %s", LEGACY_V110_SERVERS_ROOT, SERVERS_ROOT)
        except OSError:
            LOGGER.exception("Failed to migrate v1.1.0 servers root from %s", LEGACY_V110_SERVERS_ROOT)
