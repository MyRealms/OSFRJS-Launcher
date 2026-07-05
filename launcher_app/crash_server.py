"""Tiny embedded HTTP server that acts as the local ``GameCrashUrl`` target.

When the Free Realms client crashes with an ``Error# G<n>`` it
``ShellExecute``s ``GameCrashUrl`` in the default browser. We point that
URL at a small page served from this in-process server so the browser
window that pops up is always a known-good, local, minimal banner
(\"Free Realms has crashed. Please return to the OSFR Launcher for the
real error.\") instead of whatever the server pushes at runtime.

Design notes
------------
* The server binds to ``127.0.0.1`` on an ephemeral port (kernel-assigned)
  so it can never collide with another application.
* It runs on a daemon thread; stopping the launcher cleanly tears it
  down via :meth:`CrashServer.stop`.
* It only ever answers on the loopback interface, never on the LAN, so
  the launcher doesn't accidentally open a port on the user's network.
* The HTML page is intentionally tiny (a few hundred bytes) so the
  browser opens and closes instantly.
"""

from __future__ import annotations

import http.server
import logging
import socketserver
import threading
from dataclasses import dataclass

LOGGER = logging.getLogger("osfr_launcher")


# Minimal banner served at every path under the crash server. The user
# is expected to look at the launcher for the real error UI; this page
# is just a graceful "something happened" landing zone.
_CRASH_PAGE_HTML = (
    "<!doctype html>\n"
    "<html lang=\"en\">\n"
    "<head>\n"
    "<meta charset=\"utf-8\">\n"
    "<title>Free Realms has stopped</title>\n"
    "<style>\n"
    "body { font-family: 'Segoe UI', Tahoma, sans-serif; background: #1b1d23;\n"
    "       color: #e6e6e6; margin: 0; padding: 4rem 1.5rem; text-align: center; }\n"
    "h1 { font-weight: 400; font-size: 1.6rem; margin-bottom: 0.5rem; }\n"
    "p { font-size: 1rem; color: #b6b6b6; max-width: 36rem; margin: 0.4rem auto; }\n"
    ".hint { margin-top: 2rem; font-size: 0.9rem; color: #8a8a8a; }\n"
    "</style>\n"
    "</head>\n"
    "<body>\n"
    "<h1>Free Realms has stopped responding.</h1>\n"
    "<p>The actual error and suggested fixes are shown in the OSFR Launcher window.</p>\n"
    "<p class=\"hint\">You can safely close this browser tab.</p>\n"
    "</body>\n"
    "</html>\n"
).encode("utf-8")


class _CrashServerHandler(http.server.BaseHTTPRequestHandler):
    """Trivial handler: every GET returns the minimal crash banner."""

    # Silence the default per-request stderr access log; the launcher
    # has its own logging pipeline.
    def log_message(self, format: str, *args) -> None:  # noqa: A002
        LOGGER.debug("CrashServer %s - %s", self.address_string(), format % args)

    def do_GET(self) -> None:  # noqa: N802
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(_CRASH_PAGE_HTML)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("Connection", "close")
        self.end_headers()
        try:
            self.wfile.write(_CRASH_PAGE_HTML)
        except (BrokenPipeError, ConnectionResetError):
            # User closed the tab before the body finished flushing.
            pass


class _ThreadingHTTPServer(socketserver.ThreadingMixIn, http.server.HTTPServer):
    """Threaded HTTP server so a slow client can't stall the next request.

    ``daemon_threads`` lets the launcher exit even if a request is
    still being served; the OS will reap the thread on shutdown.
    """

    daemon_threads = True
    allow_reuse_address = False  # ephemeral port; never share it


@dataclass(slots=True)
class CrashServer:
    """In-process HTTP server that owns the local ``GameCrashUrl`` target.

    Use :meth:`start` once on launcher boot and :meth:`stop` on shutdown.
    :attr:`url` is populated by :meth:`start` and is the full URL the
    client config should be rewritten to point at.
    """

    host: str = "127.0.0.1"
    url: str = ""
    _server: _ThreadingHTTPServer | None = None
    _thread: threading.Thread | None = None

    def start(self) -> str:
        """Bind the server and spawn its daemon thread. Returns the URL."""
        if self._server is not None:
            return self.url
        server = _ThreadingHTTPServer((self.host, 0), _CrashServerHandler)
        # ``server_address[1]`` is the kernel-assigned ephemeral port.
        port = int(server.server_address[1])
        self._server = server
        self.url = f"http://{self.host}:{port}/crash"
        thread = threading.Thread(
            target=server.serve_forever,
            name="osfr-crash-server",
            daemon=True,
        )
        self._thread = thread
        thread.start()
        LOGGER.info("CrashServer listening on %s", self.url)
        return self.url

    def stop(self) -> None:
        if self._server is None:
            return
        try:
            self._server.shutdown()
            self._server.server_close()
        except Exception:  # noqa: BLE001
            LOGGER.exception("CrashServer stop failed")
        finally:
            self._server = None
            self._thread = None
            self.url = ""
            LOGGER.info("CrashServer stopped")

    @property
    def is_running(self) -> bool:
        return self._server is not None
