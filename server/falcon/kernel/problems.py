"""RFC 9457 problem details.

Every error leaves the API as ``application/problem+json``::

    {
      "type": "https://falcon.local/problems/not-found",
      "title": "Not found",
      "status": 404,
      "detail": "System 'PAY-GW' does not exist",
      "code": "not_found",
      "errors": [{"field": "name", "message": "..."}]   # validation only
    }

``code`` is the stable machine-readable key the console switches on.
"""
from __future__ import annotations

from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

PROBLEM_BASE = "https://falcon.local/problems/"
MEDIA_TYPE = "application/problem+json"

_TITLES = {
    400: "Bad request",
    401: "Authentication required",
    403: "Not permitted",
    404: "Not found",
    405: "Method not allowed",
    409: "Conflict",
    413: "Payload too large",
    422: "Validation failed",
    423: "Locked",
    429: "Too many requests",
    500: "Internal error",
    503: "Unavailable",
}

_CODES = {
    400: "bad_request",
    401: "unauthenticated",
    403: "forbidden",
    404: "not_found",
    405: "method_not_allowed",
    409: "conflict",
    413: "payload_too_large",
    422: "validation_failed",
    423: "locked",
    429: "rate_limited",
    500: "internal_error",
    503: "unavailable",
}


class Problem(Exception):
    """Raise from any layer to return a problem document."""

    def __init__(
        self,
        status: int,
        detail: str,
        *,
        code: str | None = None,
        title: str | None = None,
        errors: list[dict[str, str]] | None = None,
        headers: dict[str, str] | None = None,
    ) -> None:
        super().__init__(detail)
        self.status = status
        self.detail = detail
        self.code = code or _CODES.get(status, f"http_{status}")
        self.title = title or _TITLES.get(status, "Error")
        self.errors = errors
        self.headers = headers


def not_found(what: str) -> Problem:
    return Problem(404, f"{what} was not found")


def conflict(detail: str, code: str = "conflict") -> Problem:
    return Problem(409, detail, code=code)


def forbidden(detail: str = "You do not have permission to perform this action") -> Problem:
    return Problem(403, detail)


def _document(status: int, code: str, title: str, detail: str, errors=None) -> dict[str, Any]:
    body: dict[str, Any] = {
        "type": PROBLEM_BASE + code.replace("_", "-"),
        "title": title,
        "status": status,
        "detail": detail,
        "code": code,
    }
    if errors:
        body["errors"] = errors
    return body


def _respond(body: dict[str, Any], headers: dict[str, str] | None = None) -> JSONResponse:
    return JSONResponse(body, status_code=body["status"], media_type=MEDIA_TYPE, headers=headers)


def install(app: FastAPI) -> None:
    @app.exception_handler(Problem)
    async def _problem(_: Request, exc: Problem) -> JSONResponse:
        return _respond(_document(exc.status, exc.code, exc.title, exc.detail, exc.errors), exc.headers)

    @app.exception_handler(StarletteHTTPException)
    async def _http(_: Request, exc: StarletteHTTPException) -> JSONResponse:
        status = exc.status_code
        code = _CODES.get(status, f"http_{status}")
        return _respond(
            _document(status, code, _TITLES.get(status, "Error"), str(exc.detail)),
            getattr(exc, "headers", None),
        )

    @app.exception_handler(RequestValidationError)
    async def _validation(_: Request, exc: RequestValidationError) -> JSONResponse:
        errors = []
        for err in exc.errors():
            loc = [str(p) for p in err.get("loc", ()) if p not in ("body", "query", "path")]
            # Never echo the submitted value back: it may be a password.
            message = str(err.get("msg", "Invalid value")).removeprefix("Value error, ")
            errors.append({"field": ".".join(loc) or "request", "message": message})
        detail = errors[0]["message"] if len(errors) == 1 else f"{len(errors)} fields need attention"
        return _respond(_document(422, "validation_failed", "Validation failed", detail, errors))
