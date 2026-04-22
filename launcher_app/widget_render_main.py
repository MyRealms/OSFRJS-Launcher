from __future__ import annotations

from .widget_render_content import LauncherWidgetRenderContentMixin
from .widget_render_frame import LauncherWidgetRenderFrameMixin
from .widget_render_navigation import LauncherWidgetRenderNavigationMixin


class LauncherWidgetRenderMainMixin(
    LauncherWidgetRenderContentMixin,
    LauncherWidgetRenderNavigationMixin,
    LauncherWidgetRenderFrameMixin,
):
    pass
