from __future__ import annotations

from PySide6.QtWidgets import QWidget

from .widget_bootstrap import LauncherWidgetBootstrapMixin
from .widget_events import LauncherWidgetEventsMixin
from .widget_flow import LauncherWidgetFlowMixin
from .widget_render import LauncherWidgetRenderMixin


class LauncherWidget(
    LauncherWidgetEventsMixin,
    LauncherWidgetRenderMixin,
    LauncherWidgetFlowMixin,
    LauncherWidgetBootstrapMixin,
    QWidget,
):
    def __init__(self) -> None:
        super().__init__()
        self._initialize_widget()
