from __future__ import annotations

import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time

import requests
from .constants import APP_DIR, CLIENT_EXECUTABLE_NAME, LOCAL_SERVER_BUNDLE_DIR, LOCAL_SERVER_RUNTIME_DIR
from .models import LauncherError, LoginResult, ServerManifest, ServerProfile, ServerStatus
from .utils import join_url, slugify


class LauncherWidgetLaunchFlowMixin:
    def _decode_process_output(self, payload: bytes) -> str:
        for encoding in ("utf-8", "utf-16-le", "cp1254", "cp1252"):
            try:
                return payload.decode(encoding)
            except UnicodeDecodeError:
                continue
        return payload.decode("utf-8", errors="replace")

    def _is_game_running(self, *, force_refresh: bool = False) -> bool:
        now = time.monotonic()
        if force_refresh or (now - self.game_running_last_probe) >= 1.0:
            self._refresh_process_state()
            running = self._process_is_running(self.client_process) or self._tasklist_has_process(CLIENT_EXECUTABLE_NAME)
            state_changed = running != self.game_running_cached
            self.game_running_cached = running
            self.game_running_last_probe = now
            if state_changed and self.current_screen == "main":
                self.update()
        return self.game_running_cached

    def _local_server_runtime_paths(self) -> dict[str, Path]:
        runtime_dir = LOCAL_SERVER_RUNTIME_DIR
        emulator_dir = runtime_dir / "Emulator"
        authbridge_dir = runtime_dir / "AuthBridge"
        node_dir = runtime_dir / "node"
        return {
            "runtime_dir": runtime_dir,
            "login_exe": emulator_dir / "Sanctuary.Login.exe",
            "gateway_exe": emulator_dir / "Sanctuary.Gateway.exe",
            "node_exe": node_dir / "node.exe",
            "authbridge_script": authbridge_dir / "server.mjs",
            "emulator_dir": emulator_dir,
            "authbridge_dir": authbridge_dir,
        }

    def _ensure_local_server_runtime(self) -> Path:
        paths = self._local_server_runtime_paths()
        required = (
            paths["login_exe"],
            paths["gateway_exe"],
            paths["node_exe"],
            paths["authbridge_script"],
        )
        if LOCAL_SERVER_RUNTIME_DIR.exists() and all(path.exists() for path in required):
            return LOCAL_SERVER_RUNTIME_DIR
        if not LOCAL_SERVER_BUNDLE_DIR.exists():
            raise LauncherError(f"Local server runtime is missing: {LOCAL_SERVER_BUNDLE_DIR}")
        shutil.copytree(LOCAL_SERVER_BUNDLE_DIR, LOCAL_SERVER_RUNTIME_DIR, dirs_exist_ok=True)
        if not all(path.exists() for path in required):
            missing = ", ".join(path.name for path in required if not path.exists())
            raise LauncherError(f"Local server runtime is incomplete: {missing}")
        return LOCAL_SERVER_RUNTIME_DIR

    def _background_creation_flags(self) -> int:
        return getattr(subprocess, "CREATE_NO_WINDOW", 0) if sys.platform == "win32" else 0

    def _process_is_running(self, proc: subprocess.Popen[str] | None) -> bool:
        return proc is not None and proc.poll() is None

    def _tasklist_has_process(self, image_name: str) -> bool:
        if sys.platform != "win32":
            return False
        try:
            result = subprocess.run(
                ["tasklist", "/FI", f"IMAGENAME eq {image_name}", "/NH"],
                capture_output=True,
                check=False,
                creationflags=self._background_creation_flags(),
            )
        except OSError:
            return False
        stdout_text = self._decode_process_output(result.stdout or b"")
        return image_name.lower() in stdout_text.lower()

    def _normalize_process_path(self, value: str | Path) -> str:
        try:
            return str(Path(value).resolve()).replace("/", "\\").lower()
        except OSError:
            return str(value).replace("/", "\\").lower()

    def _runtime_process_snapshot(self) -> list[dict[str, object]]:
        if sys.platform != "win32":
            return []
        command = (
            "Get-CimInstance Win32_Process | "
            "Select-Object ProcessId,Name,ExecutablePath,CommandLine | "
            "ConvertTo-Json -Compress"
        )
        try:
            result = subprocess.run(
                ["powershell", "-NoProfile", "-Command", command],
                capture_output=True,
                check=False,
                creationflags=self._background_creation_flags(),
            )
        except OSError:
            return []
        stdout_text = self._decode_process_output(result.stdout or b"")
        if result.returncode != 0 or not stdout_text.strip():
            return []
        try:
            payload = json.loads(stdout_text)
        except json.JSONDecodeError:
            return []
        if isinstance(payload, dict):
            return [payload]
        if isinstance(payload, list):
            return [item for item in payload if isinstance(item, dict)]
        return []

    def _kill_process_id(self, pid: int) -> None:
        if sys.platform != "win32":
            return
        try:
            subprocess.run(
                ["taskkill", "/PID", str(pid), "/T", "/F"],
                capture_output=True,
                check=False,
                creationflags=self._background_creation_flags(),
            )
        except OSError:
            return

    def _cleanup_stale_local_server_processes(self) -> None:
        paths = self._local_server_runtime_paths()
        expected_login = self._normalize_process_path(paths["login_exe"])
        expected_gateway = self._normalize_process_path(paths["gateway_exe"])
        expected_node = self._normalize_process_path(paths["node_exe"])
        expected_authbridge = self._normalize_process_path(paths["authbridge_script"])

        stale_pids: set[int] = set()
        for process in self._runtime_process_snapshot():
            try:
                pid = int(process.get("ProcessId", 0) or 0)
            except (TypeError, ValueError):
                continue
            executable_path = self._normalize_process_path(process.get("ExecutablePath", "") or "")
            command_line = self._normalize_process_path(process.get("CommandLine", "") or "")
            if not pid or not executable_path:
                continue
            if executable_path in {expected_login, expected_gateway}:
                stale_pids.add(pid)
                continue
            if executable_path == expected_node and expected_authbridge in command_line:
                stale_pids.add(pid)

        for pid in sorted(stale_pids):
            self._kill_process_id(pid)

        self.local_login_process = None
        self.local_gateway_process = None
        self.local_authbridge_process = None

    def _start_local_server_process(
        self,
        executable: Path,
        *,
        arguments: list[str] | None = None,
        working_directory: Path,
    ) -> subprocess.Popen[str]:
        if not executable.exists():
            raise LauncherError(f"Missing local server component: {executable}")
        command = [str(executable)]
        if arguments:
            command.extend(arguments)
        startupinfo = None
        if sys.platform == "win32":
            startupinfo = subprocess.STARTUPINFO()
            startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        try:
            return subprocess.Popen(
                command,
                cwd=str(working_directory),
                creationflags=self._background_creation_flags(),
                startupinfo=startupinfo,
            )
        except OSError as exc:
            raise LauncherError(f"Failed to start local server component {executable.name}: {exc}") from exc

    def _authbridge_ready(self, profile: ServerProfile) -> bool:
        try:
            requests.get(join_url(profile.server_url, "ServerManifest.xml"), timeout=3)
        except requests.RequestException:
            return False
        return True

    def _ensure_offline_server_started(self, profile: ServerProfile) -> None:
        self._refresh_process_state()
        self._ensure_local_server_runtime()
        paths = self._local_server_runtime_paths()

        login_running = self._process_is_running(self.local_login_process) or self._tasklist_has_process("Sanctuary.Login.exe")
        gateway_running = self._process_is_running(self.local_gateway_process) or self._tasklist_has_process("Sanctuary.Gateway.exe")
        authbridge_running = self._process_is_running(self.local_authbridge_process) or self._authbridge_ready(profile)

        if not login_running:
            self.local_login_process = self._start_local_server_process(
                paths["login_exe"],
                working_directory=paths["emulator_dir"],
            )
            time.sleep(2.0)
        if not gateway_running:
            self.local_gateway_process = self._start_local_server_process(
                paths["gateway_exe"],
                working_directory=paths["emulator_dir"],
            )
            time.sleep(1.0)
        if not authbridge_running:
            self.local_authbridge_process = self._start_local_server_process(
                paths["node_exe"],
                arguments=[str(paths["authbridge_script"])],
                working_directory=paths["authbridge_dir"],
            )

    def _wait_for_offline_server_ready(
        self,
        profile: ServerProfile,
        *,
        timeout_seconds: float = 25.0,
    ) -> tuple[ServerManifest, ServerStatus]:
        deadline = time.monotonic() + timeout_seconds
        last_error: Exception | None = None
        while time.monotonic() < deadline:
            self._refresh_process_state()
            try:
                server_manifest = self._resolve_server_manifest(profile)
                login_server = profile.login_server or server_manifest.login_server
                server_status = self._fetch_server_status(login_server)
                if server_status.is_online:
                    return server_manifest, server_status
            except Exception as exc:  # noqa: BLE001
                last_error = exc
            time.sleep(1.0)

        if last_error is not None:
            raise LauncherError(f"Local server did not become ready in time: {last_error}")
        raise LauncherError("Local server did not become ready in time.")

    def _terminate_process_handle(self, proc: subprocess.Popen[str] | None) -> None:
        if proc is None or proc.poll() is not None:
            return
        try:
            proc.terminate()
            proc.wait(timeout=3)
            return
        except (OSError, subprocess.TimeoutExpired):
            pass
        try:
            proc.kill()
            proc.wait(timeout=2)
        except (OSError, subprocess.TimeoutExpired):
            pass

    def _shutdown_local_server_processes(self) -> None:
        for attribute_name in ("local_authbridge_process", "local_gateway_process", "local_login_process"):
            proc = getattr(self, attribute_name, None)
            self._terminate_process_handle(proc)
            setattr(self, attribute_name, None)
        self._cleanup_stale_local_server_processes()

    def _stop_running_game(self) -> None:
        stopped = False
        if self._process_is_running(self.client_process):
            self._terminate_process_handle(self.client_process)
            self.client_process = None
            stopped = True
        elif self._tasklist_has_process(CLIENT_EXECUTABLE_NAME):
            try:
                subprocess.run(
                    ["taskkill", "/IM", CLIENT_EXECUTABLE_NAME, "/F"],
                    capture_output=True,
                    check=False,
                    creationflags=self._background_creation_flags(),
                )
                stopped = True
            except OSError as exc:
                raise LauncherError(f"Failed to stop {CLIENT_EXECUTABLE_NAME}: {exc}") from exc
        if not stopped:
            self._show_error("FreeRealms.exe is not currently running.")
            return
        self.game_running_cached = False
        self.game_running_last_probe = 0.0
        self.update()

    def _queue_play_flow(self) -> None:
        if self.play_press_pending or self.current_screen != "main":
            return
        if self._is_game_running(force_refresh=True):
            self._stop_running_game()
            return
        self.play_press_tick = 0
        self.play_press_pending = True
        self.update()

    def _start_play_flow(self) -> None:
        self._refresh_process_state()
        if self._is_game_running(force_refresh=True):
            self._show_error("The game is already running for the selected profile.")
            return

        profile = self.settings.profile_for_index(self.selected_menu)
        if profile.key == "freerealmsjs":
            self._open_message_overlay("OSFR Launcher", "Online browser support is coming soon.")
            return
        if self._can_launch_without_overlay(profile):
            self._launch_with_profile_credentials(profile)
            return
        self._open_login_overlay(profile)

    def _can_launch_without_overlay(self, profile: ServerProfile) -> bool:
        if profile.key != "offline_mode":
            return False
        return bool(profile.server_url and profile.username and profile.password)

    def _open_login_overlay(self, profile: ServerProfile) -> None:
        self.overlay_kind = "login"
        self.overlay_title = profile.title
        if profile.key == "osfr_server":
            self.overlay_message = "Please register at www.osfrealms.com if you do not have an account."
            self.overlay_link_text = self.overlay_message
            self.overlay_link_url = "https://www.osfrealms.com"
        else:
            self.overlay_message = "Review the server and login details before launching."
            self.overlay_link_text = ""
            self.overlay_link_url = ""
        self.overlay_submit_label = "Launch"
        self.overlay_cancel_label = "Cancel"
        self.overlay_action = profile.key
        self.overlay_intro_tick = 0
        self.overlay_server_edit.setText(profile.server_url)
        self.overlay_server_edit.setPlaceholderText("https://your-server.example/")
        self.overlay_username_edit.setText(profile.username)
        self.overlay_username_edit.setPlaceholderText("Username")
        self.overlay_password_edit.setText(profile.password)
        self.overlay_password_edit.setPlaceholderText("Password")
        self.overlay_remember_username = profile.remember_username
        self.overlay_remember_password = profile.remember_password
        self.update()

    def _launch_with_profile_credentials(self, updated_profile: ServerProfile) -> None:
        username = updated_profile.username.strip()
        password = updated_profile.password
        if not updated_profile.server_url:
            self._show_error("Server URL is required.")
            return
        if not username or not password:
            self._show_error("Username and password are required.")
            return

        profile_to_save = ServerProfile(
            key=updated_profile.key,
            title=updated_profile.title,
            subtitle=updated_profile.subtitle,
            name=updated_profile.name,
            description=updated_profile.description,
            server_url=updated_profile.server_url,
            login_server=updated_profile.login_server,
            login_api_url=updated_profile.login_api_url,
            save_path=updated_profile.save_path,
            username=username if updated_profile.remember_username else "",
            password=password if updated_profile.remember_password else "",
            remember_username=updated_profile.remember_username,
            remember_password=updated_profile.remember_password,
        )

        self.settings.update_profile(profile_to_save)
        self.settings.save()

        try:
            server_status = None
            if updated_profile.key == "offline_mode":
                self._set_status_screen("Warming", "Waking up Server")
                self._ensure_offline_server_started(updated_profile)
                server_manifest, server_status = self._wait_for_offline_server_ready(updated_profile)
            else:
                self._set_status_screen("Warming", "Waking up Server")
                server_manifest = self._resolve_server_manifest(updated_profile)
            updated_profile.name = server_manifest.name or updated_profile.name
            updated_profile.description = server_manifest.description or updated_profile.description
            if not updated_profile.login_server:
                updated_profile.login_server = server_manifest.login_server
            if updated_profile.login_api_url.startswith("/"):
                updated_profile.login_api_url = join_url(updated_profile.server_url, updated_profile.login_api_url.lstrip("/"))
            if not updated_profile.login_api_url:
                updated_profile.login_api_url = join_url(server_manifest.web_api_url, "login")
            profile_to_save.name = updated_profile.name
            profile_to_save.description = updated_profile.description
            profile_to_save.login_server = updated_profile.login_server
            profile_to_save.login_api_url = updated_profile.login_api_url
            self.settings.update_profile(profile_to_save)
            self.settings.save()

            self._set_status_screen("Warming", "Contacting login server")
            if server_status is None:
                server_status = self._fetch_server_status(updated_profile.login_server or server_manifest.login_server)
            if not server_status.is_online:
                raise LauncherError("Unable to login, the server is offline.")

            self._set_status_screen("Warming", "Checking client files")
            client_manifest = self._fetch_client_manifest(updated_profile.server_url)
            self._verify_client_files(updated_profile, client_manifest)

            self._set_status_screen("Warming", "Logging in")
            login_result = self._login(updated_profile, server_manifest, username, password)

            self._set_status_screen("Warming", "Checking DirectX 9")
            if not self._directx9_available():
                self.current_screen = "main"
                self._offer_directx_download()
                return

            self._set_status_screen("Warming", "Launching Free Realms")
            self.client_process = self._launch_client(updated_profile, server_manifest, login_result)
            self.game_running_cached = True
            self.game_running_last_probe = time.monotonic()
            self.current_screen = "main"
            self.update()
        except LauncherError as exc:
            self.current_screen = "main"
            self._show_error(str(exc))
        except requests.RequestException as exc:
            self.current_screen = "main"
            self._show_error(f"Network error: {exc}")
        except Exception as exc:  # noqa: BLE001
            self.current_screen = "main"
            self._show_error(f"Unexpected error: {exc}")

    def _submit_login_overlay(self) -> None:
        username = self.overlay_username_edit.text().strip()
        password = self.overlay_password_edit.text()
        profile = self.settings.profiles[self.overlay_action]
        updated_profile = ServerProfile(
            key=profile.key,
            title=profile.title,
            subtitle=profile.subtitle,
            name=profile.name,
            description=profile.description,
            server_url=self.overlay_server_edit.text().strip(),
            login_server=profile.login_server,
            login_api_url=profile.login_api_url,
            save_path=profile.save_path,
            username=username,
            password=password,
            remember_username=self.overlay_remember_username,
            remember_password=self.overlay_remember_password,
        )
        if not updated_profile.server_url:
            self._show_error("Server URL is required.")
            return
        if not username or not password:
            self._show_error("Username and password are required.")
            return

        self._close_overlay()
        self._launch_with_profile_credentials(updated_profile)

    def _directx9_available(self) -> bool:
        windows_dir = Path(os.environ.get("WINDIR", r"C:\\Windows"))
        system32 = windows_dir / "System32"
        required = ("d3d9.dll", "d3dx9_31.dll")
        return system32.exists() and all((system32 / item).exists() for item in required)

    def _offer_directx_download(self) -> None:
        self._open_confirm_overlay(
            "DirectX 9 Required",
            "DirectX 9 could not be found. Open the download page?",
            "Open Page",
            "Cancel",
            "open_directx",
        )

    def _launch_client(
        self,
        profile: ServerProfile,
        server_manifest: ServerManifest,
        login_result: LoginResult,
    ) -> subprocess.Popen[str]:
        working_directory = self._client_directory(profile)
        executable_path = working_directory / CLIENT_EXECUTABLE_NAME
        if not executable_path.exists():
            raise LauncherError(f"Unable to launch the game. {executable_path} could not be found.")

        launcher_arguments = [
            f"Server={profile.login_server or server_manifest.login_server}",
            f"SessionId={login_result.session_id}",
            f"Internationalization:Locale={self.settings.locale}",
        ]
        if login_result.launch_arguments:
            launcher_arguments.append(login_result.launch_arguments)
        arguments = " ".join(launcher_arguments)

        if sys.platform != "win32":
            raise LauncherError("This Python launcher currently supports launching on Windows only.")

        command = f'"{executable_path}" {arguments}'
        try:
            return subprocess.Popen(command, cwd=str(working_directory))
        except OSError as exc:
            raise LauncherError(f"Failed to start the client process: {exc}") from exc

    def _client_directory(self, profile: ServerProfile) -> Path:
        if self.settings.game_path:
            configured_path = Path(self.settings.game_path)
            if configured_path.is_file():
                return configured_path.parent
            if configured_path.is_dir() and (configured_path / CLIENT_EXECUTABLE_NAME).exists():
                return configured_path

        portable_servers_root = self._portable_servers_root()
        portable_client_dir = portable_servers_root / (profile.save_path or slugify(profile.key)) / "Client"
        if (portable_client_dir / CLIENT_EXECUTABLE_NAME).exists():
            return portable_client_dir

        candidates = [APP_DIR / "Free Realms", APP_DIR / "FreeRealms", APP_DIR / "Game", APP_DIR]
        for candidate in candidates:
            if (candidate / CLIENT_EXECUTABLE_NAME).exists():
                return candidate
        return portable_client_dir

    def _portable_servers_root(self) -> Path:
        candidates = [APP_DIR / "Servers", APP_DIR.parent / "Servers"]
        for candidate in candidates:
            if candidate.exists():
                return candidate
        return APP_DIR.parent / "Servers" if APP_DIR.name.lower() == "launcher" else APP_DIR / "Servers"
