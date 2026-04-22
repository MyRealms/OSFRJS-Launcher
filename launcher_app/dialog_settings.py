from __future__ import annotations

from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QGroupBox,
    QLineEdit,
    QSpinBox,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from .constants import WINDOW_SCALE
from .models import MENU_ITEMS
from .settings import LauncherSettings
from .utils import slugify


class SettingsDialog(QDialog):
    def __init__(self, settings: LauncherSettings, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Settings")
        self.setModal(True)
        self.setMinimumWidth(max(460, int(620 * WINDOW_SCALE)))

        self._profile_fields: dict[str, dict[str, QWidget]] = {}

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 18, 20, 18)
        layout.setSpacing(14)

        general_box = QGroupBox("General")
        general_form = QFormLayout(general_box)
        self.display_name_edit = QLineEdit(settings.display_name)
        self.display_name_edit.setPlaceholderText("Launcher name shown on home screen")
        general_form.addRow("Display Name", self.display_name_edit)
        self.locale_edit = QLineEdit(settings.locale)
        self.locale_edit.setPlaceholderText("en_US")
        general_form.addRow("Locale", self.locale_edit)
        self.parallel_download_check = QCheckBox("Enable parallel downloads")
        self.parallel_download_check.setChecked(settings.parallel_download)
        general_form.addRow("", self.parallel_download_check)
        self.download_threads_spin = QSpinBox()
        self.download_threads_spin.setRange(1, 32)
        self.download_threads_spin.setValue(max(1, settings.download_threads))
        self.download_threads_spin.setEnabled(settings.parallel_download)
        general_form.addRow("Download Threads", self.download_threads_spin)
        self.parallel_download_check.toggled.connect(self.download_threads_spin.setEnabled)
        layout.addWidget(general_box)

        tabs = QTabWidget()
        for meta in MENU_ITEMS:
            profile = settings.profiles[meta.key]
            tab = QWidget()
            form = QFormLayout(tab)
            form.setHorizontalSpacing(12)
            form.setVerticalSpacing(10)

            server_url = QLineEdit(profile.server_url)
            login_server = QLineEdit(profile.login_server)
            login_api = QLineEdit(profile.login_api_url)
            save_path = QLineEdit(profile.save_path)
            username = QLineEdit(profile.username)
            password = QLineEdit(profile.password)
            password.setEchoMode(QLineEdit.Password)
            remember_username = QCheckBox("Remember username")
            remember_username.setChecked(profile.remember_username)
            remember_password = QCheckBox("Remember password")
            remember_password.setChecked(profile.remember_password)

            form.addRow("Server URL", server_url)
            form.addRow("Login Server", login_server)
            form.addRow("Login API", login_api)
            form.addRow("Save Path", save_path)
            form.addRow("Username", username)
            form.addRow("Password", password)
            form.addRow("", remember_username)
            form.addRow("", remember_password)

            self._profile_fields[meta.key] = {
                "server_url": server_url,
                "login_server": login_server,
                "login_api_url": login_api,
                "save_path": save_path,
                "username": username,
                "password": password,
                "remember_username": remember_username,
                "remember_password": remember_password,
            }
            tabs.addTab(tab, profile.name or meta.title)

        layout.addWidget(tabs)

        buttons = QDialogButtonBox(QDialogButtonBox.Cancel | QDialogButtonBox.Save)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def apply_to_settings(self, settings: LauncherSettings) -> None:
        settings.display_name = self.display_name_edit.text().strip()
        settings.locale = self.locale_edit.text().strip() or settings.locale
        settings.parallel_download = self.parallel_download_check.isChecked()
        settings.download_threads = self.download_threads_spin.value()
        for meta in MENU_ITEMS:
            profile = settings.profiles[meta.key]
            fields = self._profile_fields[meta.key]
            profile.server_url = _cast_line(fields["server_url"]).text().strip()
            profile.login_server = _cast_line(fields["login_server"]).text().strip()
            profile.login_api_url = _cast_line(fields["login_api_url"]).text().strip()
            profile.save_path = _cast_line(fields["save_path"]).text().strip() or profile.save_path or slugify(meta.key)
            profile.username = _cast_line(fields["username"]).text().strip()
            profile.password = _cast_line(fields["password"]).text()
            profile.remember_username = _cast_check(fields["remember_username"]).isChecked()
            profile.remember_password = _cast_check(fields["remember_password"]).isChecked()


def _cast_line(widget: QWidget) -> QLineEdit:
    if isinstance(widget, QLineEdit):
        return widget
    raise TypeError("Expected QLineEdit")


def _cast_check(widget: QWidget) -> QCheckBox:
    if isinstance(widget, QCheckBox):
        return widget
    raise TypeError("Expected QCheckBox")
