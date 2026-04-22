from __future__ import annotations

from PySide6.QtCore import QRectF
from PySide6.QtGui import QColor, QPainter

from .widget_render_base import PPT_CY


class LauncherWidgetRenderFrameMixin:
    def _header_reddit_rect(self, content_rect: QRectF) -> QRectF:
        return self._ppt_rect(content_rect, 10091214, 330432, 474483, 474483)

    def _header_discord_rect(self, content_rect: QRectF) -> QRectF:
        return self._ppt_rect(content_rect, 10687231, 330433, 474482, 474482)

    def _draw_main_screen(self, painter: QPainter, content_rect: QRectF) -> None:
        intro_progress = min(1.0, max(0.0, self.main_intro_tick / 42.0))
        sidebar_progress = self._stage_progress(intro_progress, 0.00, 0.42)
        hero_progress = self._stage_progress(intro_progress, 0.12, 0.68)
        outro_progress = self._stage_progress(min(1.0, max(0.0, self.main_outro_tick / 14.0)), 0.0, 1.0) if self.settings_transition_pending else 0.0
        outro_visibility = 1.0 - outro_progress

        sidebar_rect = self._ppt_rect(content_rect, 0, 0, 2558233, PPT_CY)
        sidebar_offset_x = -sidebar_rect.width() * (1.0 - sidebar_progress)
        self._draw_launcher_shell(
            painter,
            content_rect,
            sidebar_offset_x=sidebar_offset_x - (sidebar_rect.width() * 0.10 * outro_progress),
            sidebar_opacity=(0.35 + (sidebar_progress * 0.65)) * (0.18 + (outro_visibility * 0.82)),
        )

        painter.save()
        painter.setOpacity((0.22 + (sidebar_progress * 0.78)) * (0.12 + (outro_visibility * 0.88)))
        painter.translate(sidebar_offset_x - (content_rect.width() * 0.018 * outro_progress), 0.0)
        self._draw_left_navigation(painter, content_rect)
        painter.restore()

        painter.save()
        painter.setOpacity((0.18 + (hero_progress * 0.82)) * (0.10 + (outro_visibility * 0.90)))
        painter.translate(content_rect.width() * (0.11 * (1.0 - hero_progress) - 0.035 * outro_progress), 0.0)
        self._draw_hero_panel(painter, content_rect)
        self._draw_selection_overlay(painter, content_rect)
        painter.restore()

        self._draw_action_panel(painter, content_rect)
        self._draw_header(painter, content_rect)

    def _draw_launcher_shell(
        self,
        painter: QPainter,
        content_rect: QRectF,
        *,
        sidebar_offset_x: float = 0.0,
        sidebar_opacity: float = 1.0,
    ) -> None:
        painter.save()
        sidebar_rect = self._ppt_rect(content_rect, 0, 0, 2558233, PPT_CY)
        topbar_rect = self._ppt_rect(content_rect, 2558233, 0, 8962255, 1091350)
        if self.window_svg and self.window_svg.isValid():
            self.window_svg.render(painter, content_rect)
        else:
            painter.fillRect(content_rect, QColor("#2A2A2A"))
        if not (self.window_svg and self.window_svg.isValid()):
            painter.fillRect(topbar_rect, QColor("#2B2B2B"))

        painter.save()
        painter.translate(sidebar_offset_x, 0.0)
        painter.setOpacity(sidebar_opacity)
        if self.sidebar_svg and self.sidebar_svg.isValid():
            self.sidebar_svg.render(painter, sidebar_rect)
        else:
            painter.fillRect(sidebar_rect, QColor("#1F1F1F"))
        painter.setPen(QColor(255, 255, 255, 18))
        painter.drawLine(sidebar_rect.right(), content_rect.y(), sidebar_rect.right(), content_rect.bottom())
        top_split_y = self._ppt_rect(content_rect, 0, 1091350, 0, 0).y()
        bottom_split_y = self._ppt_rect(content_rect, 0, 6115000, 0, 0).y()
        painter.drawLine(content_rect.x(), top_split_y, sidebar_rect.right(), top_split_y)
        painter.drawLine(content_rect.x(), bottom_split_y, sidebar_rect.right(), bottom_split_y)
        painter.restore()
        painter.restore()

    def _draw_header(self, painter: QPainter, content_rect: QRectF) -> None:
        intro_progress = min(1.0, max(0.0, self.main_intro_tick / 42.0))
        icon_progress = self._stage_progress(intro_progress, 0.76, 1.0)
        painter.save()
        avatar_rect = self._header_reddit_rect(content_rect)
        discord_rect = self._header_discord_rect(content_rect)
        if icon_progress < 1.0:
            painter.setOpacity(0.10 + (icon_progress * 0.90))
            painter.translate(content_rect.width() * 0.035 * (1.0 - icon_progress), -content_rect.height() * 0.012 * (1.0 - icon_progress))
        self._draw_top_icon_slot(painter, avatar_rect, self.avatar_pixmap)
        self._draw_top_icon_slot(painter, discord_rect, self.discord_pixmap, circular=True)
        painter.restore()
