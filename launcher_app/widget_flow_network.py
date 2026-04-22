from __future__ import annotations

from .widget_flow_auth import LauncherWidgetAuthFlowMixin
from .widget_flow_client_files import LauncherWidgetClientFilesFlowMixin
from .widget_flow_manifest import LauncherWidgetManifestFlowMixin


class LauncherWidgetNetworkFlowMixin(
    LauncherWidgetAuthFlowMixin,
    LauncherWidgetClientFilesFlowMixin,
    LauncherWidgetManifestFlowMixin,
):
    pass
