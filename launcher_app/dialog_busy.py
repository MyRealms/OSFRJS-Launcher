from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication, QProgressDialog, QWidget

from .constants import WINDOW_SCALE


class BusyDialog(QProgressDialog):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__("Preparing launcher...", "", 0, 0, parent)
        self.setWindowTitle("FreeRealmsJS Launcher")
        self.setWindowModality(Qt.WindowModal)
        self.setCancelButton(None)
        self.setMinimumDuration(0)
        self.setAutoClose(False)
        self.setAutoReset(False)
        self.setMinimumWidth(max(260, int(360 * WINDOW_SCALE)))
        self.show()
        QApplication.processEvents()

    def update_status(self, message: str) -> None:
        self.setLabelText(message)
        QApplication.processEvents()
