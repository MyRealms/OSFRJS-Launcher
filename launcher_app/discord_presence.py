from __future__ import annotations

import time

from .constants import CLIENT_EXECUTABLE_NAME, DISCORD_RPC_APP_ID

try:
    from pypresence import Presence
except Exception:  # noqa: BLE001
    Presence = None


class DiscordPresenceController:
    def __init__(self) -> None:
        self.client = None
        self.connected = False
        self.start_timestamp = int(time.time())

    def update_for_widget(self, widget) -> None:
        if not DISCORD_RPC_APP_ID or Presence is None:
            return
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
        try:
            self.client = Presence(DISCORD_RPC_APP_ID)
            self.client.connect()
            self.connected = True
            return True
        except Exception:  # noqa: BLE001
            self.client = None
            self.connected = False
            return False

    def _details_text(self, widget) -> str:
        client_running = False
        try:
            widget._refresh_process_state()
            client_running = bool(widget.client_process) or widget._tasklist_has_process(CLIENT_EXECUTABLE_NAME)
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
