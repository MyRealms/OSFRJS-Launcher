from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QColor, QPainter, QPainterPath, QPen, QPixmap
from PySide6.QtSvg import QSvgRenderer

PPT_CX = 11520488
PPT_CY = 7199313


class LauncherWidgetRenderBaseMixin:
    def _stage_progress(self, progress: float, start: float, end: float) -> float:
        if progress <= start:
            return 0.0
        if progress >= end:
            return 1.0
        t = (progress - start) / max(0.0001, end - start)
        return 1.0 - pow(1.0 - t, 3)

    def _draw_window_background(self, painter: QPainter) -> None:
        painter.fillRect(self.rect(), QColor("#1A1A1A"))

    def _ppt_rect(self, content_rect: QRectF, x: float, y: float, w: float, h: float) -> QRectF:
        scale_x = content_rect.width() / PPT_CX
        scale_y = content_rect.height() / PPT_CY
        return QRectF(content_rect.x() + x * scale_x, content_rect.y() + y * scale_y, w * scale_x, h * scale_y)

    def _draw_asset_placeholder(self, painter: QPainter, rect: QRectF, label: str) -> None:
        self._rounded_rect(painter, rect, 8, QColor(255, 255, 255, 12), QColor(255, 255, 255, 44), 1.0)
        painter.save()
        painter.setPen(QColor(233, 221, 199, 170))
        font = painter.font()
        font.setPixelSize(max(10, int(rect.height() * 0.09)))
        painter.setFont(font)
        painter.drawText(rect.adjusted(10, 0, -10, 0), Qt.AlignCenter | Qt.TextWordWrap, label)
        painter.restore()

    def _draw_input_box(self, painter: QPainter, rect: QRectF, text: str) -> None:
        self._rounded_rect(painter, rect, 10, QColor("#1D1D1D"), QColor(255, 255, 255, 52), 1.0)
        painter.save()
        painter.setPen(QColor(230, 230, 230, 220))
        font = painter.font()
        font.setFamily("Trebuchet MS")
        font.setPixelSize(14)
        painter.setFont(font)
        painter.drawText(rect.adjusted(18, 0, -18, 0), Qt.AlignLeft | Qt.AlignVCenter, text)
        painter.restore()

    def _draw_cover_pixmap(self, painter: QPainter, rect: QRectF, pixmap: QPixmap, radius: float = 0.0) -> None:
        if pixmap.isNull():
            return

        painter.save()
        path = QPainterPath()
        if radius > 0:
            path.addRoundedRect(rect, radius, radius)
            painter.setClipPath(path)

        source = QRectF(pixmap.rect())
        pixmap_ratio = pixmap.width() / max(1, pixmap.height())
        target_ratio = rect.width() / max(1.0, rect.height())
        if pixmap_ratio > target_ratio:
            target_width = pixmap.height() * target_ratio
            source.setX((pixmap.width() - target_width) / 2.0)
            source.setWidth(target_width)
        else:
            target_height = pixmap.width() / max(target_ratio, 0.001)
            source.setY((pixmap.height() - target_height) / 2.0)
            source.setHeight(target_height)

        painter.drawPixmap(rect, pixmap, source)
        painter.restore()

    def _draw_contain_pixmap(self, painter: QPainter, rect: QRectF, pixmap: QPixmap) -> None:
        if pixmap.isNull():
            return
        target = pixmap.scaled(rect.size().toSize(), Qt.KeepAspectRatio, Qt.SmoothTransformation)
        draw_rect = QRectF(
            rect.x() + (rect.width() - target.width()) / 2.0,
            rect.y() + (rect.height() - target.height()) / 2.0,
            target.width(),
            target.height(),
        )
        painter.drawPixmap(draw_rect.topLeft(), target)

    def _load_pixmap(self, *paths: Path) -> QPixmap:
        for path in paths:
            if path.exists():
                pixmap = QPixmap(str(path))
                if not pixmap.isNull():
                    return pixmap
        return QPixmap()

    def _load_svg(self, *paths: Path) -> QSvgRenderer | None:
        for path in paths:
            if path.exists():
                renderer = QSvgRenderer(str(path))
                if renderer.isValid():
                    return renderer
        return None

    def _draw_nav_icon(self, painter: QPainter, rect: QRectF, color: QColor) -> None:
        painter.save()
        painter.setPen(Qt.NoPen)
        painter.setBrush(color)
        center_x = rect.center().x()
        center_y = rect.center().y()
        r = rect.width() * 0.17
        painter.drawEllipse(QRectF(center_x - r * 2.1, center_y - r * 0.9, r * 2, r * 2))
        painter.drawEllipse(QRectF(center_x - r, center_y - r * 1.5, r * 2, r * 2))
        painter.drawEllipse(QRectF(center_x + r * 0.1, center_y - r * 0.9, r * 2, r * 2))
        painter.drawRect(QRectF(center_x - r * 0.45, center_y, r * 0.9, r * 1.7))
        painter.restore()

    def _draw_top_icon_slot(self, painter: QPainter, rect: QRectF, pixmap: QPixmap, circular: bool = False) -> None:
        painter.save()
        if circular:
            self._rounded_rect(painter, rect.adjusted(-4, -4, 4, 4), rect.width() / 2, QColor(255, 255, 255, 20))
        else:
            self._rounded_rect(painter, rect.adjusted(-4, -4, 4, 4), 8, QColor(255, 255, 255, 18))
        path = QPainterPath()
        if circular:
            path.addEllipse(rect)
        else:
            path.addRoundedRect(rect, 4, 4)
        painter.setClipPath(path)

        if not pixmap.isNull():
            self._draw_cover_pixmap(painter, rect, pixmap, radius=rect.width() / 2 if circular else 4)
        else:
            painter.fillRect(rect, QColor("#D0D0D0"))
            painter.setClipping(False)
            painter.setPen(QColor("#7A7A7A"))
            painter.drawText(rect, Qt.AlignCenter, "PNG")
            painter.restore()
            return
        painter.restore()

    def _rounded_rect(
        self,
        painter: QPainter,
        rect: QRectF,
        radius: float,
        fill,
        outline: QColor | None = None,
        width: float = 0.0,
    ) -> None:
        path = QPainterPath()
        path.addRoundedRect(rect, radius, radius)
        painter.save()
        painter.setBrush(fill)
        if outline and width > 0:
            painter.setPen(QPen(outline, width))
        else:
            painter.setPen(Qt.NoPen)
        painter.drawPath(path)
        painter.restore()
