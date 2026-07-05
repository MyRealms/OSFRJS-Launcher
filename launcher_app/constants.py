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

# DirectX 9 redistributable (June 2010) web installer. Silent install supported via /Q.
DIRECTX9_REDIST_URL = "https://download.microsoft.com/download/1/7/1/1718CCC4-6315-4D8E-9543-8E28A4E18C4C/dxwebsetup.exe"

# Node.js portable distribution, installed on demand for the AuthBridge.
NODE_VERSION = "v20.18.0"
NODE_DOWNLOAD_URL_WINDOWS = "https://nodejs.org/dist/v20.18.0/node-v20.18.0-win-x64.zip"
NODE_DOWNLOAD_URL_LINUX = "https://nodejs.org/dist/v20.18.0/node-v20.18.0-linux-x64.tar.xz"
NODE_DOWNLOAD_URL_OSX = "https://nodejs.org/dist/v20.18.0/node-v20.18.0-darwin-x64.tar.gz"

# Launcher update checking (GitHub releases). Only notifies the user and opens the
# releases page in a browser; it does not auto-download/install updates.
LAUNCHER_VERSION = "1.1.1"
GITHUB_RELEASES_URL = "https://github.com/MyRealms/OSFRJS-Launcher/releases"
GITHUB_LATEST_RELEASE_API_URL = "https://api.github.com/repos/MyRealms/OSFRJS-Launcher/releases/latest"
IS_FROZEN = bool(getattr(sys, "frozen", False))
APP_DIR = Path(sys.executable).resolve().parent if IS_FROZEN else Path(__file__).resolve().parent.parent
RESOURCE_DIR = Path(getattr(sys, "_MEIPASS", APP_DIR))


# ---------------------------------------------------------------------------
# Portable layout (v1.1.1+)
# ---------------------------------------------------------------------------
# The launcher is fully portable: every writable file lives next to the
# launcher binary itself. Drop the folder anywhere (USB stick, external
# drive, custom user dir) and it just works - no AppData, no Program
# Files requirement, no UAC prompts. This is the historical v1.0.0 layout
# restored; the v1.1.0 AppData model is gone.
#
#   <APP_DIR>/
#     FreeRealmsJSLauncher.exe
#     Launcher.xml                <- settings + server list
#     launcher_debug.log
#     local_server/               <- extracted from RESOURCE_DIR on first run
#       Emulator/  AuthBridge/  start_server.bat
#     node/                       <- portable Node.js (downloaded on demand)
#     Client/                     <- default bundled client (next to launcher)
#     Servers/<save_path>/        <- per-profile client + saves
#       Client/  Saves/

USER_DATA_DIR = APP_DIR
SETTINGS_PATH = APP_DIR / "Launcher.xml"
LEGACY_SETTINGS_PATH = APP_DIR / "launcher_settings.json"
LOCAL_SERVER_BUNDLE_DIR = RESOURCE_DIR / "local_server"
LOCAL_SERVER_RUNTIME_DIR = APP_DIR / "local_server"
LOCAL_SERVER_PID_FILE = APP_DIR / "local_server_pids.json"
DEBUG_LOG_PATH = APP_DIR / "launcher_debug.log"
CLIENT_DATA_DIR = APP_DIR / "Client"
SERVERS_ROOT = APP_DIR / "Servers"
SAVE_DATA_DIR = SERVERS_ROOT / "saves"

# Client containers (per-server isolated client copies).
# The "Client" folder is a user-managed stash of client trees. The golden
# (safe, unedited) client lives at ``Client/OSFR - Original``. The launcher
# copies that tree into ``Client/OSFR - <server name>/`` whenever the user
# adds a new server with "Create new client container" enabled, so each
# server gets its own sandboxed client (saves, config, custom assets never
# leak across servers).
CLIENT_STASH_DIR = APP_DIR / "Client"
CLIENT_STASH_ORIGINAL_NAME = "OSFR - Original"
CLIENT_STASH_ORIGINAL_DIR = CLIENT_STASH_DIR / CLIENT_STASH_ORIGINAL_NAME
# Prefix used when the launcher auto-names a new container for a server.
CLIENT_CONTAINER_PREFIX = "OSFR - "
HTTP_TIMEOUT = 30
DOWNLOAD_TIMEOUT = 90
DISCORD_RPC_APP_ID = os.environ.get("OSFR_DISCORD_APP_ID", "1496283833061081168").strip()
DISCORD_RPC_UPDATE_INTERVAL_MS = 15000

# Resources packed inside the launcher binary (icon, font, etc.)
ICON_PATH = RESOURCE_DIR / "launcher.ico"
FONT_PATH = RESOURCE_DIR / "FreeRealms.ttf"


# ---------------------------------------------------------------------------
# Legacy AppData migration (v1.1.0)
# ---------------------------------------------------------------------------
# v1.1.0 stored everything under %LOCALAPPDATA%\OSFR Launcher\ so it would
# not trigger UAC. That model broke portability: the launcher stopped
# working when copied to another machine. v1.1.1 moved back to APP_DIR,
# but users who already ran v1.1.0 have settings, per-profile clients
# and downloaded Node there. We surface those paths so the launcher can
# auto-migrate on first launch instead of silently dropping user data.

def _v110_user_data_root() -> Path | None:
    """Return the v1.1.0 per-user data root, or None if not applicable."""
    if sys.platform == "win32":
        base = os.environ.get("LOCALAPPDATA")
        if not base:
            return None
        return Path(base) / "OSFR Launcher"
    if sys.platform == "darwin":
        return Path.home() / "Library" / "Application Support" / "OSFR Launcher"
    base = os.environ.get("XDG_DATA_HOME") or str(Path.home() / ".local" / "share")
    return Path(base) / "OSFR Launcher"


LEGACY_V110_USER_DATA_DIR = _v110_user_data_root()
LEGACY_V110_SETTINGS_PATH = (
    LEGACY_V110_USER_DATA_DIR / "Launcher.xml" if LEGACY_V110_USER_DATA_DIR else None
)
LEGACY_V110_SERVERS_ROOT = (
    LEGACY_V110_USER_DATA_DIR / "servers" if LEGACY_V110_USER_DATA_DIR else None
)
LEGACY_V110_NODE_DIR = (
    LEGACY_V110_USER_DATA_DIR / "node" if LEGACY_V110_USER_DATA_DIR else None
)
LEGACY_V110_LOCAL_SERVER_DIR = (
    LEGACY_V110_USER_DATA_DIR / "local_server" if LEGACY_V110_USER_DATA_DIR else None
)
