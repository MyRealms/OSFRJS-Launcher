from __future__ import annotations

from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QColor, QPainter, QPainterPath

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

    def _settings_layout(self, content_rect: QRectF) -> dict[str, QRectF]:
        """Full-screen settings layout. Every element is positioned relative to
        the full content area, so the screen is easy to scan and to extend."""
        header_height = 84.0
        back_size = 44.0
        back_rect = QRectF(
            content_rect.x() + 24,
            content_rect.y() + (header_height - back_size) / 2,
            back_size,
            back_size,
        )
        title_rect = QRectF(
            back_rect.right() + 16,
            content_rect.y(),
            content_rect.width() - back_rect.right() - 40,
            header_height,
        )

        content_margin = 40.0
        content_x = content_rect.x() + content_margin
        content_width = content_rect.width() - (content_margin * 2)
        content_top = content_rect.y() + header_height + 50

        name_label_rect = QRectF(content_x, content_top, content_width, 22)
        name_field_rect = QRectF(content_x, content_top + 30, content_width, 52)

        game_label_y = name_field_rect.bottom() + 40
        game_label_rect = QRectF(content_x, game_label_y, content_width, 22)
        game_field_h = 52
        browse_w = 220.0
        browse_button_rect = QRectF(
            content_x + content_width - browse_w,
            game_label_y + 30,
            browse_w,
            game_field_h,
        )
        game_field_rect = QRectF(
            content_x,
            game_label_y + 30,
            content_width - browse_w - 16,
            game_field_h,
        )

        # Open Config Folder sits on the left of the links row, just below the
        # game folder field. Reset Launcher Settings is a destructive action
        # so it's tucked into the bottom-right corner, above the disclaimer.
        links_y = game_field_rect.bottom() + 60
        config_link_rect = QRectF(content_x, links_y, content_width / 2 - 10, 30)
        reset_link_rect = QRectF(
            content_rect.right() - 320,
            content_rect.bottom() - 60,
            300,
            30,
        )

        button_h = 52
        button_w = 320.0
        button_y = content_rect.bottom() - button_h - 80
        button_rect = QRectF(
            content_rect.center().x() - button_w / 2,
            button_y,
            button_w,
            button_h,
        )

        disclaimer_rect = QRectF(content_x, content_rect.bottom() - 30, content_width, 20)

        return {
            "header_rect": QRectF(content_rect.x(), content_rect.y(), content_rect.width(), header_height),
            "back": back_rect,
            "title": title_rect,
            "name_label": name_label_rect,
            "name_field": name_field_rect,
            "game_label": game_label_rect,
            "game_field": game_field_rect,
            "browse": browse_button_rect,
            "config_link": config_link_rect,
            "reset_link": reset_link_rect,
            "button": button_rect,
            "disclaimer": disclaimer_rect,
        }

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

        # Cancel button while a launch/download is in progress.
        # Anchored to the right edge of the main content area and vertically
        # centred with the play button so it never overlaps the action panel.
        cancel_ppt_x = 9395597  # 11520488 - 1824891 - 300000 margin
        cancel_ppt_y = 6184128  # 6075000 + (653256 - 430000) / 2  → centred with Play
        cancel_ppt_w = 1824891
        cancel_ppt_h = 430000
        if getattr(self, "is_launching", False) and not getattr(self, "launch_cancelled", False):
            cancel_rect = self._ppt_rect(content_rect, cancel_ppt_x, cancel_ppt_y, cancel_ppt_w, cancel_ppt_h)
            self._rounded_rect(painter, cancel_rect, 10, QColor("#1F1F1F"), QColor(255, 255, 255, 40), 1.0)
            painter.save()
            painter.setPen(QColor(235, 235, 235, 230))
            font = painter.font()
            font.setFamily(self.display_font_family)
            font.setBold(True)
            font.setPixelSize(15)
            painter.setFont(font)
            painter.drawText(cancel_rect, Qt.AlignCenter, "Cancel")
            painter.restore()
            self.click_regions.append(("cancel_launch", "status", cancel_rect))
        elif getattr(self, "launch_cancelled", False):
            cancel_rect = self._ppt_rect(content_rect, cancel_ppt_x, cancel_ppt_y, cancel_ppt_w, cancel_ppt_h)
            painter.save()
            painter.setPen(QColor(200, 200, 200, 180))
            font = painter.font()
            font.setFamily(self.display_font_family)
            font.setBold(True)
            font.setPixelSize(14)
            painter.setFont(font)
            painter.drawText(cancel_rect, Qt.AlignCenter, "Cancelling...")
            painter.restore()

    def _draw_settings_screen(self, painter: QPainter, content_rect: QRectF) -> None:
        layout = self._settings_layout(content_rect)
        intro_opacity, intro_offset_y = self._setup_screen_intro_state(content_rect, True)

        # Background
        painter.save()
        painter.fillRect(content_rect, QColor("#1E1E1E"))
        painter.restore()

        # Header bar separator
        painter.save()
        painter.setOpacity(0.96)
        painter.fillRect(layout["header_rect"], QColor(255, 255, 255, 5))
        painter.setPen(QColor(255, 255, 255, 22))
        painter.drawLine(
            content_rect.x(),
            layout["header_rect"].bottom(),
            content_rect.right(),
            layout["header_rect"].bottom(),
        )
        painter.restore()

        # Apply intro animation to the rest of the screen
        painter.save()
        painter.setOpacity(intro_opacity)
        if intro_offset_y:
            painter.translate(0.0, intro_offset_y)

        # Back button
        self._draw_back_button(painter, layout["back"])

        # Title
        painter.setPen(QColor("#FFFFFF"))
        font = painter.font()
        font.setFamily(self.display_font_family)
        font.setBold(True)
        font.setPixelSize(26)
        painter.setFont(font)
        painter.drawText(layout["title"], Qt.AlignLeft | Qt.AlignVCenter, "Settings")

        # Field labels
        painter.setPen(QColor(235, 235, 235, 210))
        font.setBold(True)
        font.setPixelSize(14)
        painter.setFont(font)
        painter.drawText(layout["name_label"], Qt.AlignLeft | Qt.AlignVCenter, "Display Name")
        painter.drawText(layout["game_label"], Qt.AlignLeft | Qt.AlignVCenter, "Game Folder")

        # Game Folder hint
        painter.setPen(QColor(222, 222, 200))
        font.setBold(False)
        font.setPixelSize(13)
        painter.setFont(font)
        hint_rect = QRectF(
            layout["game_field"].x(),
            layout["game_field"].bottom() + 6,
            layout["game_field"].width(),
            18,
        )
        painter.drawText(
            hint_rect,
            Qt.AlignLeft | Qt.AlignVCenter,
            "Choose the folder that contains FreeRealms.exe",
        )

        # Quick links
        painter.setPen(QColor("#9FB8D9"))
        font.setBold(True)
        font.setPixelSize(15)
        painter.setFont(font)
        painter.drawText(layout["config_link"], Qt.AlignLeft | Qt.AlignVCenter, "Open Config Folder")
        painter.setPen(QColor("#8FC95D"))
        painter.drawText(layout["reset_link"], Qt.AlignRight | Qt.AlignVCenter, "Reset Launcher Settings")

        # Input boxes
        self._draw_input_box(painter, layout["name_field"], "")
        self._draw_input_box(painter, layout["game_field"], "")

        # Browse button
        self._rounded_rect(
            painter,
            layout["browse"],
            10,
            QColor("#78A84A"),
            QColor(214, 245, 176, 130),
            1.0,
        )
        painter.setPen(QColor("#FFFFFF"))
        font.setBold(True)
        font.setPixelSize(16)
        painter.setFont(font)
        painter.drawText(layout["browse"], Qt.AlignCenter, "Browse")

        # Save Changes button
        if self.play_button_svg and self.play_button_svg.isValid():
            self.play_button_svg.render(painter, layout["button"])
        else:
            self._rounded_rect(painter, layout["button"], 20, QColor("#78A84A"))
        painter.setPen(QColor("#FFFFFF"))
        font.setBold(True)
        font.setPixelSize(24)
        painter.setFont(font)
        painter.drawText(layout["button"], Qt.AlignCenter, "Save Changes")

        # Disclaimer
        painter.setPen(QColor(215, 215, 215, 135))
        font.setBold(False)
        font.setPixelSize(11)
        painter.setFont(font)
        painter.drawText(
            layout["disclaimer"],
            Qt.AlignCenter | Qt.AlignVCenter,
            "Unofficial fan project. Not affiliated with Sony or Daybreak.",
        )

        painter.restore()

    def _draw_setup_screen(self, painter: QPainter, content_rect: QRectF, settings_mode: bool) -> None:
        if settings_mode:
            self._draw_settings_screen(painter, content_rect)
            return
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
        name_field_rect = self._ppt_rect(content_rect, 2333621, 1880000 if settings_mode else 3620000, 6657975, 540000)
        game_full_rect = self._ppt_rect(content_rect, 2333621, 3260000 if settings_mode else 5000000, 6657975, 540000)
        scale_x = content_rect.width() / PPT_CX
        scale_y = content_rect.height() / PPT_CY
        name_label_rect = QRectF(name_field_rect.x(), name_field_rect.y() - 360000 * scale_y, name_field_rect.width(), 220000 * scale_y)
        game_label_rect = QRectF(game_full_rect.x(), game_full_rect.y() - 460000 * scale_y, game_full_rect.width(), 220000 * scale_y)
        game_hint_rect = QRectF(game_full_rect.x(), game_full_rect.y() - 200000 * scale_y, game_full_rect.width(), 170000 * scale_y)
        browse_button_rect = QRectF(game_full_rect.right() - 1320000 * (content_rect.width() / PPT_CX), game_full_rect.y(), 1320000 * (content_rect.width() / PPT_CX), game_full_rect.height())
        game_field_rect = QRectF(game_full_rect.x(), game_full_rect.y(), game_full_rect.width() - browse_button_rect.width() - 140000 * (content_rect.width() / PPT_CX), game_full_rect.height())
        button_rect = self._ppt_rect(content_rect, 4347800, 6210516 if settings_mode else 4770000, 2824891, 653256)
        back_rect = self._ppt_rect(content_rect, 260000, 260000, 1380000, 380000)
        footer_note_rect = self._ppt_rect(content_rect, 2333621, 5640000, 4200000, 290000)
        disclaimer_rect = (
            QRectF(
                form_card_rect.x() + 280000 * scale_x,
                form_card_rect.bottom() - 300000 * scale_y,
                form_card_rect.width() - 560000 * scale_x,
                220000 * scale_y,
            )
            if settings_mode
            else self._ppt_rect(content_rect, 2333621, 5960000, 6657975, 260000)
        )
        reset_rect = QRectF(
            form_card_rect.right() - 2600000 * scale_x,
            form_card_rect.bottom() - 340000 * scale_y,
            2450000 * scale_x,
            240000 * scale_y,
        )
        # "Open Config Folder" button, placed to the left of the reset button.
        config_rect = QRectF(
            form_card_rect.x() + 150000 * scale_x,
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
        painter.drawText(name_label_rect, (Qt.AlignLeft if settings_mode else Qt.AlignCenter) | Qt.AlignVCenter, "Display Name")
        if settings_mode:
            painter.drawText(game_label_rect, Qt.AlignLeft | Qt.AlignVCenter, "Game Folder")

        if settings_mode:
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
            painter.setPen(QColor("#9FB8D9"))
            painter.setFont(font)
            painter.drawText(config_rect, Qt.AlignLeft | Qt.AlignVCenter, "Open Config Folder")
        else:
            painter.setPen(QColor(220, 220, 220, 165))
            font.setBold(False)
            font.setPixelSize(13)
            painter.setFont(font)
            painter.drawText(footer_note_rect, Qt.AlignLeft | Qt.AlignVCenter, "You can change these later in Settings.")
        painter.setPen(QColor(215, 215, 215, 135))
        font.setBold(False)
        font.setPixelSize(11)
        painter.setFont(font)
        painter.drawText(
            disclaimer_rect,
            ((Qt.AlignLeft | Qt.AlignVCenter) if settings_mode else (Qt.AlignCenter | Qt.AlignVCenter)) | Qt.TextWordWrap,
            "Unofficial fan project. Not affiliated with Sony or Daybreak.",
        )
        painter.restore()

        self._draw_input_box(painter, name_field_rect, "")
        if settings_mode:
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
        if settings_mode:
            layout = self._settings_layout(content_rect)
            _, intro_offset_y = self._setup_screen_intro_state(content_rect, True)
            name_field_rect = QRectF(layout["name_field"])
            game_field_rect = QRectF(layout["game_field"])
            browse_button_rect = QRectF(layout["browse"])
            button_rect = QRectF(layout["button"])
            reset_rect = QRectF(layout["reset_link"])
            config_rect = QRectF(layout["config_link"])
            back_rect = QRectF(layout["back"])
            for rect in (
                name_field_rect,
                game_field_rect,
                browse_button_rect,
                button_rect,
                reset_rect,
                config_rect,
                back_rect,
            ):
                if intro_offset_y:
                    rect.translate(0.0, intro_offset_y)
            self.click_regions.append(("setup_field", "display_name", name_field_rect))
            self.click_regions.append(("setup_field", "game_path", game_field_rect))
            self.click_regions.append(("setup_browse", "game_path", browse_button_rect))
            self.click_regions.append(("setup_submit", "settings", button_rect))
            self.click_regions.append(("open_config_folder", "settings", config_rect))
            self.click_regions.append(("setup_reset", "settings", reset_rect))
            self.click_regions.append(("back_to_main", "main", back_rect))
            return

        name_field_rect = self._ppt_rect(content_rect, 2333621, 3620000, 6657975, 540000)
        button_rect = self._ppt_rect(content_rect, 4347800, 4770000, 2824891, 653256)
        self.click_regions.append(("setup_field", "display_name", name_field_rect))
        self.click_regions.append(("setup_submit", "setup", button_rect))

    def _overlay_layout(self, content_rect: QRectF) -> dict[str, QRectF]:
        # Full-screen overlay panel - the entire content area is the panel.
        # This makes positioning easier (everything is relative to the full
        # window) and gives content enough breathing room to be readable.
        panel = QRectF(content_rect)

        intro_progress = self._overlay_intro_progress()
        panel.translate(0.0, content_rect.height() * 0.04 * (1.0 - intro_progress))

        # Header bar (back button + title)
        header_height = 84.0
        back_size = 44.0
        back_rect = QRectF(
            panel.x() + 24,
            panel.y() + (header_height - back_size) / 2,
            back_size,
            back_size,
        )
        title_rect = QRectF(
            back_rect.right() + 16,
            panel.y(),
            panel.width() - back_rect.right() - 40,
            header_height,
        )

        # Content area
        content_margin = 32.0
        content_top = panel.y() + header_height + content_margin

        # Buttons at the bottom
        button_height = 52.0
        button_margin = 32.0
        button_gap = 20.0
        button_y = panel.bottom() - button_height - 28
        button_width = (panel.width() - (button_margin * 2) - button_gap) / 2.0

        # Default message rect (used for descriptions on text_input / server_profile
        # and as the main body on message/confirm). Overridden below for login and
        # for the full-height message/confirm case.
        default_message = QRectF(
            panel.x() + content_margin,
            content_top,
            panel.width() - (content_margin * 2),
            22.0,
        )

        layout = {
            "panel": panel,
            "back": back_rect,
            "title": title_rect,
            "message": default_message,
            "submit": QRectF(panel.right() - button_margin - button_width, button_y, button_width, button_height),
            "cancel": QRectF(panel.x() + button_margin, button_y, button_width, button_height),
        }

        # Single-button overlays (e.g. message/OK): centre the submit button so it
        # isn't stuck in a corner with empty space beside it.
        if not self.overlay_cancel_label:
            centered_width = min(button_width * 1.6, panel.width() - button_margin * 2)
            layout["submit"] = QRectF(
                panel.center().x() - centered_width / 2.0,
                button_y,
                centered_width,
                button_height,
            )
        if self.overlay_kind == "text_input":
            layout["input1"] = QRectF(
                panel.x() + content_margin,
                content_top + 50,
                panel.width() - (content_margin * 2),
                52.0,
            )
        elif self.overlay_kind == "server_profile":
            field_height = 52.0
            # 2-column grid for the four primary fields:
            #   row 1: Server Name | Server Address
            #   row 2: Username    | Password
            col_gap = 24.0
            col_width = (panel.width() - (content_margin * 2) - col_gap) / 2.0
            col1_x = panel.x() + content_margin
            col2_x = col1_x + col_width + col_gap
            row_top = content_top + 30

            layout["input1"] = QRectF(col1_x, row_top, col_width, field_height)
            layout["input2"] = QRectF(col2_x, row_top, col_width, field_height)
            row2_top = layout["input1"].bottom() + 32
            layout["input3"] = QRectF(col1_x, row2_top, col_width, field_height)
            layout["input4"] = QRectF(col2_x, row2_top, col_width, field_height)

            toggle_y = layout["input3"].bottom() + 18
            layout["toggle_credentials"] = QRectF(
                panel.x() + content_margin,
                toggle_y,
                panel.width() - (content_margin * 2),
                24,
            )

            # Icon strip — horizontal scrollable row of thumbnails. Strip area
            # stays a fixed rectangle; the actual thumbnail positions are
            # computed in the drawing/click code using the current scroll.
            strip_label_y = layout["toggle_credentials"].bottom() + 18
            strip_y = strip_label_y + 26
            strip_height = 80.0
            layout["icon_strip"] = QRectF(
                panel.x() + content_margin,
                strip_y,
                panel.width() - (content_margin * 2),
                strip_height,
            )

            if self.overlay_alt_label:
                alt_width = (panel.width() - (content_margin * 2) - (button_gap * 2)) / 3.0
                layout["alt"] = QRectF(panel.x() + content_margin, button_y, alt_width, button_height)
                layout["cancel"] = QRectF(panel.x() + content_margin + alt_width + button_gap, button_y, alt_width, button_height)
                layout["submit"] = QRectF(panel.x() + content_margin + ((alt_width + button_gap) * 2), button_y, alt_width, button_height)
        elif self.overlay_kind == "login":
            field_height = 52.0
            field_gap = 40.0
            # Login reuses the message slot for the link/instruction line.
            layout["message"] = QRectF(panel.x() + content_margin, content_top, panel.width() - (content_margin * 2), 22)
            if self.overlay_link_text:
                layout["link"] = layout["message"]
            layout["input1"] = QRectF(panel.x() + content_margin, content_top + 52, panel.width() - (content_margin * 2), field_height)
            layout["input2"] = QRectF(panel.x() + content_margin, layout["input1"].bottom() + field_gap, panel.width() - (content_margin * 2), field_height)
            layout["input3"] = QRectF(panel.x() + content_margin, layout["input2"].bottom() + field_gap, panel.width() - (content_margin * 2), field_height)
            layout["toggle_combined"] = QRectF(panel.x() + content_margin, layout["input3"].bottom() + 20, panel.width() - (content_margin * 2), 24)
        else:
            # message/confirm overlays: let the message span from below the title
            # down to just above the action buttons.
            message_top = content_top + 10
            message_bottom = button_y - 20
            layout["message"] = QRectF(
                panel.x() + 40,
                message_top,
                panel.width() - 80,
                max(60.0, message_bottom - message_top),
            )
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
        painter.drawText(rect, Qt.AlignCenter, self._elide_text(painter, text, rect.width() - 12))
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
        text_rect = QRectF(rect.x() + 28, rect.y(), rect.width() - 28, rect.height())
        painter.drawText(
            text_rect,
            Qt.AlignLeft | Qt.AlignVCenter,
            self._elide_text(painter, text, text_rect.width()),
        )
        painter.restore()

    def _draw_back_button(self, painter: QPainter, rect: QRectF) -> None:
        self._rounded_rect(painter, rect, 10, QColor("#1F1F1F"), QColor(255, 255, 255, 26), 1.0)
        painter.save()
        painter.setRenderHint(QPainter.Antialiasing)
        pen = painter.pen()
        pen.setColor(QColor("#EAEAEA"))
        pen.setWidth(2)
        pen.setCapStyle(Qt.RoundCap)
        pen.setJoinStyle(Qt.RoundJoin)
        painter.setPen(pen)
        # Left-pointing chevron
        cx = rect.center().x()
        cy = rect.center().y()
        s = rect.width() * 0.18
        path = QPainterPath()
        path.moveTo(cx + s * 0.4, cy - s)
        path.lineTo(cx - s * 0.6, cy)
        path.lineTo(cx + s * 0.4, cy + s)
        painter.drawPath(path)
        painter.restore()

    def _draw_server_icon_strip(self, painter: QPainter, layout: dict[str, QRectF]) -> None:
        from .server_icons import available_icons, load_icon_pixmap

        strip_rect = layout["icon_strip"]
        icons = available_icons()
        if not icons:
            painter.save()
            painter.setPen(QColor(200, 200, 200, 150))
            font = painter.font()
            font.setFamily(self.display_font_family)
            font.setBold(False)
            font.setPixelSize(13)
            painter.setFont(font)
            painter.drawText(
                strip_rect,
                Qt.AlignCenter,
                "Drop PNG icons into assets/server_icons/ to populate this list.",
            )
            painter.restore()
            return

        # Background of the strip
        self._rounded_rect(painter, strip_rect, 10, QColor(255, 255, 255, 6), QColor(255, 255, 255, 22), 1.0)

        thumb_size = 64.0
        thumb_gap = 10.0
        slot = thumb_size + thumb_gap
        visible_count = max(1, int((strip_rect.width() + thumb_gap) / slot))
        # Clamp scroll offset to a valid range based on the icon count.
        max_scroll = max(0.0, (len(icons) - visible_count) * slot)
        scroll = max(0.0, min(getattr(self, "overlay_icon_strip_scroll", 0.0), max_scroll))
        self.overlay_icon_strip_scroll = scroll

        painter.save()
        painter.setClipRect(strip_rect)
        first_index = int(scroll / slot)
        offset_in_slot = scroll - (first_index * slot)
        x = strip_rect.x() - offset_in_slot
        y = strip_rect.center().y() - thumb_size / 2

        selected = getattr(self, "overlay_icon_name", "")
        for index in range(first_index, len(icons)):
            thumb_rect = QRectF(x, y, thumb_size, thumb_size)
            name = icons[index]
            pixmap = load_icon_pixmap(name)
            is_selected = name == selected

            # Slot background
            slot_color = QColor("#1F1F1F")
            outline = QColor(143, 201, 93, 220) if is_selected else QColor(255, 255, 255, 30)
            self._rounded_rect(painter, thumb_rect, 8, slot_color, outline, 2.0 if is_selected else 1.0)
            if not pixmap.isNull():
                painter.save()
                clip_path = QPainterPath()
                clip_path.addRoundedRect(thumb_rect.adjusted(4, 4, -4, -4), 6, 6)
                painter.setClipPath(clip_path)
                scaled = pixmap.scaled(
                    int(thumb_size - 8),
                    int(thumb_size - 8),
                    Qt.KeepAspectRatio,
                    Qt.SmoothTransformation,
                )
                dx = thumb_rect.x() + (thumb_size - scaled.width()) / 2
                dy = thumb_rect.y() + (thumb_size - scaled.height()) / 2
                painter.drawPixmap(int(dx), int(dy), scaled)
                painter.restore()
            else:
                painter.setPen(QColor(180, 180, 180, 180))
                font = painter.font()
                font.setPixelSize(9)
                painter.setFont(font)
                painter.drawText(thumb_rect, Qt.AlignCenter, name)

            x += slot
            if x > strip_rect.right():
                break
        painter.restore()

    def _draw_overlay(self, painter: QPainter, content_rect: QRectF) -> None:
        if not self.overlay_kind:
            return

        layout = self._overlay_layout(content_rect)
        panel = layout["panel"]
        intro_progress = self._overlay_intro_progress()

        painter.save()
        # Full-screen panel: the panel itself is the screen, so no dimming
        # backdrop is needed.
        painter.setOpacity(0.96)
        self._rounded_rect(painter, panel, 0, QColor("#1A1A1A"), QColor(255, 255, 255, 18), 1.0)

        # Header bar separator
        header_height = 84.0
        header_rect = QRectF(panel.x(), panel.y(), panel.width(), header_height)
        painter.fillRect(header_rect, QColor(255, 255, 255, 5))
        painter.setPen(QColor(255, 255, 255, 22))
        painter.drawLine(panel.x(), header_rect.bottom(), panel.right(), header_rect.bottom())
        painter.restore()

        # Back button (top-left)
        painter.save()
        self._draw_back_button(painter, layout["back"])
        painter.restore()

        painter.save()
        painter.setPen(QColor("#FFFFFF"))
        font = painter.font()
        font.setFamily(self.display_font_family)
        font.setBold(True)
        font.setPixelSize(26)
        painter.setFont(font)
        painter.drawText(
            layout["title"],
            Qt.AlignLeft | Qt.AlignVCenter,
            self._elide_text(painter, self.overlay_title, layout["title"].width()),
        )

        if self.overlay_kind == "login" and self.overlay_link_text and "link" in layout:
            painter.setPen(QColor("#8FC95D"))
            font.setBold(True)
            font.setUnderline(True)
            font.setPixelSize(14)
            painter.setFont(font)
            painter.drawText(
                layout["link"],
                Qt.AlignLeft | Qt.AlignVCenter,
                self._elide_text(painter, self.overlay_link_text, layout["link"].width()),
            )
            font.setBold(False)
            font.setUnderline(False)
        else:
            painter.setPen(QColor(225, 225, 225, 210))
            font.setBold(False)
            font.setPixelSize(15)
            painter.setFont(font)
            painter.drawText(
                layout["message"],
                Qt.AlignLeft | Qt.AlignTop | Qt.TextWordWrap,
                self.overlay_message,
            )

        if self.overlay_kind == "login":
            painter.setPen(QColor(235, 235, 235, 210))
            font.setBold(True)
            font.setPixelSize(14)
            painter.setFont(font)
            painter.drawText(QRectF(layout["input1"].x(), layout["input1"].y() - 26, 220, 20), Qt.AlignLeft | Qt.AlignVCenter, "Server URL")
            painter.drawText(QRectF(layout["input2"].x(), layout["input2"].y() - 26, 220, 20), Qt.AlignLeft | Qt.AlignVCenter, "Username")
            painter.drawText(QRectF(layout["input3"].x(), layout["input3"].y() - 26, 220, 20), Qt.AlignLeft | Qt.AlignVCenter, "Password")
            combined_enabled = self.overlay_remember_username and self.overlay_remember_password
            self._draw_overlay_toggle(painter, layout["toggle_combined"], "Remember Username/Password", combined_enabled)
        elif self.overlay_kind == "server_profile":
            painter.setPen(QColor(235, 235, 235, 210))
            font.setBold(True)
            font.setPixelSize(14)
            painter.setFont(font)
            painter.drawText(QRectF(layout["input1"].x(), layout["input1"].y() - 26, 220, 20), Qt.AlignLeft | Qt.AlignVCenter, "Server Name")
            painter.drawText(QRectF(layout["input2"].x(), layout["input2"].y() - 26, 220, 20), Qt.AlignLeft | Qt.AlignVCenter, "Server Address")
            painter.drawText(QRectF(layout["input3"].x(), layout["input3"].y() - 26, 220, 20), Qt.AlignLeft | Qt.AlignVCenter, "Username")
            painter.drawText(QRectF(layout["input4"].x(), layout["input4"].y() - 26, 220, 20), Qt.AlignLeft | Qt.AlignVCenter, "Password")
            combined_enabled = self.overlay_remember_username and self.overlay_remember_password
            self._draw_overlay_toggle(painter, layout["toggle_credentials"], "Remember Username/Password", combined_enabled)
            # Server icon strip label + thumbnails
            painter.setPen(QColor(235, 235, 235, 210))
            font.setBold(True)
            font.setPixelSize(14)
            painter.setFont(font)
            painter.drawText(
                QRectF(layout["icon_strip"].x(), layout["icon_strip"].y() - 24, 220, 20),
                Qt.AlignLeft | Qt.AlignVCenter,
                "Server Icon",
            )
            self._draw_server_icon_strip(painter, layout)

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
            desired_geometries["username"] = layout["input3"]
            desired_geometries["password"] = layout["input4"]
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
        if settings_mode:
            layout = self._settings_layout(content_rect)
            _, intro_offset_y = self._setup_screen_intro_state(content_rect, True)
            name_field_rect = QRectF(layout["name_field"])
            game_field_rect = QRectF(layout["game_field"])
            if intro_offset_y:
                name_field_rect.translate(0.0, intro_offset_y)
                game_field_rect.translate(0.0, intro_offset_y)
        else:
            name_field_rect = self._ppt_rect(content_rect, 2333621, 3620000, 6657975, 540000)
            game_field_rect = QRectF()

        edit_rect = name_field_rect.adjusted(2, 2, -2, -2).toRect()
        if self.setup_name_edit.text() != self.setup_display_name:
            self.setup_name_edit.setText(self.setup_display_name)
        if self.setup_name_edit.geometry() != edit_rect:
            self.setup_name_edit.setGeometry(edit_rect)
        if self.setup_name_edit.isHidden():
            self.setup_name_edit.show()
        if not settings_mode:
            if not self.setup_game_path_edit.isHidden():
                self.setup_game_path_edit.hide()
            return
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
        self.click_regions.append(("overlay_back", self.overlay_action, layout["back"]))
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
            self.click_regions.append(("overlay_focus", "username", layout["input3"]))
            self.click_regions.append(("overlay_focus", "password", layout["input4"]))
            self.click_regions.append(("overlay_toggle", "remember_both", layout["toggle_credentials"]))
            # Icon strip — one clickable thumbnail per visible icon.
            from .server_icons import available_icons

            strip_rect = layout["icon_strip"]
            icons = available_icons()
            if icons:
                thumb_size = 64.0
                thumb_gap = 10.0
                slot = thumb_size + thumb_gap
                visible_count = max(1, int((strip_rect.width() + thumb_gap) / slot))
                max_scroll = max(0.0, (len(icons) - visible_count) * slot)
                scroll = max(0.0, min(self.overlay_icon_strip_scroll, max_scroll))
                first_index = int(scroll / slot)
                offset_in_slot = scroll - (first_index * slot)
                x = strip_rect.x() - offset_in_slot
                y = strip_rect.center().y() - thumb_size / 2
                for index in range(first_index, len(icons)):
                    thumb_rect = QRectF(x, y, thumb_size, thumb_size)
                    if thumb_rect.right() < strip_rect.left() or thumb_rect.left() > strip_rect.right():
                        x += slot
                        continue
                    if thumb_rect.left() >= strip_rect.left() and thumb_rect.right() <= strip_rect.right():
                        self.click_regions.append(("overlay_select_icon", icons[index], thumb_rect))
                    x += slot
                    if x > strip_rect.right():
                        break
        elif self.overlay_kind == "login":
            self.click_regions.append(("overlay_focus", "server_url", layout["input1"]))
            self.click_regions.append(("overlay_focus", "username", layout["input2"]))
            self.click_regions.append(("overlay_focus", "password", layout["input3"]))
            self.click_regions.append(("overlay_toggle", "remember_both", layout["toggle_combined"]))
            if self.overlay_link_text and "link" in layout:
                self.click_regions.append(("overlay_link", self.overlay_link_url, layout["link"]))
