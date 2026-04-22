from __future__ import annotations

from .widget_flow_launch import LauncherWidgetLaunchFlowMixin
from .widget_flow_network import LauncherWidgetNetworkFlowMixin
from .widget_flow_setup import LauncherWidgetSetupFlowMixin


class LauncherWidgetFlowMixin(
    LauncherWidgetLaunchFlowMixin,
    LauncherWidgetNetworkFlowMixin,
    LauncherWidgetSetupFlowMixin,
):
    pass
