from __future__ import annotations

import xml.etree.ElementTree as ET

from .constants import LEGACY_SETTINGS_PATH, SETTINGS_PATH
from .models import MENU_ITEMS, ServerProfile
from .utils import parse_bool, parse_int, slugify


class LauncherSettings:
    def __init__(self) -> None:
        self.display_name = ""
        self.game_path = ""
        self.locale = "en_US"
        self.parallel_download = True
        self.download_threads = 4
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
        settings = cls()
        if not SETTINGS_PATH.exists():
            if LEGACY_SETTINGS_PATH.exists():
                settings._load_legacy_json()
            return settings

        try:
            root = ET.fromstring(SETTINGS_PATH.read_text(encoding="utf-8"))
        except (OSError, ET.ParseError):
            return settings

        settings.locale = (root.findtext("Locale") or settings.locale).strip() or settings.locale
        settings.display_name = (root.findtext("DisplayName") or settings.display_name).strip()
        settings.game_path = (root.findtext("GamePath") or settings.game_path).strip()
        settings.parallel_download = parse_bool(root.findtext("ParallelDownload"), settings.parallel_download)
        settings.download_threads = max(1, parse_int(root.findtext("DownloadThreads"), settings.download_threads))

        server_nodes = root.findall("./ServerInfoList/ServerInfo")
        used_keys: set[str] = set()
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
                )
            if key not in settings.profile_order:
                settings.profile_order.append(key)
        return settings

    def save(self) -> None:
        SETTINGS_PATH.parent.mkdir(parents=True, exist_ok=True)
        root = ET.Element("Settings")
        ET.SubElement(root, "DiscordActivity").text = "true"
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
            ET.SubElement(node, "Username").text = profile.username if profile.remember_username else ""
            ET.SubElement(node, "RememberUsername").text = "true" if profile.remember_username else "false"
            ET.SubElement(node, "Password").text = profile.password if profile.remember_password else ""
            ET.SubElement(node, "RememberPassword").text = "true" if profile.remember_password else "false"

        ET.indent(root)
        xml_text = ET.tostring(root, encoding="unicode", xml_declaration=True)
        SETTINGS_PATH.write_text(xml_text, encoding="utf-8")

    def profile_for_index(self, index: int) -> ServerProfile:
        key = self.profile_order[index]
        return self.profiles[key]

    def all_profiles(self) -> list[ServerProfile]:
        return [self.profiles[key] for key in self.profile_order if key in self.profiles]

    def update_profile(self, profile: ServerProfile) -> None:
        self.profiles[profile.key] = profile
        if profile.key not in self.profile_order:
            self.profile_order.append(profile.key)

    def add_custom_profile(self, server_url: str, name: str = "") -> ServerProfile:
        base_name = name.strip() or "Custom Server"
        host_key = slugify(base_name if name.strip() else server_url)
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
            server_url=server_url.strip(),
            save_path=key,
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
        name = str(payload.get("name", "")).strip().lower()
        save_path = str(payload.get("save_path", "")).strip().lower()
        if (name == "local" or save_path == "local") and "offline_mode" not in used_keys:
            return "offline_mode"
        if ("os free realms" in name or "osfr" in name) and "osfr_server" not in used_keys:
            return "osfr_server"
        if save_path == "freerealmsjs" and "freerealmsjs" not in used_keys:
            return "freerealmsjs"
        if name == "freerealmsjs" and "freerealmsjs" not in used_keys:
            return "freerealmsjs"
        custom_base = slugify(str(payload.get("save_path", "") or payload.get("name", "") or payload.get("server_url", "")).strip())
        if custom_base:
            custom_key = f"custom_{custom_base}"
            suffix = 2
            while custom_key in used_keys:
                custom_key = f"custom_{custom_base}_{suffix}"
                suffix += 1
            return custom_key
        for meta in MENU_ITEMS:
            if meta.key not in used_keys:
                return meta.key
        return None

    def _load_legacy_json(self) -> None:
        try:
            import json

            payload = json.loads(LEGACY_SETTINGS_PATH.read_text(encoding="utf-8"))
        except Exception:  # noqa: BLE001
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
                    self.profiles[meta.key] = ServerProfile.from_mapping(meta.key, meta, profile_payload)
        self.save()
