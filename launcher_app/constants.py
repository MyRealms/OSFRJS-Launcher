from __future__ import annotations

import os
from pathlib import Path
import sys

BASE_WIDTH = 1194.0
BASE_HEIGHT = 740.0
WINDOW_SCALE = 0.75
DEFAULT_WINDOW_WIDTH = int(1280 * WINDOW_SCALE)
DEFAULT_WINDOW_HEIGHT = int(800 * WINDOW_SCALE)
MIN_WINDOW_WIDTH = int(900 * WINDOW_SCALE)
MIN_WINDOW_HEIGHT = int(560 * WINDOW_SCALE)

CLIENT_EXECUTABLE_NAME = "FreeRealms.exe"
DIRECTX_DOWNLOAD_URL = "https://www.microsoft.com/en-us/download/details.aspx?id=8109"
IS_FROZEN = bool(getattr(sys, "frozen", False))
APP_DIR = Path(sys.executable).resolve().parent if IS_FROZEN else Path(__file__).resolve().parent.parent
RESOURCE_DIR = Path(getattr(sys, "_MEIPASS", APP_DIR))
ICON_PATH = RESOURCE_DIR / "launcher.ico"
FONT_PATH = RESOURCE_DIR / "FreeRealms.ttf"
SETTINGS_PATH = APP_DIR / "Launcher.xml"
LEGACY_SETTINGS_PATH = APP_DIR / "launcher_settings.json"
LOCAL_SERVER_BUNDLE_DIR = RESOURCE_DIR / "local_server"
LOCAL_SERVER_RUNTIME_DIR = RESOURCE_DIR / "local_server" if IS_FROZEN else APP_DIR / "local_server"
LOCAL_SERVER_PID_FILE = APP_DIR / "local_server_pids.json"
HTTP_TIMEOUT = 30
DOWNLOAD_TIMEOUT = 90
DISCORD_RPC_APP_ID = os.environ.get("OSFR_DISCORD_APP_ID", "1496283833061081168").strip()
DISCORD_RPC_UPDATE_INTERVAL_MS = 15000
