import logging

import sentry_sdk
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from slowapi.errors import RateLimitExceeded
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.shared.config import settings
from app.shared.middleware import apply_cors_header, apply_security_headers

logger = logging.getLogger(__name__)

# Public (no leading underscore): also imported by app/shared/openapi.py so
# documented error-code examples can't drift from what handlers actually
# return.
CODE_BY_STATUS = {
    400: "bad_request",
    401: "unauthorized",
    403: "forbidden",
    404: "not_found",
    405: "method_not_allowed",
    409: "conflict",
    422: "validation_error",
    429: "rate_limited",
    500: "internal_error",
}

# Only status codes this app's own code actually raises get a hint — 400/
# 403/405/409 are unused today, and inventing a hint for a case that was
# never decided would be filler, not help.
_HTTP_HINTS = {
    401: "Include an X-API-Key header with a valid key.",
    404: "Check that the id is correct.",
}

_BBOX_HINT = "Example: bbox=-38.63,-3.87,-38.42,-3.69"
_EXTRA_FORBIDDEN_HINT = "See the parameter list at /docs for this endpoint."


def build_error_content(code: str, message: str, hint: str | None = None) -> dict:
    """The one place that builds the `{"error": {...}}` envelope — `hint` is
    omitted entirely (not `null`) when there's nothing useful to add, so
    that omit-when-None behavior can't drift between handlers."""
    error = {"code": code, "message": message}
    if hint is not None:
        error["hint"] = hint
    return {"error": error}


def _friendly_validation_message(error: dict) -> tuple[str, str | None]:
    """One Pydantic error dict -> (friendly message suffix, hint or None).
    Falls back to Pydantic's own `msg` (hint=None) for any `type` not
    listed here, so an unrecognized/future error shape degrades gracefully
    instead of raising or showing nothing."""
    error_type = error["type"]
    ctx = error.get("ctx", {})

    if error_type == "less_than_equal":
        return f"must be {ctx['le']} or less", None
    if error_type == "greater_than_equal":
        return f"must be {ctx['ge']} or greater", None
    if error_type == "int_parsing":
        return "must be a whole number", None
    if error_type in ("enum", "literal_error"):
        return f"must be one of: {ctx['expected']}", None
    if error_type == "extra_forbidden":
        return "this parameter isn't recognized", _EXTRA_FORBIDDEN_HINT
    if error_type == "value_error":
        message = error["msg"].removeprefix("Value error, ")
        hint = _BBOX_HINT if error["loc"][-1] == "bbox" else None
        return message, hint
    return error["msg"], None


async def http_exception_handler(request: Request, exc: StarletteHTTPException) -> JSONResponse:
    code = CODE_BY_STATUS.get(exc.status_code, "error")
    content = build_error_content(code, str(exc.detail), hint=_HTTP_HINTS.get(exc.status_code))
    return JSONResponse(status_code=exc.status_code, content=content, headers=exc.headers)


def rate_limit_exceeded_handler(request: Request, exc: RateLimitExceeded) -> JSONResponse:
    # Must stay a plain (non-async) function: SlowAPIMiddleware intercepts
    # RateLimitExceeded itself, synchronously, before Starlette's own
    # exception dispatch ever runs — it looks up this handler in
    # app.exception_handlers but only calls it directly (no await), falling
    # back to slowapi's own default handler (a bare {"error": "<message>"}
    # string, not this project's {"error": {"code", "message"}} envelope)
    # whenever the registered handler is a coroutine function.
    message = f"Rate limit exceeded ({settings.rate_limit_per_minute} requests per minute)."
    content = build_error_content("rate_limited", message, hint="Wait a moment before retrying.")
    response = JSONResponse(status_code=429, content=content)
    return request.app.state.limiter._inject_headers(response, request.state.view_rate_limit)


async def validation_exception_handler(
    request: Request, exc: RequestValidationError
) -> JSONResponse:
    first = exc.errors()[0]
    location = ".".join(str(part) for part in first["loc"])
    message, hint = _friendly_validation_message(first)
    content = build_error_content("validation_error", f"{location}: {message}", hint=hint)
    return JSONResponse(status_code=422, content=content)


async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    # Full traceback stays server-side only — the client never sees exception
    # details, per docs/ARCHITECTURE.md's "Errors never leak internals."
    # method/path passed as structured fields, not interpolated into the
    # message string, so a crafted path can't inject fake log lines.
    logger.error(
        "Unhandled exception",
        extra={"http_method": request.method, "http_path": request.url.path},
        exc_info=exc,
    )
    # Explicit, not relying on Sentry's Starlette auto-instrumentation: a
    # handler registered for the bare Exception class (this one) means the
    # exception never reaches Starlette as "unhandled", so the automatic
    # capture never fires. A no-op when SENTRY_DSN isn't set.
    sentry_sdk.capture_exception(exc)
    content = build_error_content("internal_error", "An unexpected error occurred.")
    response = JSONResponse(status_code=500, content=content)
    # A handler registered for the bare Exception class runs as Starlette's
    # outermost ServerErrorMiddleware — outside SecurityHeadersMiddleware and
    # CORSMiddleware alike, neither of which gets to run on this path.
    # Applied directly here so a genuinely unhandled exception doesn't ship
    # without them (a missing CORS header here previously turned a real
    # server error into an opaque CORS failure for browser callers instead
    # of the intended JSON error body).
    return apply_cors_header(apply_security_headers(response))


def register_error_handlers(app: FastAPI) -> None:
    app.add_exception_handler(StarletteHTTPException, http_exception_handler)
    app.add_exception_handler(RequestValidationError, validation_exception_handler)
    app.add_exception_handler(RateLimitExceeded, rate_limit_exceeded_handler)
    app.add_exception_handler(Exception, unhandled_exception_handler)
