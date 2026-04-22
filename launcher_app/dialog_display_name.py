from __future__ import annotations

from PySide6.QtWidgets import QDialog, QDialogButtonBox, QFormLayout, QLineEdit, QVBoxLayout, QWidget

from .constants import WINDOW_SCALE


class DisplayNameDialog(QDialog):
    def __init__(self, display_name: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Launcher Name")
        self.setModal(True)
        self.setMinimumWidth(max(280, int(380 * WINDOW_SCALE)))

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 18, 20, 18)
        layout.setSpacing(12)

        form = QFormLayout()
        self.name_edit = QLineEdit(display_name)
        self.name_edit.setPlaceholderText("Enter launcher name")
        form.addRow("Name", self.name_edit)
        layout.addLayout(form)

        buttons = QDialogButtonBox(QDialogButtonBox.Cancel | QDialogButtonBox.Ok)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def display_name(self) -> str:
        return self.name_edit.text().strip()
