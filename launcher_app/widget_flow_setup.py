from __future__ import annotations

import logging
import threading
import time
from pathlib import Path

from PySide6.QtWidgets import QApplication, QFileDialog

from .constants import APP_DIR, CLIENT_DATA_DIR, CLIENT_EXECUTABLE_NAME, CLIENT_STASH_ORIGINAL_DIR, SERVERS_ROOT
from .settings import LauncherSettings

LOGGER = logging.getLogger("osfr_launcher")


class LauncherWidgetSetupFlowMixin:
    def _bundled_client_executable(self) -> Path | None:
        # Portable: everything lives next to the launcher. The golden client
        # tree that the user keeps under ``Client\OSFR - Original\`` is the
        # canonical bundled client (see ``CLIENT_STASH_ORIGINAL_DIR``). We
        # also look at a few legacy locations for users who dropped a bare
        # ``Client\FreeRealms.exe`` next to the launcher without renaming it.
        candidates = [
            CLIENT_STASH_ORIGINAL_DIR / CLIENT_EXECUTABLE_NAME,
            CLIENT_DATA_DIR / CLIENT_EXECUTABLE_NAME,
            APP_DIR / "Free Realms" / CLIENT_EXECUTABLE_NAME,
            APP_DIR / "FreeRealms" / CLIENT_EXECUTABLE_NAME,
            APP_DIR / "Game" / CLIENT_EXECUTABLE_NAME,
            APP_DIR / CLIENT_EXECUTABLE_NAME,
        ]
        for candidate in candidates:
            if candidate.exists():
                return candidate
        return None

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
        game_running = self._is_game_running()
        main_motion_paused = game_running and self.current_screen == "main" and self.overlay_kind is None
        self._consume_pending_server_status_result()
        if self.frame_tick % 8 == 0 and not main_motion_paused:
            self.loading_tick += 1
        # Hero carousel rotates on wall-clock time so it stays ~10s per slide
        # regardless of the (now adaptive) timer interval.
        hero_switched = False
        if not game_running and self.overlay_kind is None and self.hero_backgrounds:
            now = time.monotonic()
            if (now - self.hero_background_last_switch) >= 10.0:
                self.hero_background_index = (self.hero_background_index + 1) % len(self.hero_backgrounds)
                self.hero_background_last_switch = now
                hero_switched = True
        if main_motion_paused:
            self.menu_highlight_index = self.menu_highlight_target
            self.main_intro_tick = max(self.main_intro_tick, 42)
            self.main_outro_tick = 14
            self.play_press_pending = False
            self.play_press_tick = 0
        elif abs(self.menu_highlight_index - self.menu_highlight_target) > 0.001:
            self.menu_highlight_index += (self.menu_highlight_target - self.menu_highlight_index) * 0.24
            if abs(self.menu_highlight_index - self.menu_highlight_target) < 0.01:
                self.menu_highlight_index = self.menu_highlight_target
        if self.current_screen == "main" and self.main_intro_tick < 42 and not main_motion_paused:
            self.main_intro_tick += 1
        if self.current_screen == "settings" and self.settings_intro_tick < 14:
            self.settings_intro_tick += 1
        if self.current_screen == "main" and self.settings_transition_pending and self.main_outro_tick < 14 and not main_motion_paused:
            self.main_outro_tick += 1
            if self.main_outro_tick >= 14:
                self.settings_transition_pending = False
                self.main_outro_tick = 14
                self.setup_display_name = self.settings.display_name
                self.setup_game_path = self.settings.game_path
                self.current_screen = "settings"
                self.settings_intro_tick = 0
                self.update()
        if self.current_screen == "main" and self.play_press_pending and self.play_press_tick < 12 and not main_motion_paused:
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
        animating = (
            self.current_screen in {"loading", "status"}
            or (
                self.current_screen == "main"
                and not main_motion_paused
                and (self.main_intro_tick < 42 or self.play_press_pending or self.settings_transition_pending)
            )
            or (self.current_screen == "settings" and self.settings_intro_tick < 14)
            or (self.overlay_kind is not None and self.overlay_intro_tick < 12)
            or abs(self.menu_highlight_index - self.menu_highlight_target) > 0.001
        )
        if animating or hero_switched:
            self.update()

        # Adaptive frame rate: run at full speed only while something is
        # animating; otherwise idle slowly to keep CPU usage low. The timer is
        # never stopped because background polling (status, process, carousel)
        # still needs to tick.
        desired_interval = self.ANIM_INTERVAL_ACTIVE if animating else self.ANIM_INTERVAL_IDLE
        if self.anim_timer.interval() != desired_interval:
            self.anim_timer.setInterval(desired_interval)

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
        if self._is_game_running():
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
        LOGGER.info("Opening settings screen")
        self.setup_display_name = self.settings.display_name
        self.setup_game_path = self.settings.game_path
        self.settings_transition_pending = False
        self.main_outro_tick = 14
        self.current_screen = "settings"
        self.settings_intro_tick = 0
        self.update()

    def _refresh_process_state(self) -> None:
        if self.client_process and self.client_process.poll() is not None:
            LOGGER.info("Client launcher process exited with code %s", self.client_process.returncode)
            self.client_process = None
            # The game just exited; check whether it logged a new critical (G) error.
            self._check_for_client_crash()
            # Re-rewrite GameCrashUrl in case the server pushed a fresh URL
            # during the login handshake. Doing this after the client exits
            # means the next launch already points at the local crash server.
            self._disable_crash_url_post_exit()
        if self.local_login_process and self.local_login_process.poll() is not None:
            self.local_login_process = None
        if self.local_gateway_process and self.local_gateway_process.poll() is not None:
            self.local_gateway_process = None
        if self.local_webapi_process and self.local_webapi_process.poll() is not None:
            self.local_webapi_process = None
        if self.local_authbridge_process and self.local_authbridge_process.poll() is not None:
            self.local_authbridge_process = None

    def _check_for_client_crash(self) -> None:
        """After the game exits, show an in-launcher explanation if it logged a G-error."""
        client_dir = getattr(self, "_active_client_dir", None)
        if client_dir is None:
            return
        try:
            from .error_help import detect_new_crash

            error = detect_new_crash(client_dir, getattr(self, "_crash_log_mtime", 0.0))
        except Exception:  # noqa: BLE001
            LOGGER.exception("Failed to check for client crash")
            return
        finally:
            self._active_client_dir = None

        if error is None:
            return

        LOGGER.warning("Client reported critical error %s: %s", error.code, error.detail)
        suggestions = "\n".join(f"• {line}" for line in error.suggestions)
        detail = f"\n\nDetails: {error.detail}" if error.detail else ""
        message = (
            f"{error.title}  (Error {error.code})\n\n"
            f"{suggestions}{detail}"
        )
        self._open_message_overlay(f"Game Error — {error.code}", message)
        return error

    def _disable_crash_url_post_exit(self) -> None:
        """Re-run config sanitization after the client exits.

        The server can drop a fresh ``GameCrashUrl=`` (or any other
        web URL) into the client config during the login handshake.
        Doing a second pass after the client exits means the *next*
        launch already points at the local crash server again.
        """
        client_dir = getattr(self, "_active_client_dir", None)
        if client_dir is None:
            return
        crash_url = getattr(self, "crash_url", "") or (
            self.crash_server.url if getattr(self, "crash_server", None) else ""
        )
        if not crash_url:
            return
        try:
            from .error_help import disable_crash_url

            disable_crash_url(client_dir, crash_url)
        except Exception:  # noqa: BLE001
            LOGGER.exception("Post-exit crash URL sanitization failed")

    def _show_error(self, message: str) -> None:
        LOGGER.error("Launcher error shown: %s", message)
        self._open_message_overlay("OSFR Launcher", message)

    def _ensure_startup_profile(self) -> None:
        self._finish_loading_screen()

    def _finish_loading_screen(self) -> None:
        bundled_client = self._bundled_client_executable()
        if bundled_client is not None and not self.settings.game_path.strip():
            self.settings.game_path = str(bundled_client.parent)
            self.settings.save()
            LOGGER.info("Auto-detected bundled client path: %s", bundled_client.parent)
        self.setup_display_name = self.settings.display_name
        self.setup_game_path = self.settings.game_path or (str(bundled_client.parent) if bundled_client is not None else "")
        self.current_screen = "main" if self._has_required_setup() else "setup"
        self.main_intro_tick = 0 if self.current_screen == "main" else 42
        LOGGER.info("Loading finished; current_screen=%s", self.current_screen)
        self.update()

    def _has_required_setup(self) -> bool:
        if not self.settings.display_name.strip():
            return False
        if self.settings.game_path.strip():
            return self._resolve_game_executable(self.settings.game_path) is not None
        return self._bundled_client_executable() is not None

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
        bundled_client = self._bundled_client_executable()
        # Portable: open the bundled client directory (next to the launcher)
        # so users naturally land in the writable, portable-friendly spot.
        default_dir = (
            str(CLIENT_DATA_DIR)
            if bundled_client is None
            else str(bundled_client.parent)
        )
        start_dir = self.setup_game_path or self.settings.game_path or default_dir
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
        game_executable = self._resolve_game_executable(self.setup_game_path) or self._bundled_client_executable()
        if game_executable is None:
            self._show_error("Please choose a valid folder that contains FreeRealms.exe.")
            return

        self.settings.display_name = self.setup_display_name.strip()
        self.settings.game_path = str(game_executable.parent)
        self.settings.save()
        LOGGER.info(
            "Submitted %s form; display_name=%r game_path=%s",
            "settings" if settings_mode else "setup",
            self.settings.display_name,
            self.settings.game_path,
        )
        self.current_screen = "main"
        self.main_intro_tick = 42
        self.main_outro_tick = 14
        self.settings_transition_pending = False
        self.settings_intro_tick = 14
        self.update()

    def _open_config_folder(self) -> None:
        """Open the folder that contains the launcher's settings/manifest (Launcher.xml)."""
        import subprocess
        import sys

        from .constants import APP_DIR, SETTINGS_PATH

        try:
            APP_DIR.mkdir(parents=True, exist_ok=True)
        except OSError:
            pass

        # Prefer selecting the settings file directly when the OS supports it.
        target = APP_DIR
        try:
            if sys.platform == "win32":
                if SETTINGS_PATH.exists():
                    subprocess.Popen(["explorer", "/select,", str(SETTINGS_PATH)])
                else:
                    subprocess.Popen(["explorer", str(target)])
            elif sys.platform == "darwin":
                if SETTINGS_PATH.exists():
                    subprocess.Popen(["open", "-R", str(SETTINGS_PATH)])
                else:
                    subprocess.Popen(["open", str(target)])
            else:
                subprocess.Popen(["xdg-open", str(target)])
            LOGGER.info("Opened config folder: %s", target)
        except Exception:  # noqa: BLE001
            LOGGER.exception("Failed to open config folder")
            self._open_message_overlay(
                "Config Folder",
                f"Could not open the folder automatically.\n\nLocation:\n{target}",
            )

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
        # Snapshot the current overlay so dismissing this message returns
        # to the form the user was on (Add/Edit Server) instead of
        # dumping them back to the main screen and erasing their input.
        # Without this snapshot, every validation error in the Add
        # Server flow silently closed the overlay.
        if self.overlay_kind and self.overlay_kind != "message":
            self._overlay_snapshot = {
                "kind": self.overlay_kind,
                "title": self.overlay_title,
                "message": self.overlay_message,
                "submit_label": self.overlay_submit_label,
                "cancel_label": self.overlay_cancel_label,
                "alt_label": self.overlay_alt_label,
                "alt_action": self.overlay_alt_action,
                "action": self.overlay_action,
                "text": self.overlay_text_edit.text(),
                "server_url": self.overlay_server_edit.text(),
                "username": self.overlay_username_edit.text(),
                "password": self.overlay_password_edit.text(),
                "remember_username": bool(self.overlay_remember_username),
                "remember_password": bool(self.overlay_remember_password),
                "icon_name": self.overlay_icon_name,
                "icon_strip_scroll": float(self.overlay_icon_strip_scroll),
            }
        else:
            self._overlay_snapshot = None
        LOGGER.info("Open message overlay: title=%r message=%r", title, message)
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

    def check_for_update_async(self) -> None:
        """Check GitHub for a newer launcher version in the background and prompt if found."""
        from PySide6.QtCore import QTimer

        from .dependencies import check_for_update

        def _worker() -> None:
            available, latest_version, release_url = check_for_update()
            if not available:
                return

            def _prompt() -> None:
                self.pending_update_url = release_url
                self._open_confirm_overlay(
                    "Update Available",
                    f"A new launcher version (v{latest_version}) is available. "
                    "Open the download page?",
                    "Download",
                    "Later",
                    "open_update",
                )

            # Marshal back onto the UI thread before touching widget state.
            QTimer.singleShot(0, _prompt)

        threading.Thread(target=_worker, daemon=True).start()

    def _open_confirm_overlay(self, title: str, message: str, submit_label: str, cancel_label: str, action: str) -> None:
        LOGGER.info("Open confirm overlay: title=%r action=%s", title, action)
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
        LOGGER.info("Open text input overlay: title=%r action=%s", title, action)
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
        username: str = "",
        password: str = "",
        remember_credentials: bool = False,
        icon_name: str = "",
    ) -> None:
        LOGGER.info("Open server profile overlay: title=%r action=%s server_url=%s icon=%s", title, action, server_url, icon_name)
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
        self.overlay_username_edit.setText(username)
        self.overlay_username_edit.setPlaceholderText("Username")
        self.overlay_password_edit.setText(password)
        self.overlay_password_edit.setPlaceholderText("Password")
        self.overlay_remember_username = remember_credentials
        self.overlay_remember_password = remember_credentials
        self.overlay_icon_name = icon_name
        self.overlay_icon_strip_scroll = 0.0
        self.overlay_text_edit.setFocus()
        self.overlay_text_edit.selectAll()
        self.update()

    def _open_add_server_overlay(self) -> None:
        self._open_server_profile_overlay(
            "Add Server",
            "Enter a server name and address. You can use an IP (e.g. 192.168.1.50:3000) or a URL. "
            "A sandboxed client copy is created automatically from OSFR - Original.",
            name="",
            server_url="",
            action="add_server_profile",
            submit_label="Add Server",
        )

    def _open_server_manage_overlay(self, profile_index: int) -> None:
        profile = self.settings.profile_for_index(profile_index)
        remember = bool(profile.remember_password and profile.remember_username)
        self._open_server_profile_overlay(
            "Edit Server",
            "Update the server name, address, icon, and login credentials for this profile.",
            name=profile.title or profile.name,
            server_url=profile.server_url,
            action=f"edit_server_profile:{profile.key}",
            submit_label="Save Changes",
            alt_label="Delete" if self.settings.can_delete_profile(profile.key) else "",
            alt_action=f"confirm_delete_profile:{profile.key}" if self.settings.can_delete_profile(profile.key) else "",
            username=profile.username if remember else "",
            password=profile.password if remember else "",
            remember_credentials=remember,
            icon_name=profile.icon_name,
        )

    def _select_overlay_icon(self, icon_name: str) -> None:
        if self.overlay_kind != "server_profile":
            return
        LOGGER.info("Selected server icon: %s", icon_name)
        self.overlay_icon_name = icon_name
        self.update()

    def _close_overlay(self) -> None:
        # If a message overlay is closing AND we have a snapshot of the
        # overlay that opened it, restore that snapshot so the user
        # lands back on the form they were filling in (validation
        # error on Add Server -> message -> OK -> Add Server again,
        # with the typed name / URL / icon preserved).
        snapshot = getattr(self, "_overlay_snapshot", None)
        if self.overlay_kind == "message" and snapshot is not None:
            self._open_server_profile_overlay(
                snapshot["title"],
                snapshot["message"],
                name=snapshot["text"],
                server_url=snapshot["server_url"],
                action=snapshot["action"],
                submit_label=snapshot["submit_label"],
                alt_label=snapshot["alt_label"],
                alt_action=snapshot["alt_action"],
                username=snapshot["username"],
                password=snapshot["password"],
                remember_credentials=(snapshot["remember_username"] and snapshot["remember_password"]),
                icon_name=snapshot["icon_name"],
            )
            self.overlay_icon_strip_scroll = snapshot["icon_strip_scroll"]
            self._overlay_snapshot = None
            self.update()
            return
        LOGGER.info("Close overlay: kind=%s action=%s", self.overlay_kind, self.overlay_action)
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
        self.overlay_icon_name = ""
        self.overlay_icon_strip_scroll = 0.0
        for widget in (
            self.overlay_text_edit,
            self.overlay_server_edit,
            self.overlay_username_edit,
            self.overlay_password_edit,
        ):
            widget.hide()
        self.update()

    def _submit_overlay(self) -> None:
        LOGGER.info("Submit overlay: kind=%s action=%s", self.overlay_kind, self.overlay_action)
        if self.overlay_kind == "message":
            self._close_overlay()
            return
        if self.overlay_kind == "confirm":
            self._apply_overlay_action(self.overlay_action)
            self._close_overlay()
            return
        if self.overlay_kind == "server_profile":
            from .utils import normalize_server_url

            profile_name = self.overlay_text_edit.text().strip()
            server_url = normalize_server_url(self.overlay_server_edit.text())
            username = self.overlay_username_edit.text().strip()
            password = self.overlay_password_edit.text()
            remember = bool(self.overlay_remember_username and self.overlay_remember_password)
            if not profile_name:
                self._show_error("Server Name is required.")
                return
            if not server_url:
                self._show_error("Server Address is required.")
                return
            if self.overlay_action == "add_server_profile":
                from .client_containers import (
                    ClientContainerError,
                    create_container,
                    is_golden_missing,
                )

                # Reject duplicate server URLs so the user does not
                # accidentally clone the golden client multiple times
                # for the same endpoint.
                normalized_url = server_url.rstrip("/")
                for existing in self.settings.profiles.values():
                    if existing.server_url.rstrip("/") == normalized_url:
                        self._show_error(
                            f"A server with address '{server_url}' already "
                            f"exists. Use Edit Server to modify it instead."
                        )
                        return

                # Every newly added server gets its own sandboxed client
                # copy, cloned from the user-managed "OSFR - Original"
                # tree. If the original is missing we refuse to add the
                # server rather than silently sharing state with another
                # server.
                if is_golden_missing():
                    self._show_error(
                        "Cannot add a new server: the golden client tree "
                        "is missing. Place your clean Free Realms client at:\n"
                        "Client\\OSFR - Original\\\n"
                        "and try again."
                    )
                    return

                # Two-phase add: (1) register the profile + persist to XML
                #    FIRST so a failed save never leaves a multi-GB
                #    orphaned container, (2) then clone the container. If
                #    the clone fails after the profile is registered we
                #    roll back the profile so the on-disk state matches
                #    the in-memory state.
                new_profile = self.settings.add_custom_profile(
                    server_url,
                    profile_name,
                    client_container="OSFR - Original",  # placeholder until clone finishes
                )
                if remember:
                    new_profile.username = username
                    new_profile.password = password
                    new_profile.remember_username = True
                    new_profile.remember_password = True
                else:
                    new_profile.username = ""
                    new_profile.password = ""
                    new_profile.remember_username = False
                    new_profile.remember_password = False
                new_profile.icon_name = self.overlay_icon_name
                self.settings.update_profile(new_profile)
                try:
                    self.settings.save()
                except OSError as exc:
                    LOGGER.exception("Failed to save settings before cloning container")
                    self._show_error(
                        "Could not save the new server to Launcher.xml. "
                        "The container was not cloned and the server was not added.\n\n"
                        f"Details: {exc}"
                    )
                    self.settings.delete_profile(new_profile.key)
                    return

                try:
                    # The golden client tree is ~1.65 GB and the copy
                    # can take tens of seconds. Run it on the GUI thread
                    # but pump the event loop every chunk so the window
                    # does not appear frozen and the user can read the
                    # overlay state. (A full QThread / cancel-button
                    # refactor is deferred to a follow-up release.)
                    from PySide6.QtWidgets import QApplication
                    self.overlay_kind = "message"
                    self.overlay_title = "Working"
                    self.overlay_message = (
                        f"Creating client container for {profile_name}...\n"
                        "This can take a few minutes depending on disk speed."
                    )
                    self.overlay_submit_label = ""
                    self.overlay_cancel_label = ""
                    self.overlay_alt_label = ""
                    self.overlay_alt_action = ""
                    self.overlay_action = ""
                    self.overlay_intro_tick = 0
                    self.update()
                    QApplication.processEvents()
                    created = create_container(profile_name)
                    new_profile.client_container = created.name
                    LOGGER.info("Created client container %s for new server %s", created.name, profile_name)
                except ClientContainerError as exc:
                    LOGGER.exception("Failed to create client container for %s", profile_name)
                    self._show_error(
                        f"Could not create the client container:\n{exc}\n\n"
                        "The server profile was removed to keep the launcher "
                        "state consistent. Try again once the underlying issue "
                        "(disk full, permission, antivirus lock) is resolved."
                    )
                    self.settings.delete_profile(new_profile.key)
                    try:
                        self.settings.save()
                    except OSError:
                        LOGGER.exception("Failed to save settings after profile rollback")
                    return

                # Container created successfully; persist the final
                # ``client_container`` value.
                self.settings.update_profile(new_profile)
                try:
                    self.settings.save()
                except OSError:
                    LOGGER.exception("Failed to save settings after container clone")
                    # The container is on disk but the XML still references
                    # the placeholder; log loudly so the user knows.
                    self._show_error(
                        "Created the client container but failed to update "
                        "Launcher.xml. The new server will fall back to the "
                        "default golden client until you re-open the launcher."
                    )

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
                profile.icon_name = self.overlay_icon_name
                if remember:
                    profile.username = username
                    profile.password = password
                    profile.remember_username = True
                    profile.remember_password = True
                else:
                    # The user opted out of remembering credentials for
                    # this session. Only drop the *password*; the
                    # username is harmless to keep on disk and dropping
                    # both used to silently destroy the username too,
                    # which made re-entering credentials a second
                    # guessing game.
                    profile.password = ""
                    profile.remember_password = False
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
        LOGGER.info("Submit overlay alt action: %s", self.overlay_alt_action)
        self._apply_overlay_action(self.overlay_alt_action)

    def _apply_overlay_action(self, action: str) -> None:
        LOGGER.info("Apply overlay action: %s", action)
        if action.startswith("confirm_delete_profile:"):
            profile_key = action.split(":", 1)[1]
            profile = self.settings.profiles.get(profile_key)
            if profile is None:
                self._show_error("This server profile could not be found.")
                return
            # Warn the user that the per-profile directory under
            # ``Servers/<save>/`` and the sandboxed client container
            # under ``Client/OSFR - <name>/`` are preserved and would be
            # re-attached if the user re-adds a server with the same
            # name later. Without this hint the user has no idea that
            # deleting a profile is non-destructive.
            from .constants import SERVERS_ROOT, CLIENT_STASH_DIR
            save_path = profile.save_path or profile.key
            saved_dir = SERVERS_ROOT / save_path
            saved_dir_note = (
                f"\n\nThe directory\n  {saved_dir}\n"
                "and its saves will be kept on disk. Delete them manually "
                "if you want them gone for good."
            )
            self._open_confirm_overlay(
                "Delete Server",
                f"Remove {profile.title} from the launcher?{saved_dir_note}",
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
        if action == "open_update":
            import webbrowser

            from .constants import GITHUB_RELEASES_URL

            webbrowser.open(self.pending_update_url or GITHUB_RELEASES_URL)

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
