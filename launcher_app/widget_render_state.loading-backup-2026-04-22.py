from __future__ import annotations

from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QColor, QPainter

from .widget_render_base import PPT_CX, PPT_CY


class LauncherWidgetRenderStateMixin:
    def _draw_loading_screen(self, painter: QPainter, content_rect: QRectF) -> None:
        painter.save()
        if self.window_svg and self.window_svg.isValid():
            self.window_svg.render(painter, content_rect)
        else:
            painter.fillRect(content_rect, QColor("#2A2A2A"))
        subtitle_rect = self._ppt_rect(content_rect, 3470000, 3200000, 4580000, 380000)
        painter.setPen(QColor(230, 230, 230, 190))
        font = painter.font()
        font.setFamily(self.display_font_family)
        font.setBold(False)
        font.setPixelSize(16)
        painter.setFont(font)
        painter.drawText(subtitle_rect, Qt.AlignCenter | Qt.AlignVCenter, "Preparing launcher resources")
        painter.setPen(QColor("#FFFFFF"))
        font.setBold(True)
        font.setPixelSize(22)
        painter.setFont(font)
        painter.drawText(
            self._ppt_rect(content_rect, 10053638, 6778459, 1466850, 338554),
            Qt.AlignLeft | Qt.AlignVCenter,
            self._animated_status_text("Loading"),
        )
        painter.restore()

    def _draw_status_screen(self, painter: QPainter, content_rect: QRectF) -> None:
        self._draw_launcher_shell(painter, content_rect)
        self._draw_left_navigation(painter, content_rect)
        self._draw_header(painter, content_rect)
        self._draw_hero_panel(painter, content_rect)
        self._draw_selection_overlay(painter, content_rect)

        hero_rect = self._ppt_rect(content_rect, 2558618, 1091350, 8962256, 5016608)
        target_band = self._ppt_rect(content_rect, 2558618, 6107958, 8962256, 1091355)
        anim_progress = min(1.0, self.status_transition_tick / 8.0)
        eased_progress = 1.0 - pow(1.0 - anim_progress, 3)
        band_y = content_rect.bottom() - (content_rect.bottom() - target_band.y()) * eased_progress
        animated_band = QRectF(target_band.x(), band_y, target_band.width(), target_band.height())
        dark_overlay_top = hero_rect.y() + (hero_rect.bottom() - hero_rect.y()) * (1.0 - eased_progress)
        dark_overlay = QRectF(hero_rect.x(), dark_overlay_top, hero_rect.width(), hero_rect.bottom() - dark_overlay_top)

        loading_track_rect = QRectF(
            animated_band.x() + animated_band.width() * 0.035,
            animated_band.y() + animated_band.height() * 0.18,
            animated_band.width() * 0.93,
            max(4.0, animated_band.height() * 0.032),
        )
        loading_fill_rect = QRectF(
            loading_track_rect.x(),
            loading_track_rect.y(),
            loading_track_rect.width() * (((self.loading_tick % 12) + 1) / 12.0),
            loading_track_rect.height(),
        )
        title_rect = QRectF(
            animated_band.x() + animated_band.width() * 0.33,
            animated_band.y() + animated_band.height() * 0.29,
            animated_band.width() * 0.37,
            animated_band.height() * 0.47,
        )
        subtitle_rect = QRectF(
            animated_band.x() + animated_band.width() * 0.04,
            animated_band.y() + animated_band.height() * 0.36,
            animated_band.width() * 0.25,
            animated_band.height() * 0.34,
        )

        painter.save()
        painter.fillRect(dark_overlay, QColor(0, 0, 0, 118))
        painter.fillRect(animated_band, QColor(18, 18, 18, 232))
        painter.fillRect(loading_track_rect, QColor(255, 255, 255, 26))
        painter.fillRect(loading_fill_rect, QColor("#8FC95D"))

        painter.setPen(QColor(255, 255, 255, 220))
        font = painter.font()
        font.setFamily(self.display_font_family)
        font.setBold(True)
        font.setPixelSize(15)
        painter.setFont(font)
        painter.drawText(
            subtitle_rect,
            Qt.AlignLeft | Qt.AlignVCenter,
            self._animated_status_text(self.status_subtitle, self.status_subtitle_animated),
        )

        pulse_alpha = 215 + int((self.loading_tick % 4) * 8)
        painter.setPen(QColor(255, 255, 255, min(pulse_alpha, 245)))
        font.setBold(True)
        font.setPixelSize(32)
        painter.setFont(font)
        painter.drawText(
            title_rect,
            Qt.AlignCenter | Qt.AlignVCenter,
            self._animated_status_text(self.status_title, self.status_title_animated),
        )
        painter.restore()

    def _draw_setup_screen(self, painter: QPainter, content_rect: QRectF, settings_mode: bool) -> None:
        painter.save()
        painter.fillRect(content_rect, QColor("#282827"))
        header_h = 934651 if settings_mode else 1852300
        header_rect = self._ppt_rect(content_rect, 0, 0, PPT_CX, header_h)
        painter.fillRect(header_rect, QColor("#282827") if settings_mode else QColor("#1E1E1E"))
        painter.restore()

        form_card_rect = self._ppt_rect(content_rect, 1915000, 1350000 if settings_mode else 2050000, 7680000, 3950000)
        title_rect = self._ppt_rect(content_rect, 2993226 if settings_mode else 2993229, 140000 if settings_mode else 346065, 5534025, 830997 if not settings_mode else 461665)
        subtitle_rect = self._ppt_rect(content_rect, 2333621 if settings_mode else 2333625, 590000 if settings_mode else 1267526, 6657975, 540000 if settings_mode else 584775)
        name_field_rect = self._ppt_rect(content_rect, 2333621, 1880000 if settings_mode else 2730000, 6657975, 540000)
        game_full_rect = self._ppt_rect(content_rect, 2333621, 3260000 if settings_mode else 5000000, 6657975, 540000)
        scale_y = content_rect.height() / PPT_CY
        name_label_rect = QRectF(name_field_rect.x(), name_field_rect.y() - 360000 * scale_y, name_field_rect.width(), 220000 * scale_y)
        game_label_rect = QRectF(game_full_rect.x(), game_full_rect.y() - 460000 * scale_y, game_full_rect.width(), 220000 * scale_y)
        game_hint_rect = QRectF(game_full_rect.x(), game_full_rect.y() - 200000 * scale_y, game_full_rect.width(), 170000 * scale_y)
        browse_button_rect = QRectF(game_full_rect.right() - 1320000 * (content_rect.width() / PPT_CX), game_full_rect.y(), 1320000 * (content_rect.width() / PPT_CX), game_full_rect.height())
        game_field_rect = QRectF(game_full_rect.x(), game_full_rect.y(), game_full_rect.width() - browse_button_rect.width() - 140000 * (content_rect.width() / PPT_CX), game_full_rect.height())
        button_rect = self._ppt_rect(content_rect, 4347800, 6210516, 2824891, 653256)
        back_rect = self._ppt_rect(content_rect, 260000, 260000, 1380000, 380000)
        footer_note_rect = self._ppt_rect(content_rect, 2333621, 5860000, 4200000, 290000)
        scale_x = content_rect.width() / PPT_CX
        reset_rect = QRectF(
            form_card_rect.right() - 2600000 * scale_x,
            form_card_rect.bottom() - 340000 * scale_y,
            2450000 * scale_x,
            240000 * scale_y,
        )
        settings_top_line_y = self._ppt_rect(content_rect, 0, 1091350, 0, 0).y()
        settings_bottom_line_y = self._ppt_rect(content_rect, 0, 6115000, 0, 0).y()

        self._rounded_rect(
            painter,
            form_card_rect,
            18,
            QColor(255, 255, 255, 4 if settings_mode else 6),
            QColor(255, 255, 255, 22),
            1.0,
        )
        if settings_mode:
            painter.save()
            painter.setPen(QColor(255, 255, 255, 18))
            painter.drawLine(content_rect.x(), settings_top_line_y, content_rect.right(), settings_top_line_y)
            painter.drawLine(content_rect.x(), settings_bottom_line_y, content_rect.right(), settings_bottom_line_y)
            painter.restore()

        painter.save()
        if settings_mode:
            self._rounded_rect(painter, back_rect, 10, QColor("#1F1F1F"), QColor(255, 255, 255, 26), 1.0)
        painter.setPen(QColor("#FFFFFF"))
        font = painter.font()
        font.setFamily(self.display_font_family)
        font.setBold(True)
        font.setPixelSize(34 if not settings_mode else 28)
        painter.setFont(font)
        painter.drawText(title_rect, Qt.AlignCenter | Qt.AlignVCenter | Qt.TextWordWrap, "Settings" if settings_mode else "First-Time Setup")

        painter.setPen(QColor(225, 225, 225, 215))
        font.setBold(False)
        font.setPixelSize(15)
        font.setFamily(self.display_font_family)
        painter.setFont(font)
        subtitle_text = "Update your launcher settings." if settings_mode else "Before you start, we need a few details to set up your launcher."
        painter.drawText(subtitle_rect, Qt.AlignCenter | Qt.AlignVCenter | Qt.TextWordWrap, subtitle_text)

        painter.setPen(QColor("#FFFFFF"))
        font.setBold(True)
        font.setPixelSize(16)
        font.setFamily(self.display_font_family)
        painter.setFont(font)
        painter.drawText(name_label_rect, Qt.AlignLeft | Qt.AlignVCenter, "Display Name")
        painter.drawText(game_label_rect, Qt.AlignLeft | Qt.AlignVCenter, "Game Folder")

        painter.setPen(QColor(222, 222, 222, 200))
        font.setBold(False)
        font.setPixelSize(13)
        painter.setFont(font)
        painter.drawText(game_hint_rect, Qt.AlignLeft | Qt.AlignVCenter, "Choose the folder that contains FreeRealms.exe")
        if settings_mode:
            painter.setPen(QColor(235, 235, 235, 210))
            font.setBold(True)
            font.setPixelSize(15)
            painter.setFont(font)
            painter.drawText(back_rect, Qt.AlignCenter, "< Back")
            painter.setPen(QColor("#8FC95D"))
            font.setPixelSize(15)
            painter.setFont(font)
            painter.drawText(reset_rect, Qt.AlignRight | Qt.AlignVCenter, "Reset Launcher Settings")
        else:
            painter.setPen(QColor(220, 220, 220, 165))
            font.setBold(False)
            font.setPixelSize(13)
            painter.setFont(font)
            painter.drawText(footer_note_rect, Qt.AlignLeft | Qt.AlignVCenter, "You can change these later in Settings.")
        painter.restore()

        self._draw_input_box(painter, name_field_rect, self.setup_display_name or "Click to enter your display name")
        self._draw_input_box(painter, game_field_rect, self.setup_game_path or "Click to choose the folder that contains FreeRealms.exe")
        self._rounded_rect(
            painter,
            browse_button_rect,
            10,
            QColor("#78A84A"),
            QColor(214, 245, 176, 130),
            1.0,
        )
        painter.save()
        painter.setPen(QColor("#FFFFFF"))
        font = painter.font()
        font.setFamily(self.display_font_family)
        font.setBold(True)
        font.setPixelSize(16)
        painter.setFont(font)
        painter.drawText(browse_button_rect, Qt.AlignCenter, "Browse")
        painter.restore()

        if self.play_button_svg and self.play_button_svg.isValid():
            self.play_button_svg.render(painter, button_rect)
        else:
            self._rounded_rect(painter, button_rect, 20, QColor("#78A84A"))

        painter.save()
        painter.setPen(QColor("#FFFFFF"))
        font = painter.font()
        font.setFamily(self.display_font_family)
        font.setBold(True)
        font.setPixelSize(26 if settings_mode else 24)
        painter.setFont(font)
        painter.drawText(button_rect, Qt.AlignCenter, "Save Changes" if settings_mode else "Continue")
        painter.restore()

    def _register_setup_click_regions(self, content_rect: QRectF, settings_mode: bool) -> None:
        name_field_rect = self._ppt_rect(content_rect, 2333621, 1880000 if settings_mode else 2730000, 6657975, 540000)
        game_full_rect = self._ppt_rect(content_rect, 2333621, 3260000 if settings_mode else 5000000, 6657975, 540000)
        form_card_rect = self._ppt_rect(content_rect, 1915000, 1350000 if settings_mode else 2050000, 7680000, 3950000)
        scale_x = content_rect.width() / PPT_CX
        scale_y = content_rect.height() / PPT_CY
        browse_button_rect = QRectF(game_full_rect.right() - 1320000 * (content_rect.width() / PPT_CX), game_full_rect.y(), 1320000 * (content_rect.width() / PPT_CX), game_full_rect.height())
        game_field_rect = QRectF(game_full_rect.x(), game_full_rect.y(), game_full_rect.width() - browse_button_rect.width() - 140000 * (content_rect.width() / PPT_CX), game_full_rect.height())
        button_rect = self._ppt_rect(content_rect, 4347800, 6210516, 2824891, 653256)
        reset_rect = QRectF(
            form_card_rect.right() - 2600000 * scale_x,
            form_card_rect.bottom() - 340000 * scale_y,
            2450000 * scale_x,
            240000 * scale_y,
        )
        self.click_regions.append(("setup_field", "display_name", name_field_rect))
        self.click_regions.append(("setup_field", "game_path", game_field_rect))
        self.click_regions.append(("setup_browse", "game_path", browse_button_rect))
        self.click_regions.append(("setup_submit", "settings" if settings_mode else "setup", button_rect))
        if settings_mode:
            self.click_regions.append(("setup_reset", "settings", reset_rect))
            self.click_regions.append(("back_to_main", "main", self._ppt_rect(content_rect, 260000, 260000, 1380000, 380000)))

    def _overlay_layout(self, content_rect: QRectF) -> dict[str, QRectF]:
        if self.overlay_kind == "login":
            panel = QRectF(
                content_rect.center().x() - content_rect.width() * 0.315,
                content_rect.center().y() - content_rect.height() * 0.30,
                content_rect.width() * 0.63,
                content_rect.height() * 0.60,
            )
        else:
            panel = QRectF(
                content_rect.center().x() - content_rect.width() * 0.24,
                content_rect.center().y() - content_rect.height() * 0.18,
                content_rect.width() * 0.48,
                content_rect.height() * 0.36,
            )

        layout = {
            "panel": panel,
            "title": QRectF(panel.x() + 28, panel.y() + 20, panel.width() - 56, 42),
            "message": QRectF(panel.x() + 30, panel.y() + 70, panel.width() - 60, 52),
            "submit": QRectF(panel.right() - 190, panel.bottom() - 62, 160, 42),
            "cancel": QRectF(panel.right() - 370, panel.bottom() - 62, 160, 42),
        }
        if self.overlay_kind == "text_input":
            layout["input1"] = QRectF(panel.x() + 30, panel.y() + 130, panel.width() - 60, 42)
        elif self.overlay_kind == "login":
            layout["input1"] = QRectF(panel.x() + 36, panel.y() + 128, panel.width() - 72, 42)
            layout["input2"] = QRectF(panel.x() + 36, panel.y() + 196, panel.width() - 72, 42)
            layout["input3"] = QRectF(panel.x() + 36, panel.y() + 264, panel.width() - 72, 42)
            layout["toggle_user"] = QRectF(panel.x() + 36, panel.y() + 320, 220, 28)
            layout["toggle_pass"] = QRectF(panel.x() + 290, panel.y() + 320, 220, 28)
        return layout

    def _draw_overlay_button(self, painter: QPainter, rect: QRectF, text: str, *, primary: bool) -> None:
        fill = QColor("#78A84A") if primary else QColor("#1F1F1F")
        outline = QColor(214, 245, 176, 130) if primary else QColor(255, 255, 255, 30)
        self._rounded_rect(painter, rect, 10, fill, outline, 1.0)
        painter.save()
        painter.setPen(QColor("#FFFFFF"))
        font = painter.font()
        font.setFamily(self.display_font_family)
        font.setBold(True)
        font.setPixelSize(15)
        painter.setFont(font)
        painter.drawText(rect, Qt.AlignCenter, text)
        painter.restore()

    def _draw_overlay_toggle(self, painter: QPainter, rect: QRectF, text: str, enabled: bool) -> None:
        box = QRectF(rect.x(), rect.y() + 4, 18, 18)
        self._rounded_rect(
            painter,
            box,
            5,
            QColor("#78A84A") if enabled else QColor("#1F1F1F"),
            QColor(214, 245, 176, 130) if enabled else QColor(255, 255, 255, 28),
            1.0,
        )
        painter.save()
        painter.setPen(QColor("#FFFFFF"))
        font = painter.font()
        font.setFamily(self.display_font_family)
        font.setBold(True)
        font.setPixelSize(13)
        painter.setFont(font)
        painter.drawText(QRectF(rect.x() + 28, rect.y(), rect.width() - 28, rect.height()), Qt.AlignLeft | Qt.AlignVCenter, text)
        painter.restore()

    def _draw_overlay(self, painter: QPainter, content_rect: QRectF) -> None:
        if not self.overlay_kind:
            return

        layout = self._overlay_layout(content_rect)
        panel = layout["panel"]

        painter.save()
        painter.fillRect(content_rect, QColor(0, 0, 0, 155))
        self._rounded_rect(painter, panel, 18, QColor("#2A2A2A"), QColor(255, 255, 255, 30), 1.0)

        painter.setPen(QColor("#FFFFFF"))
        font = painter.font()
        font.setFamily(self.display_font_family)
        font.setBold(True)
        font.setPixelSize(24 if self.overlay_kind == "login" else 22)
        painter.setFont(font)
        painter.drawText(layout["title"], Qt.AlignLeft | Qt.AlignVCenter, self.overlay_title)

        painter.setPen(QColor(225, 225, 225, 210))
        font.setBold(False)
        font.setPixelSize(14)
        painter.setFont(font)
        painter.drawText(layout["message"], Qt.AlignLeft | Qt.AlignTop | Qt.TextWordWrap, self.overlay_message)

        if self.overlay_kind == "login":
            painter.setPen(QColor(235, 235, 235, 210))
            font.setBold(True)
            font.setPixelSize(13)
            painter.setFont(font)
            painter.drawText(QRectF(layout["input1"].x(), layout["input1"].y() - 22, 220, 18), Qt.AlignLeft | Qt.AlignVCenter, "Server URL")
            painter.drawText(QRectF(layout["input2"].x(), layout["input2"].y() - 22, 220, 18), Qt.AlignLeft | Qt.AlignVCenter, "Username")
            painter.drawText(QRectF(layout["input3"].x(), layout["input3"].y() - 22, 220, 18), Qt.AlignLeft | Qt.AlignVCenter, "Password")
            self._draw_overlay_toggle(painter, layout["toggle_user"], "Remember username", self.overlay_remember_username)
            self._draw_overlay_toggle(painter, layout["toggle_pass"], "Remember password", self.overlay_remember_password)

        self._draw_overlay_button(painter, layout["submit"], self.overlay_submit_label, primary=True)
        if self.overlay_cancel_label:
            self._draw_overlay_button(painter, layout["cancel"], self.overlay_cancel_label, primary=False)
        painter.restore()

    def _sync_overlay_widgets(self, content_rect: QRectF) -> None:
        widgets = {
            "text": self.overlay_text_edit,
            "server_url": self.overlay_server_edit,
            "username": self.overlay_username_edit,
            "password": self.overlay_password_edit,
        }
        for widget in widgets.values():
            widget.hide()

        if not self.overlay_kind:
            return

        layout = self._overlay_layout(content_rect)
        if self.overlay_kind == "text_input":
            self.overlay_text_edit.setGeometry(layout["input1"].toRect())
            self.overlay_text_edit.show()
        elif self.overlay_kind == "login":
            self.overlay_server_edit.setGeometry(layout["input1"].toRect())
            self.overlay_username_edit.setGeometry(layout["input2"].toRect())
            self.overlay_password_edit.setGeometry(layout["input3"].toRect())
            self.overlay_server_edit.show()
            self.overlay_username_edit.show()
            self.overlay_password_edit.show()

    def _register_overlay_click_regions(self, content_rect: QRectF) -> None:
        if not self.overlay_kind:
            return
        layout = self._overlay_layout(content_rect)
        self.click_regions.append(("overlay_submit", self.overlay_action, layout["submit"]))
        if self.overlay_cancel_label:
            self.click_regions.append(("overlay_cancel", self.overlay_action, layout["cancel"]))
        if self.overlay_kind == "text_input":
            self.click_regions.append(("overlay_focus", "text", layout["input1"]))
        elif self.overlay_kind == "login":
            self.click_regions.append(("overlay_focus", "server_url", layout["input1"]))
            self.click_regions.append(("overlay_focus", "username", layout["input2"]))
            self.click_regions.append(("overlay_focus", "password", layout["input3"]))
            self.click_regions.append(("overlay_toggle", "remember_username", layout["toggle_user"]))
            self.click_regions.append(("overlay_toggle", "remember_password", layout["toggle_pass"]))
