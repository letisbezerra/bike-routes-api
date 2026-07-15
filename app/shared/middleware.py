from slowapi import Limiter
from slowapi.util import get_remote_address
from starlette.middleware.base import BaseHTTPMiddleware

from app.shared.config import settings

default_limit = f"{settings.rate_limit_per_minute}/minute"
# One shared bucket (see api_scope) across every endpoint, per client — not
# one counter per endpoint. @limiter.limit() would give each decorated
# function its own independent counter, so a client throttled on one
# endpoint could keep hitting the other 9 at the same rate each.
api_scope = "api"
limiter = Limiter(key_func=get_remote_address)


def apply_security_headers(response):
    response.headers["Strict-Transport-Security"] = "max-age=63072000; includeSubDomains"
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    return response


def apply_cors_header(response):
    # Mirrors app/main.py's CORSMiddleware config (allow_origins=["*"], no
    # credentials) — a static "*" is only correct because credentials aren't
    # allowed; if that ever changes, this must echo the request Origin
    # instead. Needed on the same paths as apply_security_headers: a bare
    # Exception handler runs outside CORSMiddleware too.
    response.headers["Access-Control-Allow-Origin"] = "*"
    return response


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        response = await call_next(request)
        return apply_security_headers(response)
