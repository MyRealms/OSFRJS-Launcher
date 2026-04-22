from __future__ import annotations

import sys

from PySide6.QtCore import QTimer
from PySide6.QtGui import QFontDatabase, QIcon
from PySide6.QtWidgets import QApplication, QMainWindow

from .constants import DEFAULT_WINDOW_HEIGHT, DEFAULT_WINDOW_WIDTH, DISCORD_RPC_UPDATE_INTERVAL_MS, FONT_PATH, ICON_PATH
from .discord_presence import DiscordPresenceController
from .styles import build_app_stylesheet
from .widget import LauncherWidget


class LauncherWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("OSFR Launcher")
        if ICON_PATH.exists():
            self.setWindowIcon(QIcon(str(ICON_PATH)))
        self.resize(DEFAULT_WINDOW_WIDTH, DEFAULT_WINDOW_HEIGHT)
        self.launcher_widget = LauncherWidget()
        self.setCentralWidget(self.launcher_widget)
        self.discord_presence = DiscordPresenceController()
        self.discord_timer = QTimer(self)
        self.discord_timer.setInterval(DISCORD_RPC_UPDATE_INTERVAL_MS)
        self.discord_timer.timeout.connect(self._sync_discord_presence)
        self.discord_timer.start()
        QTimer.singleShot(1000, self._sync_discord_presence)
        self._shutdown_done = False

    def _sync_discord_presence(self) -> None:
        self.discord_presence.update_for_widget(self.launcher_widget)

    def shutdown_runtime(self) -> None:
        if self._shutdown_done:
            return
        self._shutdown_done = True
        self.discord_timer.stop()
        self.discord_presence.shutdown()
        self.launcher_widget._shutdown_local_server_processes()

    def closeEvent(self, event) -> None:  # noqa: N802
        self.shutdown_runtime()
        super().closeEvent(event)


def _register_launcher_font(app: QApplication) -> None:
    if not FONT_PATH.exists():
        return

    font_id = QFontDatabase.addApplicationFont(str(FONT_PATH))
    if font_id < 0:
        return

    families = QFontDatabase.applicationFontFamilies(font_id)
    if families:
        app.setProperty("launcher_display_font_family", families[0])


def main() -> int:
    app = QApplication(sys.argv)
    app.setApplicationName("OSFR Launcher")
    _register_launcher_font(app)
    if ICON_PATH.exists():
        app.setWindowIcon(QIcon(str(ICON_PATH)))
    app.setStyleSheet(build_app_stylesheet())

    window = LauncherWindow()
    app.aboutToQuit.connect(window.shutdown_runtime)
    window.show()
    return app.exec()
