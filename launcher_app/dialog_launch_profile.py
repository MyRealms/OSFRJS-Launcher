from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QCheckBox, QDialog, QDialogButtonBox, QFormLayout, QLineEdit, QVBoxLayout, QWidget

from .constants import WINDOW_SCALE
from .models import ServerProfile
from .utils import slugify


class LaunchProfileDialog(QDialog):
    def __init__(self, profile: ServerProfile, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle(profile.title)
        self.setModal(True)
        self.setMinimumWidth(max(320, int(420 * WINDOW_SCALE)))

        self._profile = profile

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 18, 20, 18)
        layout.setSpacing(14)

        form = QFormLayout()
        form.setLabelAlignment(Qt.AlignLeft)
        form.setFormAlignment(Qt.AlignTop)
        form.setHorizontalSpacing(12)
        form.setVerticalSpacing(10)

        self.server_url_edit = QLineEdit(profile.server_url)
        self.server_url_edit.setPlaceholderText("https://your-server.example/")
        form.addRow("Server URL", self.server_url_edit)

        self.username_edit = QLineEdit(profile.username)
        self.username_edit.setPlaceholderText("Username")
        form.addRow("Username", self.username_edit)

        self.password_edit = QLineEdit(profile.password)
        self.password_edit.setEchoMode(QLineEdit.Password)
        self.password_edit.setPlaceholderText("Password")
        form.addRow("Password", self.password_edit)

        self.remember_username = QCheckBox("Remember username")
        self.remember_username.setChecked(profile.remember_username)
        form.addRow("", self.remember_username)

        self.remember_password = QCheckBox("Remember password")
        self.remember_password.setChecked(profile.remember_password)
        form.addRow("", self.remember_password)

        layout.addLayout(form)

        buttons = QDialogButtonBox(QDialogButtonBox.Cancel | QDialogButtonBox.Ok)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def profile(self) -> ServerProfile:
        server_url = self.server_url_edit.text().strip()
        save_path = self._profile.save_path.strip() or slugify(server_url or self._profile.key)
        remember_username = self.remember_username.isChecked()
        remember_password = self.remember_password.isChecked()
        username = self.username_edit.text().strip()
        password = self.password_edit.text()

        return ServerProfile(
            key=self._profile.key,
            title=self._profile.title,
            subtitle=self._profile.subtitle,
            name=self._profile.name,
            description=self._profile.description,
            server_url=server_url,
            login_server=self._profile.login_server,
            login_api_url=self._profile.login_api_url,
            save_path=save_path,
            username=username if remember_username else "",
            password=password if remember_password else "",
            remember_username=remember_username,
            remember_password=remember_password,
        )

    def login_credentials(self) -> tuple[str, str]:
        return self.username_edit.text().strip(), self.password_edit.text()
