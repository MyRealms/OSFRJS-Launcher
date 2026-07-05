from __future__ import annotations

import logging
import sys
import threading
import traceback

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QFontDatabase, QIcon
from PySide6.QtWidgets import QApplication, QMainWindow

from .constants import DEBUG_LOG_PATH, DEFAULT_WINDOW_HEIGHT, DEFAULT_WINDOW_WIDTH, DISCORD_RPC_UPDATE_INTERVAL_MS, FONT_PATH, ICON_PATH
from .discord_presence import DiscordPresenceController
from .styles import build_app_stylesheet
from .widget import LauncherWidget

LOGGER = logging.getLogger("osfr_launcher")


class LauncherWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("OSFR Launcher")
        if ICON_PATH.exists():
            self.setWindowIcon(QIcon(str(ICON_PATH)))
        # The launcher UI is laid out for a fixed canvas, so hide the maximise
        # button entirely from the title bar. On Windows, clearing the
        # WindowMaximizeButtonHint alone still leaves the shell button visible
        # (just disabled). Setting MSWindowsFixedSizeDialogHint tells the shell
        # to render this window as a fixed-size dialog, which removes the
        # maximise button and the manual resize grip. Minimize and close
        # buttons are preserved.
        flags = (
            Qt.Window
            | Qt.WindowTitleHint
            | Qt.WindowSystemMenuHint
            | Qt.WindowMinimizeButtonHint
            | Qt.WindowCloseButtonHint
            | Qt.MSWindowsFixedSizeDialogHint
        )
        self.setWindowFlags(flags)
        self.resize(DEFAULT_WINDOW_WIDTH, DEFAULT_WINDOW_HEIGHT)
        self.launcher_widget = LauncherWidget()
        self.setCentralWidget(self.launcher_widget)
        self.discord_presence = DiscordPresenceController()
        self.discord_timer = QTimer(self)
        self.discord_timer.setInterval(DISCORD_RPC_UPDATE_INTERVAL_MS)
        self.discord_timer.timeout.connect(self._sync_discord_presence)
        self.discord_timer.start()
        QTimer.singleShot(1000, self._sync_discord_presence)
        # Check for launcher updates shortly after startup (non-blocking).
        QTimer.singleShot(2000, self.launcher_widget.check_for_update_async)
        self._shutdown_done = False
        LOGGER.info("Launcher window initialized")

    def _sync_discord_presence(self) -> None:
        self.discord_presence.update_for_widget(self.launcher_widget)

    def shutdown_runtime(self) -> None:
        if self._shutdown_done:
            return
        self._shutdown_done = True
        LOGGER.info("Shutting down launcher runtime")
        self.discord_timer.stop()
        self.discord_presence.shutdown()
        self.launcher_widget._shutdown_local_server_processes()
        # Tear down the in-process crash server so the ephemeral port
        # is released immediately instead of waiting for the kernel to
        # TIME_WAIT it.
        crash_server = getattr(self.launcher_widget, "crash_server", None)
        if crash_server is not None:
            crash_server.stop()

    def closeEvent(self, event) -> None:  # noqa: N802
        self.shutdown_runtime()
        super().closeEvent(event)


def _parse_runtime_args(argv: list[str]) -> tuple[list[str], bool]:
    filtered = [argv[0]] if argv else ["launcher_ui.py"]
    debug_mode = False
    for arg in argv[1:]:
        normalized = arg.strip().lower()
        if normalized in {"-debug", "--debug"}:
            debug_mode = True
            continue
        filtered.append(arg)
    return filtered, debug_mode


def _configure_debug_logging(debug_mode: bool) -> None:
    if not debug_mode:
        return
    DEBUG_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(
        level=logging.DEBUG,
        format="%(asctime)s [%(levelname)s] %(message)s",
        handlers=[
            logging.FileHandler(DEBUG_LOG_PATH, mode="w", encoding="utf-8"),
        ],
        force=True,
    )
    logging.info("Debug mode enabled")
    logging.info("Python: %s", sys.version.replace("\n", " "))
    logging.info("Executable: %s", sys.executable)
    logging.info("Arguments: %s", sys.argv)

    def _log_unhandled_exception(exc_type, exc_value, exc_traceback) -> None:
        logging.critical(
            "Unhandled exception:\n%s",
            "".join(traceback.format_exception(exc_type, exc_value, exc_traceback)),
        )
        sys.__excepthook__(exc_type, exc_value, exc_traceback)

    sys.excepthook = _log_unhandled_exception

    def _thread_exception_logger(args) -> None:
        logging.critical(
            "Unhandled thread exception in %s:\n%s",
            getattr(args.thread, "name", "unknown"),
            "".join(traceback.format_exception(args.exc_type, args.exc_value, args.exc_traceback)),
        )

    threading.excepthook = _thread_exception_logger


def _register_launcher_font(app: QApplication) -> None:
    if not FONT_PATH.exists():
        LOGGER.warning("Launcher font not found: %s", FONT_PATH)
        return

    font_id = QFontDatabase.addApplicationFont(str(FONT_PATH))
    if font_id < 0:
        LOGGER.warning("Failed to register launcher font: %s", FONT_PATH)
        return

    families = QFontDatabase.applicationFontFamilies(font_id)
    if families:
        app.setProperty("launcher_display_font_family", families[0])
        LOGGER.info("Registered launcher font family: %s", families[0])


def _acquire_single_instance_lock():
    """Bind an abstract/loopback socket as a cross-platform single-instance guard.

    Returns the socket (which must be kept alive for the process lifetime) or None
    if another instance already holds the lock.
    """
    import socket

    lock_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        # A fixed loopback port acts as a system-wide mutex. If it's already bound,
        # another launcher instance is running.
        lock_socket.bind(("127.0.0.1", 50573))
        lock_socket.listen(1)
        return lock_socket
    except OSError:
        lock_socket.close()
        return None


def main() -> int:
    qt_argv, debug_mode = _parse_runtime_args(sys.argv)
    _configure_debug_logging(debug_mode)
    LOGGER.info("Launcher main() start; debug=%s", debug_mode)

    instance_lock = _acquire_single_instance_lock()
    if instance_lock is None:
        # The previous behaviour was to silently ``return 0`` with no UI
        # feedback, which made the launcher look like a flaky crash when
        # the user double-clicked the icon or had a stale install open.
        # Show a modal dialog so the user knows what happened and can
        # act on it.
        LOGGER.warning("Another launcher instance is already running. Exiting.")
        try:
            from PySide6.QtWidgets import QMessageBox
            guard_app = QApplication.instance() or QApplication(qt_argv)
            QMessageBox.information(
                None,
                "OSFR Launcher",
                "OSFR Launcher is already running.\n\n"
                "Close the existing window (it may be minimised) and try again.",
            )
        except Exception:  # noqa: BLE001
            # If Qt is not available (e.g. the lock is taken by a
            # crashed instance that left the port in TIME_WAIT), fall
            # back to a plain stdout message.
            print("OSFR Launcher is already running. Close the existing window and try again.")
        return 0

    app = QApplication(qt_argv)
    app.setApplicationName("OSFR Launcher")
    app.setProperty("launcher_debug_mode", debug_mode)
    _register_launcher_font(app)
    if ICON_PATH.exists():
        app.setWindowIcon(QIcon(str(ICON_PATH)))
    app.setStyleSheet(build_app_stylesheet())

    window = LauncherWindow()
    if debug_mode:
        window.setWindowTitle("OSFR Launcher [Debug]")
    app.aboutToQuit.connect(window.shutdown_runtime)
    window.show()
    LOGGER.info("Launcher window shown")
    return app.exec()
