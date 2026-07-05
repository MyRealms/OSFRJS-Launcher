from __future__ import annotations

import time

from .constants import DISCORD_RPC_APP_ID

try:
    from pypresence import Presence
except Exception:  # noqa: BLE001
    Presence = None


class DiscordPresenceController:
    def __init__(self) -> None:
        self.client = None
        self.connected = False
        self.start_timestamp = int(time.time())
        # Exponential backoff state for the IPC handshake. The previous
        # code retried every ``DISCORD_RPC_UPDATE_INTERVAL_MS`` (15s)
        # forever when Discord was not running, which both spammed the
        # IPC pipe and burned CPU. After a failure we wait 30s, then
        # 1m, then 5m, then 15m, then cap at 15m until the next
        # successful connect.
        self._next_attempt_at = 0.0
        self._failure_streak = 0

    def update_for_widget(self, widget) -> None:
        if not DISCORD_RPC_APP_ID or Presence is None:
            return
        # Respect the user's per-launcher Discord Rich Presence toggle.
        try:
            if not getattr(widget.settings, "discord_activity", True):
                if self.connected:
                    self.shutdown()
                return
        except Exception:  # noqa: BLE001
            pass
        if not self._ensure_connected():
            return

        try:
            profile = widget.settings.profile_for_index(widget.selected_menu)
            self.client.update(
                details=self._details_text(widget),
                state=self._state_text(widget, profile.title),
                start=self.start_timestamp,
            )
        except Exception:  # noqa: BLE001
            self.connected = False
            self.client = None
            self._schedule_retry()

    def shutdown(self) -> None:
        if not self.connected or self.client is None:
            return
        try:
            self.client.clear()
        except Exception:  # noqa: BLE001
            pass
        try:
            self.client.close()
        except Exception:  # noqa: BLE001
            pass
        self.client = None
        self.connected = False

    def _ensure_connected(self) -> bool:
        if self.connected and self.client is not None:
            return True
        now = time.monotonic()
        if now < self._next_attempt_at:
            return False
        try:
            self.client = Presence(DISCORD_RPC_APP_ID)
            self.client.connect()
            self.connected = True
            # Reset the backoff state on a successful handshake so the
            # next failure starts from 30s again.
            self._failure_streak = 0
            self._next_attempt_at = 0.0
            return True
        except Exception:  # noqa: BLE001
            self.client = None
            self.connected = False
            self._schedule_retry()
            return False

    def _schedule_retry(self) -> None:
        # 30s, 60s, 300s, 900s, then cap at 900s.
        delays = (30, 60, 300, 900)
        self._failure_streak = min(self._failure_streak + 1, len(delays))
        delay = delays[self._failure_streak - 1]
        self._next_attempt_at = time.monotonic() + delay

    def _details_text(self, widget) -> str:
        # Use the launcher's already-maintained running state instead of
        # spawning a tasklist/pgrep subprocess on every RPC refresh.
        client_running = False
        try:
            widget._refresh_process_state()
            client_running = bool(widget.client_process) or bool(widget.game_running_cached)
        except Exception:  # noqa: BLE001
            client_running = bool(getattr(widget, "client_process", None))

        if client_running:
            return "Playing"
        if widget.current_screen == "loading":
            return "Starting launcher"
        if widget.current_screen == "setup":
            return "First-time setup"
        if widget.current_screen == "settings":
            return "Adjusting settings"
        if widget.current_screen == "status":
            return widget.status_title.strip() or "Warming"
        return "Launch Ready"

    def _state_text(self, widget, profile_title: str) -> str:
        if widget.current_screen == "status":
            return widget.status_subtitle.strip() or "Preparing launcher"
        if widget.current_screen == "main":
            return profile_title
        if widget.current_screen == "settings":
            return "Launcher configuration"
        if widget.current_screen == "setup":
            return "Completing required setup"
        return "Preparing OSFR"
