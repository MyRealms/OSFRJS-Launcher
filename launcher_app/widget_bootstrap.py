from __future__ import annotations

import subprocess
import time

from PySide6.QtCore import QRectF, QTimer
from PySide6.QtWidgets import QApplication, QLineEdit

from .constants import APP_DIR, MIN_WINDOW_HEIGHT, MIN_WINDOW_WIDTH, RESOURCE_DIR
from .crash_server import CrashServer
from .settings import LauncherSettings


class LauncherWidgetBootstrapMixin:
    def _initialize_widget(self) -> None:
        self._configure_window()
        self._load_widget_assets()
        self._initialize_widget_state()
        self._create_overlay_widgets()
        self._start_animation_timer()
        self._start_crash_server()

    def _configure_window(self) -> None:
        self.setMinimumSize(MIN_WINDOW_WIDTH, MIN_WINDOW_HEIGHT)
        self.setMouseTracking(True)

    def _load_widget_assets(self) -> None:
        media_dir_candidates = [
            RESOURCE_DIR / "pptx_media_extract",
            APP_DIR / "pptx_media_extract",
            APP_DIR.parent / "pptx_media_extract",
        ]
        media_dir = next((path for path in media_dir_candidates if path.exists()), media_dir_candidates[0])
        assets_dir = RESOURCE_DIR / "assets"
        self.background_pixmap = self._load_pixmap(media_dir / "image3.jpg", assets_dir / "snow-village.jpg")
        self.hero_backgrounds = [
            pixmap
            for pixmap in (
                self._load_pixmap(assets_dir / "sanctuary.jpg"),
                self._load_pixmap(assets_dir / "wall1.jpg"),
                self._load_pixmap(assets_dir / "wall2.jpg"),
                self._load_pixmap(assets_dir / "wall3.jpg"),
            )
            if not pixmap.isNull()
        ]
        self.logo_pixmap = self._load_pixmap(
            assets_dir / "OSFRLogo.png",
            media_dir / "image5.png",
            assets_dir / "open-source-freerealms.png",
        )
        self.hero_pixmap = self._load_pixmap(assets_dir / "hero.png")
        self.avatar_pixmap = self._load_pixmap(media_dir / "image10.png", assets_dir / "avatar.png")
        self.discord_pixmap = self._load_pixmap(media_dir / "image9.png", assets_dir / "discord.png")
        self.window_svg = self._load_svg(media_dir / "image1.svg")
        self.sidebar_svg = self._load_svg(media_dir / "image2.svg")
        self.play_button_svg = self._load_svg(media_dir / "image4.svg")
        self.local_icon_svg = self._load_svg(media_dir / "image6.svg")
        self.online_icon_svg = self._load_svg(media_dir / "image7.svg")
        self.browser_icon_svg = self._load_svg(media_dir / "image8.svg")

    def _initialize_widget_state(self) -> None:
        app = QApplication.instance()
        display_font_family = app.property("launcher_display_font_family") if app is not None else None
        self.display_font_family = str(display_font_family).strip() if display_font_family else "Trebuchet MS"
        self.settings = LauncherSettings.load()
        self.selected_menu = 0
        self.menu_highlight_index = 0.0
        self.menu_highlight_target = 0.0
        self.hovered_menu_index = -1
        self.menu_list_hovered = False
        self.menu_scrollbar_hovered = False
        self.menu_scrollbar_dragging = False
        self.menu_scroll_offset = 0.0
        self.menu_scroll_drag_offset = 0.0
        self.current_screen = "loading"
        self.click_regions: list[tuple[str, str, QRectF]] = []
        self.client_process: subprocess.Popen[str] | None = None
        self.local_login_process: subprocess.Popen[str] | None = None
        self.local_gateway_process: subprocess.Popen[str] | None = None
        self.local_webapi_process: subprocess.Popen[str] | None = None
        self.local_authbridge_process: subprocess.Popen[str] | None = None
        self.hash_warning_shown = False
        self._startup_prompt_done = False
        # Set when the user requests cancellation of the current launch/download flow.
        self.launch_cancelled = False
        self.is_launching = False
        # Used to detect a new client crash (G-code) after the game exits.
        self._active_client_dir = None
        self._crash_log_mtime = 0.0
        # Tiny in-process HTTP server that serves the local crash banner.
        # ``GameCrashUrl=`` in the client config is rewritten to point at
        # this so any browser window the client pops on a G error is
        # always the small, local, launcher-branded page.
        self.crash_server = CrashServer()
        self.setup_display_name = self.settings.display_name
        self.setup_game_path = self.settings.game_path
        self.frame_tick = 0
        self.loading_tick = 0
        self.hero_background_index = 0
        self.hero_background_last_switch = time.monotonic()
        self.main_intro_tick = 42
        self.main_outro_tick = 14
        self.settings_transition_pending = False
        self.settings_intro_tick = 14
        self.play_press_tick = 0
        self.play_press_pending = False
        self.game_running_cached = False
        self.game_running_last_probe = 0.0
        self.status_transition_tick = 24
        self.status_title_fade_tick = 0
        self.status_title = "Warming"
        self.status_subtitle = "Preparing launcher"
        self.status_title_animated = True
        self.status_subtitle_animated = True
        self.overlay_kind: str | None = None
        self.overlay_title = ""
        self.overlay_message = ""
        self.overlay_submit_label = "OK"
        self.overlay_cancel_label = "Cancel"
        self.overlay_alt_label = ""
        self.overlay_alt_action = ""
        self.overlay_action = ""
        self.overlay_link_text = ""
        self.overlay_link_url = ""
        self.overlay_intro_tick = 12
        self.overlay_remember_username = False
        self.overlay_remember_password = False
        self.overlay_icon_name = ""
        self.overlay_icon_strip_scroll = 0.0
        self._overlay_snapshot = None
        self.pending_update_url: str | None = None
        self.server_status_profile_key = ""
        self.server_status_name = ""
        self.server_status_description = ""
        self.server_status_online: bool | None = None
        self.server_status_players = 0
        self.server_status_message = "Status: Unknown"
        self.server_status_last_update = 0.0
        self.server_status_refresh_interval = 10.0
        self.server_status_poll_in_flight = False
        self.server_status_pending_result: dict[str, object] | None = None
        self.server_status_last_requested = 0.0
        self.server_status_last_rendered_key = ""
        self.server_status_boot_time = time.monotonic()
        self.scaled_pixmap_cache: dict[tuple[int, int, int, str], object] = {}

    # Frame interval (ms) while animations are actively running vs. idle.
    ANIM_INTERVAL_ACTIVE = 16
    ANIM_INTERVAL_IDLE = 150

    def _start_animation_timer(self) -> None:
        self.anim_timer = QTimer(self)
        self.anim_timer.setInterval(self.ANIM_INTERVAL_ACTIVE)
        self.anim_timer.timeout.connect(self._tick_animation)
        self.anim_timer.start()

    def _start_crash_server(self) -> None:
        """Bind the local crash server before the user clicks Play.

        The server only listens on 127.0.0.1 so it's never exposed to
        the network. If binding fails (port collision, sandbox), the
        launcher keeps working; ``disable_crash_url`` will fall back to
        leaving ``GameCrashUrl=`` untouched and a real browser window
        may pop on a G error.
        """
        try:
            url = self.crash_server.start()
        except OSError:
            self.crash_server = CrashServer()  # discard the broken instance
            return
        # Expose the URL on a simple attribute so the launch flow can
        # read it without going through self.crash_server.url every time.
        self.crash_url = url

    def _wake_animation(self) -> None:
        """Force the animation timer back to full frame rate immediately.

        Call this from interaction handlers that kick off a new animation so it
        starts smoothly instead of waiting out the idle interval.
        """
        timer = getattr(self, "anim_timer", None)
        if timer is not None and timer.interval() != self.ANIM_INTERVAL_ACTIVE:
            timer.setInterval(self.ANIM_INTERVAL_ACTIVE)

    def _create_overlay_widgets(self) -> None:
        self.setup_name_edit = QLineEdit(self)
        self.setup_game_path_edit = QLineEdit(self)
        self.overlay_text_edit = QLineEdit(self)
        self.overlay_server_edit = QLineEdit(self)
        self.overlay_username_edit = QLineEdit(self)
        self.overlay_password_edit = QLineEdit(self)
        self.overlay_password_edit.setEchoMode(QLineEdit.Password)

        for widget in (
            self.setup_name_edit,
            self.setup_game_path_edit,
            self.overlay_text_edit,
            self.overlay_server_edit,
            self.overlay_username_edit,
            self.overlay_password_edit,
        ):
            widget.hide()
            widget.setFrame(False)
            widget.setStyleSheet(
                "QLineEdit {"
                "background: #1d1d1d;"
                "color: #f4f4f4;"
                "border: 1px solid rgba(255,255,255,0.18);"
                "border-radius: 10px;"
                "padding: 0 16px;"
                "selection-background-color: rgba(143,201,93,0.45);"
                "}"
            )
        self.setup_name_edit.setStyleSheet(
            "QLineEdit {"
            "background: transparent;"
            "color: #f4f4f4;"
            "border: 0;"
            "padding: 0 18px;"
            "selection-background-color: rgba(143,201,93,0.45);"
            "}"
        )
        self.setup_game_path_edit.setStyleSheet(self.setup_name_edit.styleSheet())
        self.setup_name_edit.setPlaceholderText("Enter your display name")
        self.setup_game_path_edit.setPlaceholderText("Choose the folder that contains FreeRealms.exe")
        self.setup_name_edit.textChanged.connect(self._on_setup_name_changed)
        self.setup_game_path_edit.textChanged.connect(self._on_setup_game_path_changed)
        self.setup_name_edit.returnPressed.connect(self._submit_active_form_from_keyboard)
        self.setup_game_path_edit.returnPressed.connect(self._submit_active_form_from_keyboard)
        self.overlay_text_edit.returnPressed.connect(self._submit_active_form_from_keyboard)
        self.overlay_server_edit.returnPressed.connect(self._submit_active_form_from_keyboard)
        self.overlay_username_edit.returnPressed.connect(self._submit_active_form_from_keyboard)
        self.overlay_password_edit.returnPressed.connect(self._submit_active_form_from_keyboard)
