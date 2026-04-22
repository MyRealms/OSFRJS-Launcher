from __future__ import annotations

from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QColor, QPainter

from .widget_render_base import PPT_CX, PPT_CY


class LauncherWidgetRenderStateMixin:
    def _overlay_intro_progress(self) -> float:
        return min(1.0, max(0.0, self.overlay_intro_tick / 12.0))

    def _setup_screen_intro_state(self, content_rect: QRectF, settings_mode: bool) -> tuple[float, float]:
        if not settings_mode or self.current_screen != "settings":
            return 1.0, 0.0
        progress = min(1.0, max(0.0, self.settings_intro_tick / 14.0))
        eased = self._stage_progress(progress, 0.0, 1.0)
        return 0.20 + (eased * 0.80), content_rect.height() * 0.035 * (1.0 - eased)

    def _draw_loading_screen(self, painter: QPainter, content_rect: QRectF) -> None:
        painter.save()
        if self.window_svg and self.window_svg.isValid():
            self.window_svg.render(painter, content_rect)
        else:
            painter.fillRect(content_rect, QColor("#2A2A2A"))
        loading_rect = self._ppt_rect(content_rect, 10053638, 6778459, 1466850, 338554)
        travel_progress = min(1.0, self.frame_tick / 52.0)
        loading_alpha = max(0, int(255 * (1.0 - self._stage_progress(travel_progress, 0.0, 1.0))))
        painter.setPen(QColor(255, 255, 255, loading_alpha))
        font = painter.font()
        font.setFamily(self.display_font_family)
        font.setBold(True)
        font.setPixelSize(22)
        painter.setFont(font)
        painter.drawText(
            loading_rect,
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
        anim_progress = min(1.0, self.status_transition_tick / 24.0)
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
            loading_track_rect.width() * (((self.frame_tick % 90) + 1) / 90.0),
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

        fade_hold_ticks = 18
        fade_duration_ticks = 18
        fade_progress = max(0.0, (self.status_title_fade_tick - fade_hold_ticks) / fade_duration_ticks)
        title_alpha = max(0, int((1.0 - min(1.0, fade_progress)) * 235))
        if title_alpha > 0:
            pulse_alpha = 215 + int((self.loading_tick % 4) * 8)
            painter.setPen(QColor(255, 255, 255, min(title_alpha, pulse_alpha, 245)))
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
        intro_opacity, intro_offset_y = self._setup_screen_intro_state(content_rect, settings_mode)

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
        painter.save()
        painter.setOpacity(intro_opacity)
        if intro_offset_y:
            painter.translate(0.0, intro_offset_y)
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

        self._draw_input_box(painter, name_field_rect, "")
        self._draw_input_box(painter, game_field_rect, "")
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
        _, intro_offset_y = self._setup_screen_intro_state(content_rect, settings_mode)
        if intro_offset_y:
            name_field_rect.translate(0.0, intro_offset_y)
            browse_button_rect.translate(0.0, intro_offset_y)
            game_field_rect.translate(0.0, intro_offset_y)
            button_rect.translate(0.0, intro_offset_y)
            reset_rect.translate(0.0, intro_offset_y)
        self.click_regions.append(("setup_field", "display_name", name_field_rect))
        self.click_regions.append(("setup_field", "game_path", game_field_rect))
        self.click_regions.append(("setup_browse", "game_path", browse_button_rect))
        self.click_regions.append(("setup_submit", "settings" if settings_mode else "setup", button_rect))
        if settings_mode:
            back_rect = self._ppt_rect(content_rect, 260000, 260000, 1380000, 380000)
            if intro_offset_y:
                back_rect.translate(0.0, intro_offset_y)
            self.click_regions.append(("setup_reset", "settings", reset_rect))
            self.click_regions.append(("back_to_main", "main", back_rect))

    def _overlay_layout(self, content_rect: QRectF) -> dict[str, QRectF]:
        if self.overlay_kind == "login":
            panel = QRectF(
                content_rect.center().x() - content_rect.width() * 0.29,
                content_rect.center().y() - content_rect.height() * 0.33,
                content_rect.width() * 0.58,
                content_rect.height() * 0.68,
            )
        elif self.overlay_kind == "server_profile":
            panel = QRectF(
                content_rect.center().x() - content_rect.width() * 0.25,
                content_rect.center().y() - content_rect.height() * 0.236,
                content_rect.width() * 0.50,
                content_rect.height() * 0.50,
            )
        else:
            panel = QRectF(
                content_rect.center().x() - content_rect.width() * 0.24,
                content_rect.center().y() - content_rect.height() * 0.18,
                content_rect.width() * 0.48,
                content_rect.height() * 0.36,
            )
        intro_progress = self._overlay_intro_progress()
        panel.translate(0.0, content_rect.height() * 0.07 * (1.0 - intro_progress))

        layout = {
            "panel": panel,
            "title": QRectF(panel.x() + 28, panel.y() + 20, panel.width() - 56, 42),
            "message": QRectF(panel.x() + 30, panel.y() + 70, panel.width() - 60, 52),
            "submit": QRectF(panel.right() - 190, panel.bottom() - 62, 160, 42),
            "cancel": QRectF(panel.right() - 370, panel.bottom() - 62, 160, 42),
        }
        if self.overlay_kind == "text_input":
            layout["input1"] = QRectF(panel.x() + 30, panel.y() + 130, panel.width() - 60, 42)
        elif self.overlay_kind == "server_profile":
            field_height = 44.0
            field_gap = 38.0
            first_input_y = panel.y() + 122
            layout["input1"] = QRectF(panel.x() + 30, first_input_y, panel.width() - 60, field_height)
            layout["input2"] = QRectF(panel.x() + 30, first_input_y + field_height + field_gap, panel.width() - 60, field_height)
            if self.overlay_alt_label:
                layout["alt"] = QRectF(panel.x() + 30, panel.bottom() - 52, panel.width() * 0.26, 42)
                layout["cancel"] = QRectF(panel.center().x() - (panel.width() * 0.13), panel.bottom() - 52, panel.width() * 0.26, 42)
                layout["submit"] = QRectF(panel.right() - (panel.width() * 0.26) - 30, panel.bottom() - 52, panel.width() * 0.26, 42)
            else:
                layout["cancel"] = QRectF(panel.x() + 30, panel.bottom() - 52, panel.width() * 0.34, 42)
                layout["submit"] = QRectF(panel.right() - (panel.width() * 0.34) - 30, panel.bottom() - 52, panel.width() * 0.34, 42)
        elif self.overlay_kind == "login":
            layout["title"] = QRectF(panel.x() + 28, panel.y() + 18, panel.width() - 56, 36)
            layout["message"] = QRectF(panel.x() + 34, panel.y() + 68, panel.width() - 68, 24)
            if self.overlay_link_text:
                layout["link"] = layout["message"]
            field_height = 46.0
            field_gap = 30.0
            first_input_y = panel.y() + 126
            layout["input1"] = QRectF(panel.x() + 36, first_input_y, panel.width() - 72, field_height)
            layout["input2"] = QRectF(panel.x() + 36, first_input_y + field_height + field_gap, panel.width() - 72, field_height)
            layout["input3"] = QRectF(panel.x() + 36, first_input_y + ((field_height + field_gap) * 2), panel.width() - 72, field_height)
            layout["toggle_combined"] = QRectF(panel.x() + 36, panel.bottom() - 80, panel.width() - 72, 24)
            layout["cancel"] = QRectF(panel.x() + 36, panel.bottom() - 50, panel.width() * 0.34, 38)
            layout["submit"] = QRectF(panel.right() - (panel.width() * 0.34) - 36, panel.bottom() - 50, panel.width() * 0.34, 38)
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
        font.setPixelSize(12)
        painter.setFont(font)
        painter.drawText(QRectF(rect.x() + 28, rect.y(), rect.width() - 28, rect.height()), Qt.AlignLeft | Qt.AlignVCenter, text)
        painter.restore()

    def _draw_overlay(self, painter: QPainter, content_rect: QRectF) -> None:
        if not self.overlay_kind:
            return

        layout = self._overlay_layout(content_rect)
        panel = layout["panel"]
        intro_progress = self._overlay_intro_progress()

        painter.save()
        painter.fillRect(content_rect, QColor(0, 0, 0, int(155 * intro_progress)))
        painter.setOpacity(0.22 + (intro_progress * 0.78))
        self._rounded_rect(painter, panel, 18, QColor("#2A2A2A"), QColor(255, 255, 255, 30), 1.0)
        if self.overlay_kind == "login":
            header_rect = QRectF(panel.x(), panel.y(), panel.width(), 82)
            self._rounded_rect(painter, header_rect, 18, QColor(255, 255, 255, 4), QColor(0, 0, 0, 0), 0.0)
            painter.setPen(QColor(255, 255, 255, 18))
            painter.drawLine(panel.x() + 28, panel.y() + 96, panel.right() - 28, panel.y() + 96)
        painter.restore()

        painter.save()
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
        if self.overlay_kind == "login" and self.overlay_link_text and "link" in layout:
            painter.setPen(QColor("#8FC95D"))
            font.setBold(True)
            font.setUnderline(True)
            font.setPixelSize(13)
            painter.setFont(font)
            painter.drawText(layout["link"], Qt.AlignLeft | Qt.AlignVCenter, self.overlay_link_text)
            font.setBold(False)
            font.setUnderline(False)
        else:
            painter.drawText(layout["message"], Qt.AlignLeft | Qt.AlignTop | Qt.TextWordWrap, self.overlay_message)

        if self.overlay_kind == "login":
            painter.setPen(QColor(235, 235, 235, 210))
            font.setBold(True)
            font.setPixelSize(13)
            painter.setFont(font)
            painter.drawText(QRectF(layout["input1"].x(), layout["input1"].y() - 24, 220, 18), Qt.AlignLeft | Qt.AlignVCenter, "Server URL")
            painter.drawText(QRectF(layout["input2"].x(), layout["input2"].y() - 24, 220, 18), Qt.AlignLeft | Qt.AlignVCenter, "Username")
            painter.drawText(QRectF(layout["input3"].x(), layout["input3"].y() - 24, 220, 18), Qt.AlignLeft | Qt.AlignVCenter, "Password")
            combined_enabled = self.overlay_remember_username and self.overlay_remember_password
            self._draw_overlay_toggle(painter, layout["toggle_combined"], "Remember Username/Password", combined_enabled)
        elif self.overlay_kind == "server_profile":
            painter.setPen(QColor(235, 235, 235, 210))
            font.setBold(True)
            font.setPixelSize(13)
            painter.setFont(font)
            painter.drawText(QRectF(layout["input1"].x(), layout["input1"].y() - 24, 220, 18), Qt.AlignLeft | Qt.AlignVCenter, "Server Name")
            painter.drawText(QRectF(layout["input2"].x(), layout["input2"].y() - 24, 220, 18), Qt.AlignLeft | Qt.AlignVCenter, "Server Address")

        self._draw_overlay_button(painter, layout["submit"], self.overlay_submit_label, primary=True)
        if self.overlay_alt_label and "alt" in layout:
            self._draw_overlay_button(painter, layout["alt"], self.overlay_alt_label, primary=False)
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
        desired_geometries: dict[str, QRectF] = {}

        if not self.overlay_kind:
            for widget in widgets.values():
                if not widget.isHidden():
                    widget.hide()
            return

        layout = self._overlay_layout(content_rect)
        if self.overlay_kind == "text_input":
            desired_geometries["text"] = layout["input1"]
        elif self.overlay_kind == "server_profile":
            desired_geometries["text"] = layout["input1"]
            desired_geometries["server_url"] = layout["input2"]
        elif self.overlay_kind == "login":
            desired_geometries["server_url"] = layout["input1"]
            desired_geometries["username"] = layout["input2"]
            desired_geometries["password"] = layout["input3"]

        for key, widget in widgets.items():
            rect = desired_geometries.get(key)
            if rect is None:
                if not widget.isHidden():
                    widget.hide()
                continue
            target_rect = rect.toRect()
            if widget.geometry() != target_rect:
                widget.setGeometry(target_rect)
            if widget.isHidden():
                widget.show()

    def _sync_setup_widgets(self, content_rect: QRectF) -> None:
        if self.current_screen not in {"setup", "settings"}:
            self.setup_name_edit.hide()
            self.setup_game_path_edit.hide()
            return

        settings_mode = self.current_screen == "settings"
        name_field_rect = self._ppt_rect(content_rect, 2333621, 1880000 if settings_mode else 2730000, 6657975, 540000)
        game_full_rect = self._ppt_rect(content_rect, 2333621, 3260000 if settings_mode else 5000000, 6657975, 540000)
        browse_button_rect = QRectF(game_full_rect.right() - 1320000 * (content_rect.width() / PPT_CX), game_full_rect.y(), 1320000 * (content_rect.width() / PPT_CX), game_full_rect.height())
        game_field_rect = QRectF(game_full_rect.x(), game_full_rect.y(), game_full_rect.width() - browse_button_rect.width() - 140000 * (content_rect.width() / PPT_CX), game_full_rect.height())
        _, intro_offset_y = self._setup_screen_intro_state(content_rect, settings_mode)
        if intro_offset_y:
            name_field_rect.translate(0.0, intro_offset_y)
            game_field_rect.translate(0.0, intro_offset_y)
        edit_rect = name_field_rect.adjusted(2, 2, -2, -2).toRect()
        if self.setup_name_edit.text() != self.setup_display_name:
            self.setup_name_edit.setText(self.setup_display_name)
        if self.setup_name_edit.geometry() != edit_rect:
            self.setup_name_edit.setGeometry(edit_rect)
        if self.setup_name_edit.isHidden():
            self.setup_name_edit.show()
        if self.setup_game_path_edit.text() != self.setup_game_path:
            self.setup_game_path_edit.setText(self.setup_game_path)
        game_edit_rect = game_field_rect.adjusted(2, 2, -2, -2).toRect()
        if self.setup_game_path_edit.geometry() != game_edit_rect:
            self.setup_game_path_edit.setGeometry(game_edit_rect)
        if self.setup_game_path_edit.isHidden():
            self.setup_game_path_edit.show()

    def _register_overlay_click_regions(self, content_rect: QRectF) -> None:
        if not self.overlay_kind:
            return
        layout = self._overlay_layout(content_rect)
        self.click_regions.append(("overlay_submit", self.overlay_action, layout["submit"]))
        if self.overlay_alt_label and "alt" in layout:
            self.click_regions.append(("overlay_alt", self.overlay_alt_action, layout["alt"]))
        if self.overlay_cancel_label:
            self.click_regions.append(("overlay_cancel", self.overlay_action, layout["cancel"]))
        if self.overlay_kind == "text_input":
            self.click_regions.append(("overlay_focus", "text", layout["input1"]))
        elif self.overlay_kind == "server_profile":
            self.click_regions.append(("overlay_focus", "text", layout["input1"]))
            self.click_regions.append(("overlay_focus", "server_url", layout["input2"]))
        elif self.overlay_kind == "login":
            self.click_regions.append(("overlay_focus", "server_url", layout["input1"]))
            self.click_regions.append(("overlay_focus", "username", layout["input2"]))
            self.click_regions.append(("overlay_focus", "password", layout["input3"]))
            self.click_regions.append(("overlay_toggle", "remember_both", layout["toggle_combined"]))
            if self.overlay_link_text and "link" in layout:
                self.click_regions.append(("overlay_link", self.overlay_link_url, layout["link"]))
