"""
A small web framework built on `http.server`.

Provides just enough to run the site cleanly: pattern-based routing, request
parsing (JSON + form bodies), typed responses, cookie/session handling, static
file serving with ETag caching, a tiny template renderer, and IP rate limiting.
"""

from __future__ import annotations

import html
import json
import mimetypes
import re
import threading
import time
import traceback
import urllib.parse
from datetime import datetime
from http.cookies import SimpleCookie
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any, Callable

from . import auth
from .config import STATIC_DIR, TEMPLATE_DIR, settings

MAX_BODY_BYTES = 256 * 1024  # 256 KB is far more than any of our forms need


# --------------------------------------------------------------------------- #
# Response
# --------------------------------------------------------------------------- #
class Response:
    def __init__(
        self,
        body: bytes | str = b"",
        status: int = 200,
        content_type: str = "text/html; charset=utf-8",
        headers: dict[str, str] | None = None,
    ) -> None:
        self.body = body.encode("utf-8") if isinstance(body, str) else body
        self.status = status
        self.headers: dict[str, str] = {"Content-Type": content_type}
        if headers:
            self.headers.update(headers)
        self.cookies: list[str] = []

    def set_cookie(
        self,
        name: str,
        value: str,
        *,
        max_age: int | None = None,
        http_only: bool = True,
        same_site: str = "Lax",
        path: str = "/",
    ) -> "Response":
        parts = [f"{name}={value}", f"Path={path}", f"SameSite={same_site}"]
        if max_age is not None:
            parts.append(f"Max-Age={max_age}")
        if http_only:
            parts.append("HttpOnly")
        if settings.secure_cookies:
            parts.append("Secure")
        self.cookies.append("; ".join(parts))
        return self

    def delete_cookie(self, name: str, path: str = "/") -> "Response":
        self.cookies.append(f"{name}=; Path={path}; Max-Age=0; SameSite=Lax")
        return self


def json_response(data: Any, status: int = 200, headers: dict | None = None) -> Response:
    return Response(
        json.dumps(data, ensure_ascii=False, default=str),
        status=status,
        content_type="application/json; charset=utf-8",
        headers={"Cache-Control": "no-store", **(headers or {})},
    )


def error_response(message: str, status: int = 400, **extra: Any) -> Response:
    return json_response({"ok": False, "error": message, **extra}, status=status)


def redirect(location: str, status: int = 303) -> Response:
    return Response(b"", status=status, headers={"Location": location})


def html_response(markup: str, status: int = 200) -> Response:
    return Response(
        markup,
        status=status,
        headers={
            # Sensible baseline hardening for a self-hosted app.
            "X-Content-Type-Options": "nosniff",
            "X-Frame-Options": "SAMEORIGIN",
            "Referrer-Policy": "strict-origin-when-cross-origin",
        },
    )


# --------------------------------------------------------------------------- #
# Request
# --------------------------------------------------------------------------- #
class Request:
    def __init__(
        self,
        method: str,
        path: str,
        query: dict[str, list[str]],
        headers: Any,
        body: bytes,
        client_ip: str,
    ) -> None:
        self.method = method
        self.path = path
        self._query = query
        self.headers = headers
        self.body = body
        self.client_ip = client_ip
        self.params: dict[str, str] = {}  # populated from the URL pattern
        self._form: dict[str, list[str]] | None = None
        self._json: Any = None
        self._json_parsed = False
        self._session: dict | None = None
        self._session_loaded = False

    # -- query string -------------------------------------------------------
    def get(self, key: str, default: str = "") -> str:
        values = self._query.get(key)
        return values[0].strip() if values else default

    def get_int(self, key: str, default: int = 0) -> int:
        try:
            return int(self.get(key, str(default)))
        except ValueError:
            return default

    @property
    def query(self) -> dict[str, str]:
        return {k: v[0] for k, v in self._query.items() if v}

    # -- body ---------------------------------------------------------------
    @property
    def content_type(self) -> str:
        return (self.headers.get("Content-Type") or "").lower()

    def json(self) -> Any:
        if not self._json_parsed:
            self._json_parsed = True
            try:
                self._json = json.loads(self.body.decode("utf-8")) if self.body else None
            except (json.JSONDecodeError, UnicodeDecodeError):
                self._json = None
        return self._json

    @property
    def form(self) -> dict[str, list[str]]:
        if self._form is None:
            try:
                self._form = urllib.parse.parse_qs(
                    self.body.decode("utf-8"), keep_blank_values=True
                )
            except UnicodeDecodeError:
                self._form = {}
        return self._form

    def field(self, key: str, default: str = "") -> str:
        """Read a field from a JSON body or a urlencoded form, whichever it is."""
        if "application/json" in self.content_type:
            payload = self.json()
            if isinstance(payload, dict):
                value = payload.get(key, default)
                if isinstance(value, bool):
                    return "true" if value else ""
                return "" if value is None else str(value)
            return default
        values = self.form.get(key)
        return values[0] if values else default

    def payload(self) -> dict[str, Any]:
        """Whole body as a dict, regardless of encoding."""
        if "application/json" in self.content_type:
            data = self.json()
            return data if isinstance(data, dict) else {}
        return {k: (v[0] if v else "") for k, v in self.form.items()}

    # -- cookies & session --------------------------------------------------
    @property
    def cookies(self) -> dict[str, str]:
        jar = SimpleCookie()
        raw = self.headers.get("Cookie")
        if raw:
            try:
                jar.load(raw)
            except Exception:  # noqa: BLE001 - malformed cookie headers happen
                return {}
        return {key: morsel.value for key, morsel in jar.items()}

    @property
    def session(self) -> dict | None:
        if not self._session_loaded:
            self._session_loaded = True
            token = self.cookies.get(auth.SESSION_COOKIE, "")
            self._session = auth.get_session_user(token) if token else None
        return self._session

    @property
    def user(self) -> dict | None:
        return self.session

    def wants_json(self) -> bool:
        accept = (self.headers.get("Accept") or "").lower()
        return (
            "application/json" in accept
            or "application/json" in self.content_type
            or self.headers.get("X-Requested-With") == "fetch"
        )


# --------------------------------------------------------------------------- #
# Router
# --------------------------------------------------------------------------- #
Handler = Callable[[Request], Response]


class Router:
    def __init__(self) -> None:
        self._routes: list[tuple[str, re.Pattern[str], Handler]] = []

    def add(self, method: str, pattern: str, handler: Handler) -> None:
        """Register a route. `<name>` in the pattern captures a path segment."""
        regex = re.sub(r"<(\w+)>", r"(?P<\1>[^/]+)", pattern)
        self._routes.append(
            (method.upper(), re.compile(f"^{regex}/?$"), handler)
        )

    def route(self, method: str, pattern: str) -> Callable[[Handler], Handler]:
        def decorator(handler: Handler) -> Handler:
            self.add(method, pattern, handler)
            return handler

        return decorator

    def get(self, pattern: str) -> Callable[[Handler], Handler]:
        return self.route("GET", pattern)

    def post(self, pattern: str) -> Callable[[Handler], Handler]:
        return self.route("POST", pattern)

    def resolve(
        self, method: str, path: str
    ) -> tuple[Handler | None, dict[str, str], bool]:
        """Return (handler, path_params, path_exists_for_other_method)."""
        path_matched = False
        for route_method, regex, handler in self._routes:
            match = regex.match(path)
            if not match:
                continue
            path_matched = True
            if route_method == method:
                return handler, match.groupdict(), True
        return None, {}, path_matched


# --------------------------------------------------------------------------- #
# Templating
# --------------------------------------------------------------------------- #
_template_cache: dict[str, str] = {}
_template_lock = threading.Lock()


def load_template(name: str) -> str:
    """Read a template, caching it unless DEBUG (so edits show up live)."""
    if not settings.debug:
        with _template_lock:
            if name in _template_cache:
                return _template_cache[name]
    path = TEMPLATE_DIR / name
    if not path.is_file():
        raise FileNotFoundError(f"Template not found: {name}")
    content = path.read_text(encoding="utf-8")
    if not settings.debug:
        with _template_lock:
            _template_cache[name] = content
    return content


def render(name: str, **context: Any) -> str:
    """
    Substitute `{{ key }}` placeholders.

    Values are HTML-escaped by default. Prefix a key with `raw_` (and reference
    it as `{{ raw_key }}`) to inject trusted pre-built markup such as JSON that
    has already been serialised for a <script> tag.
    """
    template = load_template(name)

    def replace(match: re.Match[str]) -> str:
        key = match.group(1).strip()
        if key not in context:
            return match.group(0)
        value = context[key]
        if key.startswith("raw_"):
            return str(value)
        return html.escape("" if value is None else str(value), quote=True)

    return re.sub(r"\{\{\s*([\w.]+)\s*\}\}", replace, template)


def json_for_script(data: Any) -> str:
    """Serialise data for embedding inside a <script> tag safely."""
    encoded = json.dumps(data, ensure_ascii=False, default=str)
    # Prevent an embedded "</script>" or HTML comment from breaking out.
    return (
        encoded.replace("<", "\\u003c").replace(">", "\\u003e").replace("&", "\\u0026")
    )


# --------------------------------------------------------------------------- #
# Rate limiting
# --------------------------------------------------------------------------- #
class RateLimiter:
    """Fixed-window in-memory limiter, keyed by IP + bucket name."""

    def __init__(self, max_hits: int, window_seconds: int) -> None:
        self.max_hits = max_hits
        self.window = window_seconds
        self._hits: dict[str, list[float]] = {}
        self._lock = threading.Lock()

    def check(self, key: str, *, cost: int = 1) -> tuple[bool, int]:
        """Return (allowed, seconds_until_reset)."""
        now = time.time()
        with self._lock:
            timestamps = [t for t in self._hits.get(key, []) if now - t < self.window]
            if len(timestamps) + cost > self.max_hits:
                retry_after = int(self.window - (now - timestamps[0])) + 1
                self._hits[key] = timestamps
                return False, max(retry_after, 1)
            timestamps.extend([now] * cost)
            self._hits[key] = timestamps
            if len(self._hits) > 4096:  # crude cap to bound memory
                self._prune(now)
            return True, 0

    def _prune(self, now: float) -> None:
        for key in list(self._hits):
            self._hits[key] = [t for t in self._hits[key] if now - t < self.window]
            if not self._hits[key]:
                del self._hits[key]


submission_limiter = RateLimiter(
    settings.rate_limit_max, settings.rate_limit_window_seconds
)
login_limiter = RateLimiter(8, 600)


# --------------------------------------------------------------------------- #
# Static files
# --------------------------------------------------------------------------- #
_LONG_CACHE = {".woff2", ".woff", ".ttf", ".png", ".jpg", ".jpeg", ".webp", ".svg", ".ico"}


def serve_static(request: Request, url_path: str) -> Response:
    relative = url_path.lstrip("/")
    # Resolve and confirm the result stays inside STATIC_DIR (traversal guard).
    try:
        target = (STATIC_DIR / relative).resolve()
        target.relative_to(STATIC_DIR.resolve())
    except (ValueError, OSError):
        return Response("Not found", status=404, content_type="text/plain")
    if not target.is_file():
        return Response("Not found", status=404, content_type="text/plain")

    stat = target.stat()
    etag = f'W/"{int(stat.st_mtime)}-{stat.st_size}"'
    if request.headers.get("If-None-Match") == etag:
        return Response(b"", status=304, headers={"ETag": etag})

    content_type, _ = mimetypes.guess_type(str(target))
    if content_type is None:
        content_type = "application/octet-stream"
    if content_type.startswith("text/") or content_type in {
        "application/javascript",
        "application/json",
    }:
        content_type += "; charset=utf-8"

    max_age = 604800 if target.suffix.lower() in _LONG_CACHE else 3600
    cache_control = "no-cache" if settings.debug else f"public, max-age={max_age}"

    return Response(
        target.read_bytes(),
        content_type=content_type,
        headers={
            "ETag": etag,
            "Cache-Control": cache_control,
            "X-Content-Type-Options": "nosniff",
        },
    )


# --------------------------------------------------------------------------- #
# HTTP server glue
# --------------------------------------------------------------------------- #
class Application:
    def __init__(self) -> None:
        self.router = Router()
        self.error_page: Callable[[Request, int, str], Response] | None = None

    def handle(self, request: Request) -> Response:
        # Static assets first -- cheapest and most frequent.
        if request.path.startswith("/static/"):
            return serve_static(request, request.path[len("/static/") :])
        if request.path in {"/favicon.ico", "/robots.txt", "/sitemap.xml"}:
            direct = serve_static(request, request.path.lstrip("/"))
            if direct.status == 200:
                return direct

        handler, params, path_exists = self.router.resolve(request.method, request.path)
        if handler is None:
            status = 405 if path_exists else 404
            message = (
                "Method not allowed" if status == 405 else "That page does not exist."
            )
            if request.wants_json() or request.path.startswith("/api/"):
                return error_response(message, status)
            if self.error_page:
                return self.error_page(request, status, message)
            return Response(message, status=status, content_type="text/plain")

        request.params = params
        try:
            return handler(request)
        except Exception:  # noqa: BLE001 - convert any handler crash into a 500
            traceback.print_exc()
            if request.wants_json() or request.path.startswith("/api/"):
                detail = (
                    traceback.format_exc().splitlines()[-1]
                    if settings.debug
                    else "Internal server error"
                )
                return error_response(detail, 500)
            if self.error_page:
                return self.error_page(
                    request, 500, "Something went wrong on our side."
                )
            return Response("Internal server error", status=500, content_type="text/plain")


def make_handler(app: Application) -> type[BaseHTTPRequestHandler]:
    class RequestHandler(BaseHTTPRequestHandler):
        server_version = f"{settings.brand_name.replace(' ', '')}/1.0"
        sys_version = ""
        protocol_version = "HTTP/1.1"

        # -- plumbing -------------------------------------------------------
        def _client_ip(self) -> str:
            forwarded = self.headers.get("X-Forwarded-For")
            if forwarded:
                return forwarded.split(",")[0].strip()
            return self.client_address[0] if self.client_address else ""

        def _read_body(self) -> bytes | None:
            try:
                length = int(self.headers.get("Content-Length") or 0)
            except ValueError:
                return b""
            if length <= 0:
                return b""
            if length > MAX_BODY_BYTES:
                return None
            return self.rfile.read(length)

        def _dispatch(self, method: str) -> None:
            parsed = urllib.parse.urlsplit(self.path)
            path = urllib.parse.unquote(parsed.path) or "/"
            if len(path) > 1 and path.endswith("/"):
                path = path.rstrip("/") or "/"
            query = urllib.parse.parse_qs(parsed.query, keep_blank_values=True)

            body = self._read_body() if method in {"POST", "PUT", "PATCH"} else b""
            if body is None:
                self._send(error_response("Request body too large.", 413))
                return

            request = Request(
                method, path, query, self.headers, body, self._client_ip()
            )
            response = app.handle(request)
            self._send(response, head_only=(method == "HEAD"))

        def _send(self, response: Response, head_only: bool = False) -> None:
            body = b"" if head_only else response.body
            try:
                self.send_response(response.status)
                for key, value in response.headers.items():
                    self.send_header(key, value)
                for cookie in response.cookies:
                    self.send_header("Set-Cookie", cookie)
                if response.status not in {204, 304}:
                    self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                if body:
                    self.wfile.write(body)
            except (BrokenPipeError, ConnectionResetError):
                pass  # client went away mid-response

        # -- verbs ----------------------------------------------------------
        def do_GET(self) -> None:  # noqa: N802
            self._dispatch("GET")

        def do_HEAD(self) -> None:  # noqa: N802
            self._dispatch("HEAD")

        def do_POST(self) -> None:  # noqa: N802
            self._dispatch("POST")

        # -- logging --------------------------------------------------------
        def log_message(self, fmt: str, *args: Any) -> None:
            stamp = datetime.now().strftime("%H:%M:%S")
            print(f"[{stamp}] {self._client_ip()} {fmt % args}")

        def log_error(self, fmt: str, *args: Any) -> None:
            if settings.debug:
                self.log_message(fmt, *args)

    return RequestHandler


def run_server(app: Application) -> None:
    handler = make_handler(app)
    httpd = ThreadingHTTPServer((settings.host, settings.port), handler)
    httpd.daemon_threads = True

    shown_host = "localhost" if settings.host in {"0.0.0.0", ""} else settings.host
    print("=" * 66)
    print(f"  {settings.brand_name} — booking platform")
    print("=" * 66)
    print(f"  Website    http://{shown_host}:{settings.port}/")
    print(f"  Dashboard  http://{shown_host}:{settings.port}/admin")
    mail_mode = (
        f"SMTP via {settings.smtp_host}:{settings.smtp_port}"
        if settings.smtp_configured
        else "offline — writing .eml files to data/outbox/"
    )
    print(f"  Email      {mail_mode}")
    print(f"  Database   {settings.db_path}")
    print(f"  Debug      {settings.debug}")
    print("=" * 66)
    print("  Ctrl+C to stop\n")

    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down…")
    finally:
        httpd.server_close()
