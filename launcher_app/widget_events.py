from __future__ import annotations

from PySide6.QtCore import QRectF, QTimer
from PySide6.QtGui import QPainter

from .widget_render import PPT_CX, PPT_CY


class LauncherWidgetEventsMixin:
    def _content_rect(self) -> QRectF:
        width = float(self.width())
        height = float(self.height())
        scale = min(width / PPT_CX, height / PPT_CY)
        content_width = PPT_CX * scale
        content_height = PPT_CY * scale
        offset_x = (width - content_width) / 2.0
        offset_y = (height - content_height) / 2.0
        return QRectF(offset_x, offset_y, content_width, content_height)

    def _paint_current_screen(self, painter: QPainter, content_rect: QRectF) -> None:
        self.click_regions = []
        self._draw_window_background(painter)
        if self.current_screen == "loading":
            self._draw_loading_screen(painter, content_rect)
        elif self.current_screen == "status":
            self._draw_status_screen(painter, content_rect)
        elif self.current_screen == "setup":
            self._draw_setup_screen(painter, content_rect, settings_mode=False)
            self._register_setup_click_regions(content_rect, settings_mode=False)
        elif self.current_screen == "settings":
            self._draw_setup_screen(painter, content_rect, settings_mode=True)
            self._register_setup_click_regions(content_rect, settings_mode=True)
        else:
            self._draw_main_screen(painter, content_rect)
            self._register_main_click_regions(content_rect)
        self._draw_overlay(painter, content_rect)
        self._register_overlay_click_regions(content_rect)
        self._sync_setup_widgets(content_rect)
        self._sync_overlay_widgets(content_rect)

    def _handle_click_region(self, region_type: str, payload: str) -> bool:
        if region_type == "menu":
            self.selected_menu = int(payload)
            self.menu_highlight_target = float(self.selected_menu)
            self.update()
        elif region_type == "play":
            self._queue_play_flow()
        elif region_type == "settings":
            self._open_settings_dialog()
        elif region_type == "add_server":
            self._open_add_server_overlay()
        elif region_type == "menu_edit":
            self._open_server_manage_overlay(int(payload))
        elif region_type == "setup_field":
            self._edit_setup_field(payload)
        elif region_type == "setup_browse":
            self._browse_for_game_path()
        elif region_type == "setup_submit":
            self._submit_setup_form(settings_mode=payload == "settings")
        elif region_type == "setup_reset":
            self._reset_launcher_settings()
        elif region_type == "overlay_submit":
            self._submit_overlay()
        elif region_type == "overlay_cancel":
            self._close_overlay()
        elif region_type == "overlay_alt":
            self._submit_overlay_alt()
        elif region_type == "overlay_toggle":
            self._toggle_overlay_flag(payload)
        elif region_type == "overlay_link":
            self._open_overlay_link()
        elif region_type == "external_url":
            import webbrowser

            webbrowser.open(payload)
        elif region_type == "overlay_focus":
            self._focus_overlay_widget(payload)
        elif region_type == "back_to_main":
            self.current_screen = "main"
            self.selected_menu = min(self.selected_menu, max(0, len(self.settings.all_profiles()) - 1))
            self.menu_highlight_target = float(self.selected_menu)
            self.main_intro_tick = 0
            self.main_outro_tick = 14
            self.settings_transition_pending = False
            self.settings_intro_tick = 14
            self.update()
        else:
            return False
        return True

    def paintEvent(self, event) -> None:  # noqa: N802
        painter = QPainter(self)
        try:
            painter.setRenderHint(QPainter.Antialiasing)
            painter.setRenderHint(QPainter.SmoothPixmapTransform)
            self._paint_current_screen(painter, self._content_rect())
        finally:
            painter.end()

    def showEvent(self, event) -> None:  # noqa: N802
        super().showEvent(event)
        if not self._startup_prompt_done:
            self._startup_prompt_done = True
            self._cleanup_stale_local_server_processes()
            self.current_screen = "loading"
            self.update()
            QTimer.singleShot(900, self._finish_loading_screen)

    def closeEvent(self, event) -> None:  # noqa: N802
        self._shutdown_local_server_processes()
        super().closeEvent(event)

    def mousePressEvent(self, event) -> None:  # noqa: N802
        point = event.position()
        if self.current_screen == "main" and self.overlay_kind is None:
            thumb_rect = self._menu_scrollbar_thumb_rect(self._content_rect())
            if thumb_rect is not None and thumb_rect.contains(point):
                self.menu_scrollbar_dragging = True
                self.menu_scroll_drag_offset = point.y() - thumb_rect.y()
                self.update()
                return
        for region_type, payload, rect in self.click_regions:
            if rect.contains(point):
                if self._handle_click_region(region_type, payload):
                    return
                break
        if self.overlay_kind:
            return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event) -> None:  # noqa: N802
        new_hovered_index = -1
        if self.current_screen == "main" and self.overlay_kind is None:
            point = event.position()
            content_rect = self._content_rect()
            view_rect = self._menu_view_rect(content_rect)
            for index, rect in enumerate(self._menu_item_rects(content_rect)):
                clipped_rect = rect.intersected(view_rect)
                edit_rect = self._menu_edit_rect(content_rect, index).intersected(view_rect)
                if clipped_rect.contains(point) or edit_rect.contains(point):
                    new_hovered_index = index
                    break
        if new_hovered_index != self.hovered_menu_index:
            self.hovered_menu_index = new_hovered_index
            self.update()
        if self.current_screen == "main" and self.overlay_kind is None:
            content_rect = self._content_rect()
            point = event.position()
            list_hovered = self._menu_view_rect(content_rect).contains(point)
            thumb_rect = self._menu_scrollbar_thumb_rect(content_rect)
            scrollbar_hovered = thumb_rect is not None and (
                thumb_rect.contains(point) or self._menu_scrollbar_track_rect(content_rect).contains(point)
            )
            if list_hovered != self.menu_list_hovered or scrollbar_hovered != self.menu_scrollbar_hovered:
                self.menu_list_hovered = list_hovered
                self.menu_scrollbar_hovered = scrollbar_hovered
                self.update()
            if self.menu_scrollbar_dragging and thumb_rect is not None:
                track_rect = self._menu_scrollbar_track_rect(content_rect)
                layout = self._menu_layout(content_rect)
                max_scroll = float(layout["max_scroll"])
                travel = max(1.0, track_rect.height() - thumb_rect.height())
                thumb_y = min(max(track_rect.y(), point.y() - self.menu_scroll_drag_offset), track_rect.bottom() - thumb_rect.height())
                progress = (thumb_y - track_rect.y()) / travel
                self.menu_scroll_offset = max_scroll * progress
                self.update()
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event) -> None:  # noqa: N802
        if self.menu_scrollbar_dragging:
            self.menu_scrollbar_dragging = False
            self.update()
            return
        super().mouseReleaseEvent(event)

    def wheelEvent(self, event) -> None:  # noqa: N802
        if self.current_screen == "main" and self.overlay_kind is None:
            content_rect = self._content_rect()
            if self._menu_view_rect(content_rect).contains(event.position()):
                layout = self._menu_layout(content_rect)
                max_scroll = float(layout["max_scroll"])
                if max_scroll > 0.0:
                    delta_steps = event.angleDelta().y() / 120.0
                    self.menu_scroll_offset = min(max(0.0, self.menu_scroll_offset - (delta_steps * 54.0)), max_scroll)
                    self.update()
                    event.accept()
                    return
        super().wheelEvent(event)
