from __future__ import annotations

from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QColor, QPainter


class LauncherWidgetRenderNavigationMixin:
    def _sidebar_profiles(self):
        return self.settings.all_profiles()

    def _menu_view_rect(self, content_rect: QRectF) -> QRectF:
        top_split_y = 1091350
        bottom_split_y = 6115000
        return self._ppt_rect(content_rect, 0, top_split_y, 2558233, bottom_split_y - top_split_y)

    def _menu_layout(self, content_rect: QRectF) -> dict[str, float | QRectF]:
        view_rect = self._menu_view_rect(content_rect)
        scale_y = content_rect.height() / 7199313
        slot_height = 760000.0 * scale_y
        gap = 100000.0 * scale_y
        profile_count = len(self._sidebar_profiles())
        if profile_count > 1:
            fill_gap = (view_rect.height() - (profile_count * slot_height)) / (profile_count - 1)
            gap = max(gap, fill_gap)
        total_height = (profile_count * slot_height) + (max(0, profile_count - 1) * gap)
        max_scroll = max(0.0, total_height - view_rect.height())
        self.menu_scroll_offset = min(max(0.0, self.menu_scroll_offset), max_scroll)
        start_y = view_rect.y()
        if max_scroll > 0.0:
            start_y = view_rect.y() - self.menu_scroll_offset
        return {
            "view_rect": view_rect,
            "slot_height": slot_height,
            "gap": gap,
            "start_y": start_y,
            "max_scroll": max_scroll,
        }

    def _menu_label_for_profile(self, profile) -> list[str]:
        if profile.key == "offline_mode":
            return ["Local Server", "Offline Mode"]
        if profile.key == "osfr_server":
            return ["Online Server", "OSFR"]
        if profile.key == "freerealmsjs":
            return ["Browser", "FreeRealmsJS"]
        return [profile.subtitle or "Custom Server", profile.title or profile.name or "Custom Server"]

    def _menu_icon_for_profile(self, profile):
        if profile.key == "offline_mode":
            return self.local_icon_svg
        if profile.key == "freerealmsjs":
            return self.browser_icon_svg
        return self.online_icon_svg

    def _menu_item_rects(self, content_rect: QRectF) -> list[QRectF]:
        layout = self._menu_layout(content_rect)
        view_rect = layout["view_rect"]
        slot_height = float(layout["slot_height"])
        gap = float(layout["gap"])
        start_y = float(layout["start_y"])
        item_width = self._ppt_rect(content_rect, 0, 0, 2558233, 0).width()
        return [
            QRectF(view_rect.x(), start_y + (index * (slot_height + gap)), item_width, slot_height)
            for index in range(len(self._sidebar_profiles()))
        ]

    def _menu_edit_rect(self, content_rect: QRectF, index: int) -> QRectF:
        item_rect = self._menu_item_rects(content_rect)[index]
        button_size = min(item_rect.height() * 0.38, content_rect.width() * 0.028)
        return QRectF(
            item_rect.right() - button_size - 18.0,
            item_rect.center().y() - (button_size / 2.0),
            button_size,
            button_size,
        )

    def _menu_scrollbar_track_rect(self, content_rect: QRectF) -> QRectF:
        view_rect = self._menu_view_rect(content_rect)
        return QRectF(view_rect.x() + 2.0, view_rect.y() + 4.0, 7.0, view_rect.height() - 8.0)

    def _menu_scrollbar_thumb_rect(self, content_rect: QRectF) -> QRectF | None:
        layout = self._menu_layout(content_rect)
        max_scroll = float(layout["max_scroll"])
        if max_scroll <= 0.0:
            return None
        track_rect = self._menu_scrollbar_track_rect(content_rect)
        view_rect = layout["view_rect"]
        total_content_height = view_rect.height() + max_scroll
        thumb_height = max(36.0, track_rect.height() * (view_rect.height() / total_content_height))
        travel = max(0.0, track_rect.height() - thumb_height)
        progress = 0.0 if max_scroll <= 0.0 else min(1.0, max(0.0, self.menu_scroll_offset / max_scroll))
        return QRectF(track_rect.x(), track_rect.y() + (travel * progress), track_rect.width(), thumb_height)

    def _draw_edit_button(self, painter: QPainter, rect: QRectF) -> None:
        self._rounded_rect(painter, rect, 8, QColor(255, 255, 255, 12), QColor(255, 255, 255, 28), 1.0)
        painter.save()
        painter.setRenderHint(QPainter.Antialiasing)
        pen = painter.pen()
        pen.setColor(QColor("#EAEAEA"))
        pen.setWidth(2)
        painter.setPen(pen)
        painter.drawLine(rect.x() + rect.width() * 0.34, rect.y() + rect.height() * 0.68, rect.x() + rect.width() * 0.66, rect.y() + rect.height() * 0.36)
        painter.drawLine(rect.x() + rect.width() * 0.38, rect.y() + rect.height() * 0.74, rect.x() + rect.width() * 0.70, rect.y() + rect.height() * 0.42)
        painter.drawLine(rect.x() + rect.width() * 0.62, rect.y() + rect.height() * 0.32, rect.x() + rect.width() * 0.72, rect.y() + rect.height() * 0.42)
        painter.restore()

    def _draw_sidebar_multiline_text(
        self,
        painter: QPainter,
        rect: QRectF,
        lines: list[str],
        *,
        color: QColor,
        pixel_size: int,
        bold: bool = True,
        line_gap: float = 6.0,
    ) -> None:
        painter.save()
        painter.setPen(color)
        font = painter.font()
        font.setFamily(self.display_font_family)
        font.setBold(bold)
        font.setPixelSize(pixel_size)
        painter.setFont(font)

        metrics = painter.fontMetrics()
        line_height = metrics.height()
        total_height = line_height * len(lines) + max(0, len(lines) - 1) * line_gap
        y = rect.y() + max(0.0, (rect.height() - total_height) / 2.0)

        for line in lines:
            line_rect = QRectF(rect.x(), y, rect.width(), line_height + 4)
            painter.drawText(line_rect, Qt.AlignLeft | Qt.AlignVCenter, line)
            y += line_height + line_gap

        painter.restore()

    def _draw_left_navigation(self, painter: QPainter, content_rect: QRectF) -> None:
        username = self.settings.display_name.strip() or "CoderA"
        header_rect = self._ppt_rect(content_rect, 0, 158584, 2101422, 646331)
        scale_x = content_rect.width() / 11520488
        scale_y = content_rect.height() / 7199313
        welcome_rect = QRectF(
            header_rect.x() + 185000 * scale_x,
            header_rect.y() + 170000 * scale_y,
            header_rect.width() - 320000 * scale_x,
            220000 * scale_y,
        )
        username_rect = QRectF(
            header_rect.x() + 185000 * scale_x,
            header_rect.y() + 405000 * scale_y,
            header_rect.width() - 260000 * scale_x,
            340000 * scale_y,
        )
        painter.save()
        painter.setPen(QColor("#8FC95D"))
        font = painter.font()
        font.setFamily(self.display_font_family)
        font.setBold(True)
        font.setPixelSize(16)
        painter.setFont(font)
        painter.drawText(welcome_rect, Qt.AlignLeft | Qt.AlignVCenter, "Welcome Back")

        painter.setPen(QColor("#FFFFFF"))
        font.setFamily(self.display_font_family)
        font.setPixelSize(32)
        painter.setFont(font)
        painter.drawText(username_rect, Qt.AlignLeft | Qt.AlignVCenter, username)

        profiles = self._sidebar_profiles()
        menu_rects = self._menu_item_rects(content_rect)
        view_rect = self._menu_view_rect(content_rect)
        painter.save()
        painter.setClipRect(view_rect)
        for index, profile in enumerate(profiles):
            item_rect = menu_rects[index]
            if not item_rect.intersects(view_rect):
                continue
            icon_svg = self._menu_icon_for_profile(profile)
            icon_rect = QRectF(
                item_rect.x() + (60960 * (content_rect.width() / 11520488)),
                item_rect.center().y() - (535543 * (content_rect.height() / 7199313) / 2.0),
                586547 * (content_rect.width() / 11520488),
                535543 * (content_rect.height() / 7199313),
            )
            if icon_svg and icon_svg.isValid():
                icon_svg.render(painter, icon_rect)
            else:
                self._draw_nav_icon(painter, icon_rect, QColor("#7B7B7B"))

            label_rect = QRectF(
                item_rect.x() + (770000 * (content_rect.width() / 11520488)),
                item_rect.center().y() - (584775 * (content_rect.height() / 7199313) / 2.0),
                1788232 * (content_rect.width() / 11520488),
                584775 * (content_rect.height() / 7199313),
            )
            self._draw_sidebar_multiline_text(
                painter,
                label_rect,
                self._menu_label_for_profile(profile),
                color=QColor("#FFFFFF"),
                pixel_size=18,
                bold=True,
                line_gap=4.0,
            )

            if self.current_screen == "main" and self.hovered_menu_index == index and self.overlay_kind is None:
                self._draw_edit_button(painter, self._menu_edit_rect(content_rect, index))
        painter.restore()

        thumb_rect = self._menu_scrollbar_thumb_rect(content_rect)
        if thumb_rect is not None and (self.menu_list_hovered or self.menu_scrollbar_dragging or self.menu_scrollbar_hovered):
            track_rect = self._menu_scrollbar_track_rect(content_rect)
            self._rounded_rect(painter, track_rect, 4, QColor(255, 255, 255, 18), QColor(255, 255, 255, 20), 1.0)
            thumb_color = QColor("#8FC95D") if self.menu_scrollbar_dragging or self.menu_scrollbar_hovered else QColor(255, 255, 255, 80)
            self._rounded_rect(painter, thumb_rect, 4, thumb_color)

        settings_button_rect = self._ppt_rect(content_rect, 420000, 6635000, 1700000, 500000)
        add_server_button_rect = self._ppt_rect(content_rect, 420000, 6115000, 1700000, 500000)
        self._rounded_rect(
            painter,
            add_server_button_rect,
            10,
            QColor(255, 255, 255, 8),
            QColor(255, 255, 255, 26),
            1.0,
        )
        painter.setPen(QColor("#FFFFFF"))
        font.setBold(True)
        font.setPixelSize(16)
        font.setFamily(self.display_font_family)
        painter.setFont(font)
        painter.drawText(add_server_button_rect, Qt.AlignCenter, "Add Server")

        self._rounded_rect(
            painter,
            settings_button_rect,
            10,
            QColor(255, 255, 255, 8 if self.current_screen != "settings" else 16),
            QColor(255, 255, 255, 26),
            1.0,
        )
        painter.setPen(QColor("#FFFFFF"))
        font.setBold(True)
        font.setPixelSize(16)
        font.setFamily(self.display_font_family)
        painter.setFont(font)
        painter.drawText(settings_button_rect, Qt.AlignCenter, "Settings")
        painter.restore()

    def _register_click_regions(self, content_rect: QRectF) -> None:
        self._register_main_click_regions(content_rect)

    def _register_main_click_regions(self, content_rect: QRectF) -> None:
        menu_rects = self._menu_item_rects(content_rect)
        if self.current_screen == "main" and self.hovered_menu_index >= 0:
            edit_rect = self._menu_edit_rect(content_rect, self.hovered_menu_index).intersected(self._menu_view_rect(content_rect))
            if not edit_rect.isEmpty():
                self.click_regions.append(("menu_edit", str(self.hovered_menu_index), edit_rect))
        view_rect = self._menu_view_rect(content_rect)
        for index, rect in enumerate(menu_rects):
            clipped_rect = rect.intersected(view_rect)
            if not clipped_rect.isEmpty():
                self.click_regions.append(("menu", str(index), clipped_rect))

        play_rect = self._ppt_rect(content_rect, 5620000, 6075000, 2824891, 653256)
        self.click_regions.append(("play", "main", play_rect))
        add_server_rect = self._ppt_rect(content_rect, 420000, 6115000, 1700000, 500000)
        settings_rect = self._ppt_rect(content_rect, 420000, 6635000, 1700000, 500000)
        self.click_regions.append(("add_server", "main", add_server_rect))
        self.click_regions.append(("settings", "main", settings_rect))
        self.click_regions.append(("external_url", "https://www.reddit.com/r/freerealms/", self._header_reddit_rect(content_rect)))
        self.click_regions.append(("external_url", "https://discord.gg/x7Xfz99Ydv", self._header_discord_rect(content_rect)))

    def _draw_selection_overlay(self, painter: QPainter, content_rect: QRectF) -> None:
        menu_rects = self._menu_item_rects(content_rect)
        if not menu_rects:
            return
        highlight_index = min(max(self.menu_highlight_index, 0.0), len(menu_rects) - 1.0)
        base_index = int(highlight_index)
        next_index = min(base_index + 1, len(menu_rects) - 1)
        blend = highlight_index - base_index
        base_rect = menu_rects[base_index]
        next_rect = menu_rects[next_index]
        animated_rect = QRectF(
            base_rect.x(),
            base_rect.y() + ((next_rect.y() - base_rect.y()) * blend),
            base_rect.width(),
            base_rect.height(),
        )
        painter.save()
        painter.setClipRect(self._menu_view_rect(content_rect))
        painter.fillRect(animated_rect, QColor(255, 255, 255, 10))
        painter.restore()

    def _draw_username_overlay(self, painter: QPainter, content_rect: QRectF) -> None:
        return
