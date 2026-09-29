"""HTTP hardening: request ids, security headers, cache policy, timing."""
from __future__ import annotations

import logging
import secrets
import time

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response

logger = logging.getLogger("falcon.http")

def content_security_policy(desktop: bool) -> str:
    # The desktop shell's IPC channel (native dialogs) is reached through a custom protocol.
    connect = "connect-src 'self' ipc: http://ipc.localhost" if desktop else "connect-src 'self'"
    return "; ".join((
        "default-src 'self'",
        "script-src 'self'",
        "style-src 'self' 'unsafe-inline'",
        "img-src 'self' data: blob:",
        "font-src 'self' data:",
        connect,
        "frame-ancestors 'none'",
        "base-uri 'none'",
        "form-action 'self'",
        "object-src 'none'",
    ))


class HardeningMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, desktop: bool = False) -> None:  # noqa: ANN001 - ASGI app
        super().__init__(app)
        self.csp = content_security_policy(desktop)

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        request_id = request.headers.get("x-request-id") or secrets.token_hex(8)
        request.state.request_id = request_id[:64]
        started = time.perf_counter()
        response = await call_next(request)
        elapsed_ms = (time.perf_counter() - started) * 1000

        headers = response.headers
        headers["X-Request-ID"] = request.state.request_id
        headers["Server-Timing"] = f"app;dur={elapsed_ms:.1f}"
        headers.setdefault("X-Content-Type-Options", "nosniff")
        headers.setdefault("X-Frame-Options", "DENY")
        headers.setdefault("Referrer-Policy", "no-referrer")
        headers.setdefault("Cross-Origin-Opener-Policy", "same-origin")
        headers.setdefault("Cross-Origin-Resource-Policy", "same-origin")
        headers.setdefault("Permissions-Policy", "camera=(), microphone=(), geolocation=(), usb=()")
        if request.url.path.startswith("/api/"):
            headers.setdefault("Cache-Control", "no-store")
        elif not request.url.path.startswith(("/docs", "/redoc")):
            headers.setdefault("Content-Security-Policy", self.csp)
        if request.url.scheme == "https":
            headers.setdefault("Strict-Transport-Security", "max-age=63072000; includeSubDomains")

        if request.url.path.startswith("/api/"):
            logger.info(
                "%s %s -> %s (%.1f ms) rid=%s",
                request.method, request.url.path, response.status_code, elapsed_ms, request.state.request_id,
            )
        return response


def client_ip(request: Request) -> str | None:
    return request.client.host if request.client else None
