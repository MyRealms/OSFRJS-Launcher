from __future__ import annotations

import json
import logging
import os
from pathlib import Path
import shlex
import shutil
import signal
import socket
import subprocess
import sys
import threading
import time

import requests
from .constants import (
    APP_DIR,
    CLIENT_EXECUTABLE_NAME,
    CLIENT_STASH_DIR,
    CLIENT_STASH_ORIGINAL_DIR,
    LOCAL_SERVER_BUNDLE_DIR,
    LOCAL_SERVER_PID_FILE,
    LOCAL_SERVER_RUNTIME_DIR,
    SERVERS_ROOT,
)
from .client_containers import resolve_container_dir
from .dependencies import PORTABLE_NODE_DIR
from .models import LauncherError


# Module-level lock for the load-modify-save cycle on the local
# server PID file. All current callers run on the GUI thread, but the
# future-proof shape is a lock so a refactor that moves any PID write
# off the GUI thread cannot race the load-modify-save pair.
_LOCAL_SERVER_PID_LOCK = threading.Lock()


def _dir_is_writable(path: Path) -> bool:
    """Return True if ``path`` exists and the current process can create new files in it."""
    if not path.exists():
        return False
    try:
        probe = path / ".osfr_write_probe"
        probe.write_text("ok", encoding="utf-8")
        probe.unlink()
    except OSError:
        return False
    return True
from .dependencies import (
    format_progress,
    install_authbridge_dependencies,
    install_directx9,
    install_node,
    resolve_node_executable,
)
from .models import LaunchCancelled, LauncherError, LoginResult, ServerManifest, ServerProfile, ServerStatus
from .utils import join_url, slugify

LOGGER = logging.getLogger("osfr_launcher")


class LauncherWidgetLaunchFlowMixin:
    def _decode_process_output(self, payload: bytes) -> str:
        for encoding in ("utf-8", "utf-16-le", "cp1254", "cp1252"):
            try:
                return payload.decode(encoding)
            except UnicodeDecodeError:
                continue
        return payload.decode("utf-8", errors="replace")

    def _is_game_running(self, *, force_refresh: bool = False) -> bool:
        # Cheap path (no subprocess): if we launched the client ourselves we can
        # tell purely from the tracked handle. This runs every animation tick.
        self._refresh_process_state()
        running = self._process_is_running(self.client_process)

        # Expensive path (spawns tasklist/pgrep): only when explicitly requested
        # via a user interaction. There's no point polling this in the
        # background since the game can't start without the user, and idle
        # subprocess spam wastes CPU/handles.
        if not running and force_refresh:
            running = any(
                self._tasklist_has_process(process_name)
                for process_name in self._client_process_names()
            )
            self.game_running_last_probe = time.monotonic()

        state_changed = running != self.game_running_cached
        self.game_running_cached = running
        if state_changed and self.current_screen == "main":
            self.update()
        return self.game_running_cached

    def _client_process_names(self) -> tuple[str, ...]:
        if sys.platform == "win32":
            return (CLIENT_EXECUTABLE_NAME,)
        return (CLIENT_EXECUTABLE_NAME, "xalia.exe")

    def _local_server_runtime_paths(self) -> dict[str, Path]:
        runtime_dir = LOCAL_SERVER_RUNTIME_DIR
        emulator_dir = runtime_dir / "Emulator"
        authbridge_dir = runtime_dir / "AuthBridge"
        # Node is a single canonical location: ``APP_DIR/node`` (see
        # ``PORTABLE_NODE_DIR`` in ``dependencies.py``). The bundled copy
        # under ``APP_DIR/local_server/node`` is no longer consulted
        # because ``install_node`` writes to ``APP_DIR/node`` and there
        # were no callers of the old bundled path that survived the
        # move.
        resolved_node = resolve_node_executable()
        node_exe = resolved_node if resolved_node is not None else PORTABLE_NODE_DIR / "node.exe"

        return {
            "runtime_dir": runtime_dir,
            "login_exe": emulator_dir / "Sanctuary.Login.exe",
            "gateway_exe": emulator_dir / "Sanctuary.Gateway.exe",
            "webapi_exe": emulator_dir / "Sanctuary.WebAPI.exe",
            "node_exe": node_exe,
            "authbridge_script": authbridge_dir / "server.mjs",
            "emulator_dir": emulator_dir,
            "authbridge_dir": authbridge_dir,
        }

    def _ensure_local_server_runtime(self) -> Path:
        paths = self._local_server_runtime_paths()
        # node is resolved/installed separately (bundled, portable, or auto-installed),
        # so it is not part of the required bundle contents.
        required = (
            paths["login_exe"],
            paths["gateway_exe"],
            paths["webapi_exe"],
            paths["authbridge_script"],
        )

        def _incomplete_message(reason: str) -> LauncherError:
            # Distinguish "the runtime was tampered with or never installed"
            # from "the install directory is read-only". The former is a
            # reinstall-the-launcher problem; the latter is a move-it-out-
            # of-Program-Files problem, and the wrong hint in either case
            # is a real UX dead end.
            is_read_only = (
                LOCAL_SERVER_RUNTIME_DIR.exists()
                and not _dir_is_writable(LOCAL_SERVER_RUNTIME_DIR)
            )
            if is_read_only:
                return LauncherError(
                    f"Cannot update the local server runtime at "
                    f"{LOCAL_SERVER_RUNTIME_DIR} because the install directory "
                    f"is read-only ({reason}). Reinstall the launcher to a "
                    f"writable location (e.g. C:\\Users\\<you>\\FreeRealmsJS) "
                    f"and try again."
                )
            return LauncherError(
                f"Local server runtime is incomplete ({reason}). Reinstall "
                f"the launcher to repair the bundled server files."
            )

        if LOCAL_SERVER_RUNTIME_DIR.exists() and all(path.exists() for path in required):
            LOGGER.info("Using local server runtime at %s", LOCAL_SERVER_RUNTIME_DIR)
            return LOCAL_SERVER_RUNTIME_DIR
        if LOCAL_SERVER_RUNTIME_DIR == LOCAL_SERVER_BUNDLE_DIR:
            missing = ", ".join(path.name for path in required if not path.exists())
            raise _incomplete_message(f"missing files: {missing}")
        if not LOCAL_SERVER_BUNDLE_DIR.exists():
            raise LauncherError(f"Local server runtime is missing: {LOCAL_SERVER_BUNDLE_DIR}")
        try:
            shutil.copytree(LOCAL_SERVER_BUNDLE_DIR, LOCAL_SERVER_RUNTIME_DIR, dirs_exist_ok=True)
        except (OSError, PermissionError) as exc:
            raise LauncherError(
                f"Could not extract the local server runtime into "
                f"{LOCAL_SERVER_RUNTIME_DIR}: {exc}. The install directory "
                f"may be read-only. Reinstall the launcher to a writable "
                f"location (e.g. C:\\Users\\<you>\\FreeRealmsJS) and try again."
            ) from exc
        if not all(path.exists() for path in required):
            missing = ", ".join(path.name for path in required if not path.exists())
            raise _incomplete_message(f"missing files: {missing}")
        LOGGER.info("Extracted local server runtime to %s", LOCAL_SERVER_RUNTIME_DIR)
        return LOCAL_SERVER_RUNTIME_DIR

    def _background_creation_flags(self) -> int:
        return getattr(subprocess, "CREATE_NO_WINDOW", 0) if sys.platform == "win32" else 0

    def _process_is_running(self, proc: subprocess.Popen[str] | None) -> bool:
        return proc is not None and proc.poll() is None

    def _tasklist_has_process(self, image_name: str) -> bool:
        if sys.platform != "win32":
            try:
                result = subprocess.run(
                    ["pgrep", "-afi", image_name],
                    capture_output=True,
                    check=False,
                )
            except OSError:
                return False
            stdout_text = self._decode_process_output(result.stdout or b"")
            if result.returncode == 0 and image_name.lower() in stdout_text.lower():
                LOGGER.debug("Detected Linux process for %s: %s", image_name, stdout_text.strip())
                return True
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

    def _load_local_server_pid_state(self) -> dict[str, int]:
        # Atomic read: read the file directly, no temp-file dance, since
        # the JSON is small and the worst case if the read races with a
        # concurrent save is a single stale entry. PID state is best-
        # effort diagnostic data, not user data.
        if not LOCAL_SERVER_PID_FILE.exists():
            return {}
        try:
            payload = json.loads(LOCAL_SERVER_PID_FILE.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError, UnicodeDecodeError):
            return {}
        if not isinstance(payload, dict):
            return {}
        state: dict[str, int] = {}
        for key, value in payload.items():
            try:
                pid = int(value)
            except (TypeError, ValueError):
                continue
            if pid > 0:
                state[str(key)] = pid
        return state

    def _save_local_server_pid_state(self, state: dict[str, int]) -> None:
        # All callers run on the GUI thread today, but the future-proof
        # shape is to acquire a threading lock so a refactor that
        # moves any PID write off the GUI thread cannot race the
        # load-modify-save pair.
        with _LOCAL_SERVER_PID_LOCK:
            try:
                if state:
                    LOCAL_SERVER_PID_FILE.parent.mkdir(parents=True, exist_ok=True)
                    # Write atomically (temp + replace) so a crash mid-
                    # write cannot leave the file truncated.
                    tmp = LOCAL_SERVER_PID_FILE.with_suffix(LOCAL_SERVER_PID_FILE.suffix + ".tmp")
                    tmp.write_text(json.dumps(state, indent=2), encoding="utf-8")
                    tmp.replace(LOCAL_SERVER_PID_FILE)
                elif LOCAL_SERVER_PID_FILE.exists():
                    LOCAL_SERVER_PID_FILE.unlink()
            except OSError:
                return

    def _remember_local_server_pid(self, key: str, pid: int) -> None:
        if pid <= 0:
            return
        state = self._load_local_server_pid_state()
        state[key] = pid
        self._save_local_server_pid_state(state)

    def _forget_local_server_pid(self, key: str) -> None:
        state = self._load_local_server_pid_state()
        if key in state:
            state.pop(key, None)
            self._save_local_server_pid_state(state)

    def _kill_process_id(self, pid: int) -> None:
        if pid <= 0:
            return
        if sys.platform == "win32":
            try:
                subprocess.run(
                    ["taskkill", "/PID", str(pid), "/T", "/F"],
                    capture_output=True,
                    check=False,
                    creationflags=self._background_creation_flags(),
                )
            except OSError:
                return
            return
        # POSIX: ask politely first, then force kill if it is still alive.
        try:
            os.kill(pid, signal.SIGTERM)
        except OSError:
            return
        time.sleep(0.3)
        try:
            os.kill(pid, signal.SIGKILL)
        except OSError:
            pass

    def _local_server_path_markers(self) -> dict[str, list[str]]:
        roots = {
            self._normalize_process_path(LOCAL_SERVER_RUNTIME_DIR),
            self._normalize_process_path(LOCAL_SERVER_BUNDLE_DIR),
        }
        roots = {root.rstrip("\\") for root in roots if root}
        return {
            "login": [f"{root}\\emulator\\sanctuary.login.exe" for root in roots],
            "gateway": [f"{root}\\emulator\\sanctuary.gateway.exe" for root in roots],
            "webapi": [f"{root}\\emulator\\sanctuary.webapi.exe" for root in roots],
            "authbridge": [f"{root}\\authbridge\\server.mjs" for root in roots],
            "runtime": [f"{root}\\" for root in roots],
        }

    def _cleanup_stale_local_server_processes(self) -> None:
        LOGGER.info("Cleaning stale local server processes")
        pid_state = self._load_local_server_pid_state()
        for key in ("authbridge", "webapi", "gateway", "login"):
            pid = pid_state.get(key)
            if pid:
                LOGGER.info("Killing remembered %s process pid=%s", key, pid)
                self._kill_process_id(pid)
        self._save_local_server_pid_state({})

        paths = self._local_server_runtime_paths()
        expected_login = self._normalize_process_path(paths["login_exe"])
        expected_gateway = self._normalize_process_path(paths["gateway_exe"])
        expected_webapi = self._normalize_process_path(paths["webapi_exe"])
        expected_node = self._normalize_process_path(paths["node_exe"])
        expected_authbridge = self._normalize_process_path(paths["authbridge_script"])
        markers = self._local_server_path_markers()

        stale_pids: set[int] = set()
        for process in self._runtime_process_snapshot():
            try:
                pid = int(process.get("ProcessId", 0) or 0)
            except (TypeError, ValueError):
                continue
            process_name = str(process.get("Name", "") or "").strip().lower()
            executable_path = self._normalize_process_path(process.get("ExecutablePath", "") or "")
            command_line = self._normalize_process_path(process.get("CommandLine", "") or "")
            if not pid:
                continue

            login_match = (
                process_name == "sanctuary.login.exe"
                and (
                    executable_path == expected_login
                    or any(marker in executable_path for marker in markers["login"])
                    or any(marker in command_line for marker in markers["login"])
                )
            )
            gateway_match = (
                process_name == "sanctuary.gateway.exe"
                and (
                    executable_path == expected_gateway
                    or any(marker in executable_path for marker in markers["gateway"])
                    or any(marker in command_line for marker in markers["gateway"])
                )
            )
            webapi_match = (
                process_name == "sanctuary.webapi.exe"
                and (
                    executable_path == expected_webapi
                    or any(marker in executable_path for marker in markers["webapi"])
                    or any(marker in command_line for marker in markers["webapi"])
                )
            )
            authbridge_match = (
                process_name == "node.exe"
                and (
                    (executable_path == expected_node and expected_authbridge in command_line)
                    or any(marker in command_line for marker in markers["authbridge"])
                )
            )

            if login_match or gateway_match or webapi_match or authbridge_match:
                stale_pids.add(pid)

        for pid in sorted(stale_pids):
            LOGGER.info("Killing stale local server pid=%s", pid)
            self._kill_process_id(pid)

        self.local_login_process = None
        self.local_gateway_process = None
        self.local_webapi_process = None
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
        command = self._command_for_executable(executable)
        if arguments:
            command.extend(arguments)
        startupinfo = None
        if sys.platform == "win32":
            startupinfo = subprocess.STARTUPINFO()
            startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        try:
            proc = subprocess.Popen(
                command,
                cwd=str(working_directory),
                creationflags=self._background_creation_flags(),
                startupinfo=startupinfo,
            )
            LOGGER.info("Started local server component: %s pid=%s cwd=%s", executable, proc.pid, working_directory)
            return proc
        except OSError as exc:
            raise LauncherError(f"Failed to start local server component {executable.name}: {exc}") from exc

    def _windows_runner_command(self) -> list[str]:
        runner = (
            os.environ.get("OSFR_WINDOWS_RUNNER", "")
            or os.environ.get("OSFR_WINE_BINARY", "")
            or "wine"
        ).strip()
        command = shlex.split(runner, posix=sys.platform != "win32")
        if not command:
            command = ["wine"]
        if shutil.which(command[0]) is None:
            raise LauncherError(
                f"Windows runner '{command[0]}' was not found. Install Wine/Proton or set OSFR_WINDOWS_RUNNER."
            )
        return command

    def _command_for_executable(self, executable: Path) -> list[str]:
        if sys.platform == "win32" or executable.suffix.lower() != ".exe":
            return [str(executable)]
        return [*self._windows_runner_command(), str(executable)]

    def _authbridge_ready(self, profile: ServerProfile) -> bool:
        try:
            requests.get(join_url(profile.server_url, "ServerManifest.xml"), timeout=3)
        except requests.RequestException:
            return False
        return True

    def _ensure_node_runtime(self, paths: dict[str, Path]) -> Path:
        """Return a usable node executable, installing a portable copy if necessary."""
        node_dir = paths["runtime_dir"] / "node"
        node_exe = resolve_node_executable(node_dir)
        if node_exe is not None:
            return node_exe

        LOGGER.info("Node.js not found; installing a portable runtime.")
        self._set_status_screen("Warming", "Installing Node.js")
        installed = install_node(progress=self._dependency_progress("Installing Node.js"))
        if installed is None:
            raise LauncherError("Node.js is required for the local server but could not be installed.")
        return installed

    def _ensure_authbridge_dependencies(self, paths: dict[str, Path], node_exe: Path) -> None:
        """Install AuthBridge npm dependencies on first run if they are missing."""
        authbridge_dir = paths["authbridge_dir"]
        if (authbridge_dir / "node_modules").is_dir():
            return

        LOGGER.info("Installing AuthBridge dependencies.")
        self._set_status_screen("Warming", "Installing server dependencies")
        if not install_authbridge_dependencies(authbridge_dir, node_exe):
            raise LauncherError("Failed to install the local server's AuthBridge dependencies.")

    def _ensure_offline_server_started(self, profile: ServerProfile) -> None:
        self._refresh_process_state()
        self._ensure_local_server_runtime()
        paths = self._local_server_runtime_paths()
        LOGGER.info("Ensuring offline server is started for %s", profile.server_url)

        login_running = self._process_is_running(self.local_login_process) or self._tasklist_has_process("Sanctuary.Login.exe")
        gateway_running = self._process_is_running(self.local_gateway_process) or self._tasklist_has_process("Sanctuary.Gateway.exe")
        webapi_running = self._process_is_running(self.local_webapi_process) or self._tasklist_has_process("Sanctuary.WebAPI.exe")
        authbridge_running = self._process_is_running(self.local_authbridge_process) or self._authbridge_ready(profile)

        if not login_running:
            self.local_login_process = self._start_local_server_process(
                paths["login_exe"],
                working_directory=paths["emulator_dir"],
            )
            self._remember_local_server_pid("login", self.local_login_process.pid)
            time.sleep(2.0)
        if not gateway_running:
            self.local_gateway_process = self._start_local_server_process(
                paths["gateway_exe"],
                working_directory=paths["emulator_dir"],
            )
            self._remember_local_server_pid("gateway", self.local_gateway_process.pid)
            time.sleep(1.0)
        if not webapi_running:
            self.local_webapi_process = self._start_local_server_process(
                paths["webapi_exe"],
                working_directory=paths["emulator_dir"],
            )
            self._remember_local_server_pid("webapi", self.local_webapi_process.pid)
            time.sleep(1.0)
        if not authbridge_running:
            node_exe = self._ensure_node_runtime(paths)
            self._ensure_authbridge_dependencies(paths, node_exe)
            self.local_authbridge_process = self._start_local_server_process(
                node_exe,
                arguments=[str(paths["authbridge_script"])],
                working_directory=paths["authbridge_dir"],
            )
            self._remember_local_server_pid("authbridge", self.local_authbridge_process.pid)
        LOGGER.info(
            "Offline server state: login_running=%s gateway_running=%s webapi_running=%s authbridge_running=%s",
            login_running,
            gateway_running,
            webapi_running,
            authbridge_running,
        )

    def _wait_for_offline_server_ready(
        self,
        profile: ServerProfile,
        *,
        timeout_seconds: float = 25.0,
    ) -> tuple[ServerManifest, ServerStatus]:
        deadline = time.monotonic() + timeout_seconds
        last_error: Exception | None = None
        # Reuse a single UDP socket across all probes so the warmup loop doesn't
        # allocate a fresh ephemeral port on every status check.
        from PySide6.QtWidgets import QApplication

        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as probe_sock:
            while time.monotonic() < deadline:
                self._raise_if_cancelled()
                self._refresh_process_state()
                try:
                    server_manifest = self._resolve_server_manifest(profile)
                    login_server = profile.login_server or server_manifest.login_server
                    server_status = self._fetch_server_status(login_server, sock=probe_sock)
                    if server_status.is_online:
                        return server_manifest, server_status
                except Exception as exc:  # noqa: BLE001
                    last_error = exc
                # Sleep in short slices and pump the event loop so the Cancel button
                # stays responsive during the warmup wait.
                for _ in range(10):
                    self._raise_if_cancelled()
                    QApplication.processEvents()
                    time.sleep(0.1)

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
        LOGGER.info("Shutting down local server processes")
        for attribute_name, pid_key in (
            ("local_authbridge_process", "authbridge"),
            ("local_webapi_process", "webapi"),
            ("local_gateway_process", "gateway"),
            ("local_login_process", "login"),
        ):
            proc = getattr(self, attribute_name, None)
            if proc is not None and proc.poll() is None:
                LOGGER.info("Killing active %s pid=%s", pid_key, proc.pid)
                self._kill_process_id(proc.pid)
            else:
                self._terminate_process_handle(proc)
            setattr(self, attribute_name, None)
            self._forget_local_server_pid(pid_key)
        self._cleanup_stale_local_server_processes()

    def _raise_if_cancelled(self) -> None:
        """Abort the launch flow if the user pressed Cancel on the status screen."""
        if self.launch_cancelled:
            raise LaunchCancelled()

    def cancel_launch(self) -> None:
        """Request cancellation of the in-progress launch/download flow."""
        if self.is_launching:
            LOGGER.info("User requested launch cancellation.")
            self.launch_cancelled = True

    def _stop_running_game(self) -> None:
        stopped = False
        if self._process_is_running(self.client_process):
            self._terminate_process_handle(self.client_process)
            self.client_process = None
            stopped = True
        else:
            for process_name in self._client_process_names():
                if not self._tasklist_has_process(process_name):
                    continue
                if sys.platform == "win32":
                    command = ["taskkill", "/IM", process_name, "/F"]
                else:
                    command = ["pkill", "-if", process_name]
                try:
                    subprocess.run(
                        command,
                        capture_output=True,
                        check=False,
                        creationflags=self._background_creation_flags(),
                    )
                    stopped = True
                except OSError as exc:
                    raise LauncherError(f"Failed to stop {process_name}: {exc}") from exc
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
        LOGGER.info("Queued play flow for selected_menu=%s", self.selected_menu)
        self.play_press_tick = 0
        self.play_press_pending = True
        self.update()

    def _start_play_flow(self) -> None:
        self._refresh_process_state()
        if self._is_game_running(force_refresh=True):
            self._show_error("The game is already running for the selected profile.")
            return

        profile = self.settings.profile_for_index(self.selected_menu)
        LOGGER.info("Starting play flow for profile=%s server_url=%s", profile.key, profile.server_url)
        if self._can_launch_without_overlay(profile):
            self._launch_with_profile_credentials(profile)
            return
        self._open_login_overlay(profile)

    def _can_launch_without_overlay(self, profile: ServerProfile) -> bool:
        # If the user has already saved credentials for this server (via the
        # "Remember" option in the login overlay or by editing the server
        # profile), we can launch directly without showing the login popup.
        if not profile.server_url:
            return False
        return bool(profile.remember_password and profile.username and profile.password)

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
        # The login overlay exposes a single "Remember" toggle (the
        # in-canvas editor uses the same single toggle via
        # ``_toggle_overlay_flag("remember_both")``), so a profile that
        # somehow ended up with mismatched remember flags would render
        # an inconsistent UI. Normalise to "both on" if either flag is
        # true and "both off" if both are false.
        self.overlay_remember_username = profile.remember_username or profile.remember_password
        self.overlay_remember_password = self.overlay_remember_username
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

        # Preserve the per-server fields that aren't edited from the login
        # overlay (icon_name, client_container) so a successful launch
        # doesn't silently reset them to "". Using ``dataclasses.replace``
        # means any new ServerProfile field added in the future is also
        # carried over without having to extend this call site.
        from dataclasses import replace

        profile_to_save = replace(
            updated_profile,
            username=username if updated_profile.remember_username else "",
            password=password if updated_profile.remember_password else "",
        )

        self.settings.update_profile(profile_to_save)
        self.settings.save()
        LOGGER.info(
            "Launching with credentials for profile=%s server_url=%s remember_username=%s remember_password=%s",
            updated_profile.key,
            updated_profile.server_url,
            updated_profile.remember_username,
            updated_profile.remember_password,
        )

        # Reset cancellation state for this launch attempt.
        self.launch_cancelled = False
        self.is_launching = True
        try:
            server_status = None
            if updated_profile.key == "offline_mode":
                self._set_status_screen("Warming", "Waking up Server")
                self._ensure_offline_server_started(updated_profile)
                server_manifest, server_status = self._wait_for_offline_server_ready(updated_profile)
            else:
                # Online server: ensure the local server is fully stopped so it
                # can't occupy the same ports, but never auto-start it.
                LOGGER.info("Online server connect for profile=%s; not starting local server", updated_profile.key)
                self._set_status_screen("Warming", "Stopping local server")
                self._shutdown_local_server_processes()
                self._set_status_screen("Warming", "Connecting to server")
                server_manifest = self._resolve_server_manifest(updated_profile)
            self._raise_if_cancelled()
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
                raise LauncherError(
                    "The server is offline or unreachable.\n"
                    f"Address: {updated_profile.login_server or server_manifest.login_server}\n"
                    "Check that the server is running and the IP/port are correct."
                )
            self._raise_if_cancelled()

            self._set_status_screen("Warming", "Checking client files")
            client_manifest = self._fetch_client_manifest(updated_profile.server_url)
            self._verify_client_files(updated_profile, client_manifest)
            self._raise_if_cancelled()

            self._set_status_screen("Warming", "Logging in")
            login_result = self._login(updated_profile, server_manifest, username, password)

            self._set_status_screen("Warming", "Checking DirectX 9")
            if not self._directx9_available():
                self._set_status_screen("Warming", "Installing DirectX 9")
                if install_directx9(progress=self._dependency_progress("Installing DirectX 9")):
                    LOGGER.info("DirectX 9 installed automatically.")
                else:
                    self.current_screen = "main"
                    self._offer_directx_download()
                    return

            self._set_status_screen("Warming", "Launching Free Realms")
            # Remember the client dir + current crash-log time so we can detect a
            # *new* crash after the client exits and show an in-launcher explanation.
            self._active_client_dir = self._client_directory(updated_profile)
            from .error_help import disable_crash_url, read_error_log_mtime
            # Point the client's ``GameCrashUrl=`` at the launcher's tiny
            # in-process HTTP server so any browser window it pops on a
            # G error is a small, local, launcher-branded banner instead
            # of whatever the server would otherwise push. The real error
            # is shown in the launcher overlay.
            crash_url = getattr(self, "crash_url", "") or (
                self.crash_server.url if getattr(self, "crash_server", None) else ""
            )
            if crash_url:
                disable_crash_url(self._active_client_dir, crash_url)
            self._crash_log_mtime = read_error_log_mtime(self._active_client_dir)
            self.client_process = self._launch_client(updated_profile, server_manifest, login_result)
            self.game_running_cached = True
            self.game_running_last_probe = time.monotonic()
            self.current_screen = "main"
            LOGGER.info("Client launch completed for profile=%s", updated_profile.key)
            self.update()
        except LaunchCancelled:
            self.current_screen = "main"
            LOGGER.info("Launch cancelled by user.")
            self.update()
        except LauncherError as exc:
            self.current_screen = "main"
            LOGGER.exception("LauncherError during launch flow")
            self._show_error(str(exc))
        except requests.exceptions.Timeout:
            self.current_screen = "main"
            LOGGER.exception("Timeout during launch flow")
            self._show_error(
                "The server did not respond in time.\n"
                "It may be offline, or your connection is slow/unavailable."
            )
        except requests.exceptions.ConnectionError:
            self.current_screen = "main"
            LOGGER.exception("Connection error during launch flow")
            self._show_error(
                "Could not connect to the server.\n"
                "Check the server address and your internet connection."
            )
        except requests.RequestException as exc:
            self.current_screen = "main"
            LOGGER.exception("Network error during launch flow")
            self._show_error(f"Network error while contacting the server:\n{exc}")
        except Exception as exc:  # noqa: BLE001
            self.current_screen = "main"
            LOGGER.exception("Unexpected error during launch flow")
            self._show_error(f"Unexpected error:\n{exc}")
        finally:
            self.is_launching = False
            self.launch_cancelled = False

    def _submit_login_overlay(self) -> None:
        from .utils import normalize_server_url

        username = self.overlay_username_edit.text().strip()
        password = self.overlay_password_edit.text()
        profile = self.settings.profiles[self.overlay_action]
        updated_profile = ServerProfile(
            key=profile.key,
            title=profile.title,
            subtitle=profile.subtitle,
            name=profile.name,
            description=profile.description,
            server_url=normalize_server_url(self.overlay_server_edit.text()),
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
        from .dependencies import directx9_available

        return directx9_available()

    def _dependency_progress(self, label: str):
        """Return a progress callback that updates the status screen with download progress."""

        def _report(received: int, total: int) -> None:
            self._set_status_screen("Warming", f"{label} {format_progress(received, total)}")

        return _report

    def _offer_directx_download(self) -> None:
        if sys.platform != "win32":
            # On Linux / macOS the official Microsoft DirectX 9 download
            # page is useless: the user has to install ``winetricks`` and
            # use it to populate their Wine prefix instead. Surface a
            # platform-appropriate hint so the user has a next step.
            message = (
                "DirectX 9 could not be found in your Wine prefix.\n\n"
                "On Linux, install winetricks (e.g. ``apt install winetricks``"
                " on Debian/Ubuntu) and run:\n\n"
                "  winetricks -q d3dx9 d3dcompiler_43\n\n"
                "Then click Retry."
            )
            self._open_message_overlay("DirectX 9 Required (Linux)", message)
            return
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
        executable_path = self._client_executable_path(working_directory)
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

        if sys.platform == "win32":
            command: str | list[str] = f'"{executable_path}" {arguments}'
        else:
            command = self._command_for_executable(executable_path)
            command.extend(launcher_arguments)
        LOGGER.info("Launching client executable=%s arguments=%s", executable_path, arguments)
        try:
            return subprocess.Popen(command, cwd=str(working_directory))
        except OSError as exc:
            raise LauncherError(f"Failed to start the client process: {exc}") from exc

    def _client_executable_path(self, working_directory: Path) -> Path:
        override = os.environ.get("OSFR_CLIENT_EXE", "").strip()
        if override:
            override_path = Path(override)
            if not override_path.is_absolute():
                override_path = working_directory / override_path
            return override_path
        if sys.platform != "win32":
            xalia_path = working_directory / "xalia.exe"
            if xalia_path.exists():
                LOGGER.info("Using xalia.exe directly on Linux/Proton: %s", xalia_path)
                return xalia_path
        return working_directory / CLIENT_EXECUTABLE_NAME

    def _client_directory(self, profile: ServerProfile) -> Path:
        # 1) Per-server container (the user-managed Client stash). If the
        #    server was added with "Create new client container" enabled,
        #    profile.client_container holds the folder name (e.g.
        #    "OSFR - MyServer"); we resolve it to the absolute path.
        if profile.client_container:
            try:
                container_dir = resolve_container_dir(profile.client_container)
                if (container_dir / CLIENT_EXECUTABLE_NAME).exists():
                    LOGGER.info("Client directory resolved from container %s", container_dir)
                    return container_dir
            except ValueError:
                LOGGER.warning("Invalid client_container name %r on profile %s; falling back.", profile.client_container, profile.key)

        # 2) The default golden client tree, also user-managed.
        if (CLIENT_STASH_ORIGINAL_DIR / CLIENT_EXECUTABLE_NAME).exists():
            LOGGER.info("Client directory resolved from golden stash: %s", CLIENT_STASH_ORIGINAL_DIR)
            return CLIENT_STASH_ORIGINAL_DIR

        # 3) Bundled fallbacks next to the launcher (covers a freshly
        #    dropped Client/ tree that hasn't been renamed to
        #    "OSFR - Original" yet, and Free Realms installs that live in
        #    the launcher folder).
        bundled_candidates = [
            CLIENT_STASH_DIR,
            APP_DIR / "Free Realms",
            APP_DIR / "FreeRealms",
            APP_DIR / "Game",
            APP_DIR,
        ]
        for candidate in bundled_candidates:
            if (candidate / CLIENT_EXECUTABLE_NAME).exists():
                LOGGER.info("Client directory resolved from bundled candidate: %s", candidate)
                return candidate

        # 4) Explicitly configured game path from settings.
        if self.settings.game_path:
            configured_path = Path(self.settings.game_path)
            if configured_path.is_file():
                LOGGER.info("Client directory resolved from configured file path: %s", configured_path.parent)
                return configured_path.parent
            if configured_path.is_dir() and (configured_path / CLIENT_EXECUTABLE_NAME).exists():
                LOGGER.info("Client directory resolved from configured directory: %s", configured_path)
                return configured_path

        # 5) Per-profile client dir under the portable servers root
        #    (APP_DIR/Servers/<save>/Client). This is the default landing
        #    spot for ClientManifest downloads.
        save_key = profile.save_path or slugify(profile.key)
        servers_client_dir = SERVERS_ROOT / save_key / "Client"
        if (servers_client_dir / CLIENT_EXECUTABLE_NAME).exists():
            LOGGER.info("Client directory resolved from servers root: %s", servers_client_dir)
            return servers_client_dir

        LOGGER.warning("Client directory fallback used; returning %s", servers_client_dir)
        return servers_client_dir

    def _portable_servers_root(self) -> Path:
        # Portable: the servers root always lives next to the launcher.
        return SERVERS_ROOT
