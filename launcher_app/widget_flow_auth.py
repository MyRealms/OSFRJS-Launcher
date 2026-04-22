from __future__ import annotations

import requests

from .constants import HTTP_TIMEOUT
from .models import LauncherError, LoginResult, ServerManifest, ServerProfile
from .utils import join_url


class LauncherWidgetAuthFlowMixin:
    def _login(self, profile: ServerProfile, server_manifest: ServerManifest, username: str, password: str) -> LoginResult:
        login_url = profile.login_api_url.strip()
        if login_url.startswith("/"):
            login_url = join_url(profile.server_url, login_url.lstrip("/"))
        if not login_url:
            login_url = join_url(server_manifest.web_api_url, "login")
        if not login_url:
            raise LauncherError("Login API URL could not be resolved for this server.")
        response = requests.post(
            login_url,
            json={
                "username": username,
                "password": password,
                "Username": username,
                "Password": password,
            },
            timeout=HTTP_TIMEOUT,
        )

        if response.status_code == 401:
            raise LauncherError("Login failed. Username or password is incorrect.")
        response.raise_for_status()

        payload = response.json()
        session_id = str(payload.get("SessionId") or payload.get("sessionId") or "").strip()
        if not session_id:
            raise LauncherError("Login succeeded but the server did not return a SessionId.")

        launch_arguments = payload.get("LaunchArguments")
        if launch_arguments is None:
            launch_arguments = payload.get("launchArguments", "")
        return LoginResult(session_id=session_id, launch_arguments=str(launch_arguments or "").strip())
