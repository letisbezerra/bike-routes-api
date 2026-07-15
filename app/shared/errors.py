import logging

import sentry_sdk
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from slowapi.errors import RateLimitExceeded
from starlette.exceptions import HTTPException as StarletteHTTPException

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


async def http_exception_handler(request: Request, exc: StarletteHTTPException) -> JSONResponse:
    code = CODE_BY_STATUS.get(exc.status_code, "error")
    return JSONResponse(
        status_code=exc.status_code,
        content={"error": {"code": code, "message": str(exc.detail)}},
        headers=exc.headers,
    )


def rate_limit_exceeded_handler(request: Request, exc: RateLimitExceeded) -> JSONResponse:
    # Must stay a plain (non-async) function: SlowAPIMiddleware intercepts
    # RateLimitExceeded itself, synchronously, before Starlette's own
    # exception dispatch ever runs — it looks up this handler in
    # app.exception_handlers but only calls it directly (no await), falling
    # back to slowapi's own default handler (a bare {"error": "<message>"}
    # string, not this project's {"error": {"code", "message"}} envelope)
    # whenever the registered handler is a coroutine function.
    response = JSONResponse(
        status_code=429,
        content={"error": {"code": "rate_limited", "message": str(exc.detail)}},
    )
    return request.app.state.limiter._inject_headers(response, request.state.view_rate_limit)


async def validation_exception_handler(
    request: Request, exc: RequestValidationError
) -> JSONResponse:
    first = exc.errors()[0]
    location = ".".join(str(part) for part in first["loc"])
    return JSONResponse(
        status_code=422,
        content={"error": {"code": "validation_error", "message": f"{location}: {first['msg']}"}},
    )


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
    response = JSONResponse(
        status_code=500,
        content={"error": {"code": "internal_error", "message": "An unexpected error occurred."}},
    )
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
