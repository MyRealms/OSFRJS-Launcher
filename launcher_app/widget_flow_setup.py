from __future__ import annotations

import threading
import time
from pathlib import Path

from PySide6.QtWidgets import QApplication, QFileDialog

from .constants import APP_DIR, CLIENT_EXECUTABLE_NAME
from .settings import LauncherSettings


class LauncherWidgetSetupFlowMixin:
    def _on_setup_name_changed(self, value: str) -> None:
        self.setup_display_name = value

    def _on_setup_game_path_changed(self, value: str) -> None:
        self.setup_game_path = value

    def _submit_active_form_from_keyboard(self) -> None:
        if self.overlay_kind in {"login", "text_input", "server_profile"}:
            self._submit_overlay()
            return
        if self.current_screen in {"setup", "settings"}:
            self._submit_setup_form(settings_mode=self.current_screen == "settings")

    def _tick_animation(self) -> None:
        self.frame_tick += 1
        self._is_game_running()
        self._consume_pending_server_status_result()
        if self.frame_tick % 8 == 0:
            self.loading_tick += 1
        if self.overlay_kind is None and self.hero_backgrounds and self.frame_tick % 625 == 0:
            self.hero_background_index = (self.hero_background_index + 1) % len(self.hero_backgrounds)
        if abs(self.menu_highlight_index - self.menu_highlight_target) > 0.001:
            self.menu_highlight_index += (self.menu_highlight_target - self.menu_highlight_index) * 0.24
            if abs(self.menu_highlight_index - self.menu_highlight_target) < 0.01:
                self.menu_highlight_index = self.menu_highlight_target
        if self.current_screen == "main" and self.main_intro_tick < 42:
            self.main_intro_tick += 1
        if self.current_screen == "settings" and self.settings_intro_tick < 14:
            self.settings_intro_tick += 1
        if self.current_screen == "main" and self.settings_transition_pending and self.main_outro_tick < 14:
            self.main_outro_tick += 1
            if self.main_outro_tick >= 14:
                self.settings_transition_pending = False
                self.main_outro_tick = 14
                self.setup_display_name = self.settings.display_name
                self.setup_game_path = self.settings.game_path
                self.current_screen = "settings"
                self.settings_intro_tick = 0
                self.update()
                QApplication.processEvents()
        if self.current_screen == "main" and self.play_press_pending and self.play_press_tick < 12:
            self.play_press_tick += 1
            if self.play_press_tick >= 12:
                self.play_press_pending = False
                self.play_press_tick = 0
                self._start_play_flow()
        if self.current_screen == "status" and self.status_transition_tick < 24:
            self.status_transition_tick += 1
        if self.current_screen == "status":
            self.status_title_fade_tick += 1
        if self.overlay_kind and self.overlay_intro_tick < 12:
            self.overlay_intro_tick += 1
        self._schedule_server_status_refresh()
        if self.current_screen in {"loading", "status"} or (
            self.current_screen == "main" and (self.main_intro_tick < 42 or self.play_press_pending or self.settings_transition_pending)
        ) or self.current_screen == "settings" and self.settings_intro_tick < 14 or (
            self.overlay_kind is not None and self.overlay_intro_tick < 12
        ) or abs(self.menu_highlight_index - self.menu_highlight_target) > 0.001 or (
            self.overlay_kind is None and self.frame_tick % 625 == 0
        ):
            self.update()

    def _consume_pending_server_status_result(self) -> None:
        if self.server_status_pending_result is None:
            return
        result = self.server_status_pending_result
        self.server_status_pending_result = None
        self.server_status_poll_in_flight = False
        self.server_status_profile_key = str(result.get("profile_key", ""))
        self.server_status_name = str(result.get("name", ""))
        self.server_status_description = str(result.get("description", ""))
        self.server_status_online = result.get("online") if isinstance(result.get("online"), bool) else None
        self.server_status_players = int(result.get("players", 0) or 0)
        self.server_status_message = str(result.get("message", "Status: Unknown"))
        self.server_status_last_update = time.monotonic()
        self.update()

    def _reset_server_status_display(self, profile_key: str, *, message: str, name: str = "", description: str = "") -> None:
        self.server_status_profile_key = profile_key
        self.server_status_name = name
        self.server_status_description = description
        self.server_status_online = None
        self.server_status_players = 0
        self.server_status_message = message
        self.server_status_last_update = time.monotonic()
        self.server_status_poll_in_flight = False

    def _schedule_server_status_refresh(self) -> None:
        if self.current_screen != "main":
            return
        if self.overlay_kind is not None:
            return

        profile = self.settings.profile_for_index(self.selected_menu)
        if profile.key == "offline_mode":
            if self.server_status_last_rendered_key != profile.key or self.server_status_message != "Status: Local":
                self._reset_server_status_display(
                    profile.key,
                    message="Status: Local",
                    name=profile.name or profile.title,
                    description=profile.description,
                )
                self.server_status_last_rendered_key = profile.key
                self.update()
            return

        if profile.key == "freerealmsjs":
            if self.server_status_last_rendered_key != profile.key or self.server_status_message != "Status: Coming Soon":
                self._reset_server_status_display(
                    profile.key,
                    message="Status: Coming Soon",
                    name=profile.name or profile.title,
                    description=profile.description,
                )
                self.server_status_last_rendered_key = profile.key
                self.update()
            return

        now = time.monotonic()
        profile_changed = self.server_status_last_rendered_key != profile.key
        stale = (now - self.server_status_last_update) >= self.server_status_refresh_interval

        if profile_changed:
            self.server_status_last_rendered_key = profile.key
            self.server_status_name = profile.name or profile.title
            self.server_status_description = profile.description
            self.server_status_message = "Status: Checking..."
            self.server_status_online = None
            self.server_status_players = 0
            self.server_status_last_update = 0.0
            self.update()

        if self.server_status_poll_in_flight:
            return
        if not profile_changed and not stale and self.server_status_profile_key == profile.key:
            return

        self.server_status_poll_in_flight = True
        self.server_status_last_requested = now
        thread = threading.Thread(
            target=self._poll_server_status_snapshot,
            args=(profile.key, profile.server_url, profile.login_server, profile.login_api_url, profile.name or profile.title, profile.description),
            daemon=True,
        )
        thread.start()

    def _poll_server_status_snapshot(
        self,
        profile_key: str,
        server_url: str,
        login_server: str,
        login_api_url: str,
        fallback_name: str,
        fallback_description: str,
    ) -> None:
        result: dict[str, object] = {
            "profile_key": profile_key,
            "name": fallback_name,
            "description": fallback_description,
            "online": False,
            "players": 0,
            "message": "Status: Offline",
        }
        try:
            manifest = self._fetch_server_manifest(server_url, timeout=4)
            resolved_name = manifest.name or fallback_name
            resolved_description = manifest.description or fallback_description
            result["name"] = resolved_name
            result["description"] = resolved_description
            resolved_login_server = login_server or manifest.login_server
            status = self._fetch_server_status(resolved_login_server, timeout=3)
            result["online"] = status.is_online
            result["players"] = status.online_players
            result["message"] = (
                f"Status: Online | Players: {status.online_players}"
                if status.is_online
                else "Status: Offline | Players: 0"
            )
        except Exception:  # noqa: BLE001
            if login_server:
                try:
                    status = self._fetch_server_status(login_server, timeout=3)
                    result["online"] = status.is_online
                    result["players"] = status.online_players
                    result["message"] = (
                        f"Status: Online | Players: {status.online_players}"
                        if status.is_online
                        else "Status: Offline | Players: 0"
                    )
                except Exception:  # noqa: BLE001
                    result["message"] = "Status: Unavailable"
            elif login_api_url:
                result["message"] = "Status: Unavailable"
            else:
                result["message"] = "Status: Unavailable"
        self.server_status_pending_result = result

    def _animated_status_text(self, text: str, animate: bool = True) -> str:
        base = text.strip().rstrip(". ")
        if not animate:
            return text
        suffix = "." * ((self.loading_tick % 3) + 1)
        return f"{base}{suffix}"

    def _open_settings_dialog(self) -> None:
        if self.current_screen == "main":
            self.settings_transition_pending = True
            self.main_outro_tick = 0
            for tick in (2, 5, 8, 11, 14):
                self.main_outro_tick = tick
                self.update()
                QApplication.processEvents()
                time.sleep(0.01)
            self.settings_transition_pending = False
            self.main_outro_tick = 14
            self.setup_display_name = self.settings.display_name
            self.setup_game_path = self.settings.game_path
            self.current_screen = "settings"
            self.settings_intro_tick = 0
            self.update()
            return
        self.setup_display_name = self.settings.display_name
        self.setup_game_path = self.settings.game_path
        self.current_screen = "settings"
        self.settings_intro_tick = 0
        self.update()

    def _refresh_process_state(self) -> None:
        if self.client_process and self.client_process.poll() is not None:
            self.client_process = None
        if self.local_login_process and self.local_login_process.poll() is not None:
            self.local_login_process = None
        if self.local_gateway_process and self.local_gateway_process.poll() is not None:
            self.local_gateway_process = None
        if self.local_authbridge_process and self.local_authbridge_process.poll() is not None:
            self.local_authbridge_process = None

    def _show_error(self, message: str) -> None:
        self._open_message_overlay("OSFR Launcher", message)

    def _ensure_startup_profile(self) -> None:
        self._finish_loading_screen()

    def _finish_loading_screen(self) -> None:
        self.setup_display_name = self.settings.display_name
        self.setup_game_path = self.settings.game_path
        self.current_screen = "main" if self._has_required_setup() else "setup"
        self.main_intro_tick = 0 if self.current_screen == "main" else 42
        self.update()

    def _has_required_setup(self) -> bool:
        if not self.settings.display_name.strip():
            return False
        if not self.settings.game_path.strip():
            return False
        return self._resolve_game_executable(self.settings.game_path) is not None

    def _resolve_game_executable(self, value: str) -> Path | None:
        raw_path = value.strip()
        if not raw_path:
            return None
        path = Path(raw_path)
        if path.is_file() and path.name.lower() == CLIENT_EXECUTABLE_NAME.lower():
            return path
        candidate = path / CLIENT_EXECUTABLE_NAME
        if path.is_dir() and candidate.exists():
            return candidate
        return None

    def _edit_setup_field(self, field_name: str) -> None:
        if field_name == "display_name":
            self.setup_name_edit.setFocus()
            self.setup_name_edit.selectAll()
        elif field_name == "game_path":
            self.setup_game_path_edit.setFocus()
            self.setup_game_path_edit.selectAll()

    def _browse_for_game_path(self) -> None:
        start_dir = self.setup_game_path or self.settings.game_path or str(APP_DIR)
        selected_dir = QFileDialog.getExistingDirectory(
            self,
            "Select Free Realms Folder",
            start_dir,
        )
        if not selected_dir:
            return
        self.setup_game_path = selected_dir
        self.update()

    def _submit_setup_form(self, settings_mode: bool) -> None:
        if not self.setup_display_name.strip():
            self._show_error("Display Name is required.")
            return
        game_executable = self._resolve_game_executable(self.setup_game_path)
        if game_executable is None:
            self._show_error("Please choose a valid folder that contains FreeRealms.exe.")
            return

        self.settings.display_name = self.setup_display_name.strip()
        self.settings.game_path = str(game_executable.parent)
        self.settings.save()
        self.current_screen = "main"
        self.main_intro_tick = 42
        self.main_outro_tick = 14
        self.settings_transition_pending = False
        self.settings_intro_tick = 14
        self.update()

    def _reset_launcher_settings(self) -> None:
        self._open_confirm_overlay(
            "Reset Launcher Settings",
            "Reset launcher settings to defaults?",
            "Reset",
            "Cancel",
            "reset_settings",
        )

    def _set_status_screen(self, title: str, subtitle: str, *, animate_title: bool = True, animate_detail: bool = True) -> None:
        entering_status = self.current_screen != "status"
        self.status_title = title
        self.status_subtitle = subtitle
        self.status_title_animated = animate_title
        self.status_subtitle_animated = animate_detail
        self.current_screen = "status"
        if entering_status:
            self.status_title_fade_tick = 0
            self.status_transition_tick = 0
            for tick in (3, 9, 15, 21, 24):
                self.status_transition_tick = tick
                self.update()
                QApplication.processEvents()
                time.sleep(0.01)
        else:
            self.status_transition_tick = max(self.status_transition_tick, 24)
            self.update()
            QApplication.processEvents()

    def _open_message_overlay(self, title: str, message: str) -> None:
        self.overlay_kind = "message"
        self.overlay_title = title
        self.overlay_message = message
        self.overlay_submit_label = "OK"
        self.overlay_cancel_label = ""
        self.overlay_alt_label = ""
        self.overlay_alt_action = ""
        self.overlay_action = ""
        self.overlay_intro_tick = 0
        self.update()

    def _open_confirm_overlay(self, title: str, message: str, submit_label: str, cancel_label: str, action: str) -> None:
        self.overlay_kind = "confirm"
        self.overlay_title = title
        self.overlay_message = message
        self.overlay_submit_label = submit_label
        self.overlay_cancel_label = cancel_label
        self.overlay_alt_label = ""
        self.overlay_alt_action = ""
        self.overlay_action = action
        self.overlay_intro_tick = 0
        self.update()

    def _open_text_input_overlay(self, title: str, message: str, initial: str, action: str) -> None:
        self.overlay_kind = "text_input"
        self.overlay_title = title
        self.overlay_message = message
        self.overlay_submit_label = "Apply"
        self.overlay_cancel_label = "Cancel"
        self.overlay_alt_label = ""
        self.overlay_alt_action = ""
        self.overlay_action = action
        self.overlay_intro_tick = 0
        self.overlay_text_edit.setText(initial)
        self.overlay_text_edit.setPlaceholderText(title)
        self.overlay_text_edit.setFocus()
        self.overlay_text_edit.selectAll()
        self.update()

    def _open_server_profile_overlay(
        self,
        title: str,
        message: str,
        *,
        name: str,
        server_url: str,
        action: str,
        submit_label: str,
        alt_label: str = "",
        alt_action: str = "",
    ) -> None:
        self.overlay_kind = "server_profile"
        self.overlay_title = title
        self.overlay_message = message
        self.overlay_submit_label = submit_label
        self.overlay_cancel_label = "Cancel"
        self.overlay_alt_label = alt_label
        self.overlay_alt_action = alt_action
        self.overlay_action = action
        self.overlay_link_text = ""
        self.overlay_link_url = ""
        self.overlay_intro_tick = 0
        self.overlay_text_edit.setText(name)
        self.overlay_text_edit.setPlaceholderText("Server Name")
        self.overlay_server_edit.setText(server_url)
        self.overlay_server_edit.setPlaceholderText("https://your-server.example/")
        self.overlay_text_edit.setFocus()
        self.overlay_text_edit.selectAll()
        self.update()

    def _open_add_server_overlay(self) -> None:
        self._open_server_profile_overlay(
            "Add Server",
            "Enter a server name and address to add it to the launcher.",
            name="",
            server_url="https://",
            action="add_server_profile",
            submit_label="Add Server",
        )

    def _open_server_manage_overlay(self, profile_index: int) -> None:
        profile = self.settings.profile_for_index(profile_index)
        self._open_server_profile_overlay(
            "Edit Server",
            "Update the server name and address for this launcher profile.",
            name=profile.title or profile.name,
            server_url=profile.server_url,
            action=f"edit_server_profile:{profile.key}",
            submit_label="Save Changes",
            alt_label="Delete" if self.settings.can_delete_profile(profile.key) else "",
            alt_action=f"confirm_delete_profile:{profile.key}" if self.settings.can_delete_profile(profile.key) else "",
        )

    def _close_overlay(self) -> None:
        self.overlay_kind = None
        self.overlay_title = ""
        self.overlay_message = ""
        self.overlay_submit_label = "OK"
        self.overlay_cancel_label = "Cancel"
        self.overlay_alt_label = ""
        self.overlay_alt_action = ""
        self.overlay_action = ""
        self.overlay_link_text = ""
        self.overlay_link_url = ""
        self.overlay_intro_tick = 12
        for widget in (
            self.overlay_text_edit,
            self.overlay_server_edit,
            self.overlay_username_edit,
            self.overlay_password_edit,
        ):
            widget.hide()
        self.update()

    def _submit_overlay(self) -> None:
        if self.overlay_kind == "message":
            self._close_overlay()
            return
        if self.overlay_kind == "confirm":
            self._apply_overlay_action(self.overlay_action)
            self._close_overlay()
            return
        if self.overlay_kind == "server_profile":
            profile_name = self.overlay_text_edit.text().strip()
            server_url = self.overlay_server_edit.text().strip()
            if not profile_name:
                self._show_error("Server Name is required.")
                return
            if not server_url:
                self._show_error("Server Address is required.")
                return
            if self.overlay_action == "add_server_profile":
                self.settings.add_custom_profile(server_url, profile_name)
                self.settings.save()
                self.selected_menu = max(0, len(self.settings.all_profiles()) - 1)
                self.menu_highlight_index = float(self.selected_menu)
                self.menu_highlight_target = float(self.selected_menu)
                self._close_overlay()
                return
            if self.overlay_action.startswith("edit_server_profile:"):
                profile_key = self.overlay_action.split(":", 1)[1]
                profile = self.settings.profiles.get(profile_key)
                if profile is None:
                    self._show_error("This server profile could not be found.")
                    return
                profile.title = profile_name
                profile.name = profile_name
                profile.server_url = server_url
                profile.login_server = ""
                profile.login_api_url = ""
                self.settings.update_profile(profile)
                self.settings.save()
                self._close_overlay()
                return
            self._close_overlay()
            return
        if self.overlay_kind == "text_input":
            value = self.overlay_text_edit.text().strip()
            if self.overlay_action == "edit_display_name":
                self.setup_display_name = value
            elif self.overlay_action == "edit_game_path":
                self.setup_game_path = value
            elif self.overlay_action.startswith("edit_server_url:"):
                profile_key = self.overlay_action.split(":", 1)[1]
                profile = self.settings.profiles.get(profile_key)
                if profile is None:
                    self._show_error("This server profile could not be found.")
                    return
                if not value:
                    self._show_error("Server URL is required.")
                    return
                profile.server_url = value
                profile.login_server = ""
                profile.login_api_url = ""
                self.settings.update_profile(profile)
                self.settings.save()
            self._close_overlay()
            return
        if self.overlay_kind == "login":
            self._submit_login_overlay()

    def _submit_overlay_alt(self) -> None:
        if not self.overlay_alt_action:
            return
        self._apply_overlay_action(self.overlay_alt_action)

    def _apply_overlay_action(self, action: str) -> None:
        if action.startswith("confirm_delete_profile:"):
            profile_key = action.split(":", 1)[1]
            profile = self.settings.profiles.get(profile_key)
            if profile is None:
                self._show_error("This server profile could not be found.")
                return
            self._open_confirm_overlay(
                "Delete Server",
                f"Remove {profile.title} from the launcher?",
                "Delete",
                "Cancel",
                f"delete_profile:{profile_key}",
            )
            return
        if action.startswith("delete_profile:"):
            profile_key = action.split(":", 1)[1]
            try:
                self.settings.delete_profile(profile_key)
            except ValueError as exc:
                self._show_error(str(exc))
                return
            self.settings.save()
            self.selected_menu = min(self.selected_menu, max(0, len(self.settings.all_profiles()) - 1))
            self.menu_highlight_index = float(self.selected_menu)
            self.menu_highlight_target = float(self.selected_menu)
            self._close_overlay()
            return
        if action == "reset_settings":
            self.settings = LauncherSettings()
            self.settings.save()
            self.setup_display_name = self.settings.display_name
            self.setup_game_path = self.settings.game_path
            self.selected_menu = 0
            self.current_screen = "settings"
            self.settings_intro_tick = 14
            return
        if action == "open_directx":
            import webbrowser

            from .constants import DIRECTX_DOWNLOAD_URL

            webbrowser.open(DIRECTX_DOWNLOAD_URL)

    def _toggle_overlay_flag(self, flag_name: str) -> None:
        if flag_name == "remember_username":
            self.overlay_remember_username = not self.overlay_remember_username
        elif flag_name == "remember_password":
            self.overlay_remember_password = not self.overlay_remember_password
        elif flag_name == "remember_both":
            new_value = not (self.overlay_remember_username and self.overlay_remember_password)
            self.overlay_remember_username = new_value
            self.overlay_remember_password = new_value
        self.update()

    def _open_overlay_link(self) -> None:
        if not self.overlay_link_url:
            return
        import webbrowser

        webbrowser.open(self.overlay_link_url)

    def _focus_overlay_widget(self, field_name: str) -> None:
        mapping = {
            "text": self.overlay_text_edit,
            "server_url": self.overlay_server_edit,
            "username": self.overlay_username_edit,
            "password": self.overlay_password_edit,
        }
        widget = mapping.get(field_name)
        if widget is not None:
            widget.setFocus()
