from __future__ import annotations

from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QColor, QLinearGradient, QPainter


class LauncherWidgetRenderContentMixin:
    def _draw_hero_panel(self, painter: QPainter, content_rect: QRectF) -> None:
        hero_rect = self._ppt_rect(content_rect, 2558618, 1091350, 8962256, 5016608)
        if self.hero_backgrounds:
            image_pixmap = self.hero_backgrounds[self.hero_background_index]
        else:
            image_pixmap = self.hero_pixmap if not self.hero_pixmap.isNull() else self.background_pixmap
        if not image_pixmap.isNull():
            painter.save()
            self._draw_cover_pixmap(painter, hero_rect, image_pixmap)
            painter.fillRect(hero_rect, QColor(0, 0, 0, 56))
            self._rounded_rect(painter, hero_rect.adjusted(0.5, 0.5, -0.5, -0.5), 0, QColor(0, 0, 0, 0), QColor(255, 255, 255, 46), 1.0)
            painter.restore()
        else:
            self._draw_asset_placeholder(painter, hero_rect, "Main Background PNG Slot")

        logo_rect = self._ppt_rect(content_rect, 4893076, 1258120, 4292568, 1345334)
        if not self.logo_pixmap.isNull():
            self._draw_contain_pixmap(painter, logo_rect, self.logo_pixmap)
        else:
            self._draw_asset_placeholder(painter, logo_rect, "Logo PNG Slot")

    def _draw_action_panel(self, painter: QPainter, content_rect: QRectF) -> None:
        panel_rect = self._ppt_rect(content_rect, 5620000, 6075000, 2824891, 653256)
        game_running = self._is_game_running()
        intro_progress = min(1.0, max(0.0, self.main_intro_tick / 42.0))
        play_progress = self._stage_progress(intro_progress, 0.40, 0.84)
        if play_progress < 1.0:
            settle_offset = max(0.0, (1.0 - play_progress)) * (content_rect.height() * 0.08)
            panel_rect.translate(0.0, settle_offset)
        if self.play_press_pending and not game_running:
            press_progress = min(1.0, self.play_press_tick / 12.0)
            panel_rect.translate(0.0, content_rect.height() * 0.05 * press_progress)
        painter.save()
        painter.setOpacity(0.12 + (play_progress * 0.88))
        if not game_running and self.play_button_svg and self.play_button_svg.isValid():
            self.play_button_svg.render(painter, panel_rect)
        else:
            shadow_rect = panel_rect.adjusted(0, 7, 0, 7)
            shadow_color = QColor(112, 31, 31, 255) if game_running else QColor(42, 92, 35, 255)
            self._rounded_rect(painter, shadow_rect, 22, shadow_color)
            panel_gradient = QLinearGradient(panel_rect.topLeft(), panel_rect.bottomLeft())
            if game_running:
                panel_gradient.setColorAt(0.0, QColor("#D85D5D"))
                panel_gradient.setColorAt(1.0, QColor("#A13333"))
            else:
                panel_gradient.setColorAt(0.0, QColor("#9AC55A"))
                panel_gradient.setColorAt(1.0, QColor("#6B9E41"))
            self._rounded_rect(painter, panel_rect, 22, panel_gradient, QColor(216, 245, 178, 140), 1.0)

        painter.save()
        painter.setPen(QColor("#FFFFFF"))
        font = painter.font()
        font.setFamily(self.display_font_family)
        font.setBold(True)
        font.setPixelSize(30)
        painter.setFont(font)
        painter.drawText(panel_rect, Qt.AlignCenter, "Stop Game" if game_running else "Play")
        painter.restore()

        info_line = self.server_status_message.strip() or "Status: Unknown"
        info_rect = QRectF(
            panel_rect.x() - (content_rect.width() * 0.03),
            panel_rect.bottom() + (content_rect.height() * 0.006),
            panel_rect.width() + (content_rect.width() * 0.06),
            content_rect.height() * 0.05,
        )

        painter.save()
        painter.setPen(QColor("#F2F5F0"))
        font = painter.font()
        font.setFamily(self.display_font_family)
        font.setBold(True)
        font.setPixelSize(15)
        painter.setFont(font)
        painter.drawText(
            info_rect,
            Qt.AlignHCenter | Qt.AlignVCenter,
            info_line,
        )
        painter.restore()
