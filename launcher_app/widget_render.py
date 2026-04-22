from __future__ import annotations

from .widget_render_base import PPT_CX, PPT_CY, LauncherWidgetRenderBaseMixin
from .widget_render_main import LauncherWidgetRenderMainMixin
from .widget_render_setup import LauncherWidgetRenderSetupMixin


class LauncherWidgetRenderMixin(
    LauncherWidgetRenderSetupMixin,
    LauncherWidgetRenderMainMixin,
    LauncherWidgetRenderBaseMixin,
):
    PPT_CX = PPT_CX
    PPT_CY = PPT_CY
