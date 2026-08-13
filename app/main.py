import logging
from pathlib import Path

import sentry_sdk
from fastapi import APIRouter, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.openapi.docs import get_swagger_ui_html
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from sentry_sdk.scrubber import DEFAULT_DENYLIST, EventScrubber

from app.leisure_routes.router import router as leisure_routes_router
from app.parking.router import router as parking_router
from app.rest_points.router import router as rest_points_router
from app.routes.router import router as routes_router
from app.shared.config import APP_NAME, settings
from app.shared.errors import register_error_handlers
from app.shared.middleware import SecurityHeadersMiddleware, limiter
from app.stations.router import router as stations_router
from app.support_points.router import router as support_points_router

logger = logging.getLogger(__name__)

# Error monitoring only — no tracing/profiling/PII (docs/ARCHITECTURE.md:
# "Sentry catches unhandled exceptions... second priority", distinct from
# the local-only tracing/metrics demo in app/shared/observability.py). A
# no-op when settings.sentry_dsn is unset/None.
#
# include_local_variables=False: Sentry's default event-scrubber only
# redacts sensitively-named keys at the top level of each frame's locals —
# it doesn't recurse into nested dicts, doesn't touch a raw ASGI scope's
# header byte-tuples, and can't catch a secret baked into another object's
# repr() (e.g. verify_api_key's x_api_key parameter surviving inside
# Starlette's functools.partial(...) repr in the run_in_threadpool frame).
# Verified live: with local-variable capture on, a real X-API-Key value
# reached the Sentry event ~28 times through those paths despite the
# key-name scrubber. Turning off local-variable capture entirely removes
# all of them at once, rather than trying to enumerate every leak path.
# Cloudflare/Render sit in front of this app and forward the real client IP
# via CF-Connecting-IP/True-Client-IP — Sentry's own header filter only
# knows the generic WSGI set (Authorization, Cookie, X-Api-Key,
# X-Forwarded-For, ...), not CDN-specific headers, so those two reached a
# real production event in clear text (confirmed live: event 8d89c763,
# 2026-07-15). A custom EventScrubber closes that gap; it runs on top of,
# not instead of, Sentry's own filtering.
sentry_sdk.init(
    dsn=settings.sentry_dsn,
    environment=settings.environment,
    include_local_variables=False,
    event_scrubber=EventScrubber(
        denylist=[*DEFAULT_DENYLIST, "cf-connecting-ip", "true-client-ip"]
    ),
)

app = FastAPI(
    title=APP_NAME,
    description=(
        "Free, public REST API over Fortaleza's open bike infrastructure data "
        "(routes, parking, bike-share stations, rest points). Data source: "
        "AMC/Prefeitura de Fortaleza — see the README for attribution details. "
        "Every endpoint requires an `X-API-Key` header; contact the maintainer "
        "for a key."
    ),
    version="0.1.0",
    # Default /docs replaced below with a themed one (docs/specs/
    # 10-swagger-ui-styling.md) — disabled here so FastAPI doesn't also
    # register its own at the same path.
    docs_url=None,
    contact={
        "name": "Issues & key requests",
        "url": "https://github.com/letisbezerra/bike-routes-api/issues",
    },
    license_info={
        "name": "AGPL-3.0",
        "url": "https://github.com/letisbezerra/bike-routes-api/blob/main/LICENSE",
    },
    openapi_tags=[
        {
            "name": "routes",
            "description": "Bike routes — ciclovias, ciclofaixas, ciclorrotas, passeios "
            "compartilhados.",
        },
        {"name": "parking", "description": "Bike parking spots — paraciclos and bicicletários."},
        {"name": "stations", "description": "Bicicletar bike-share stations."},
        {"name": "rest-points", "description": "Rest points along bike routes."},
        {"name": "leisure-routes", "description": "Leisure cycling routes."},
        {
            "name": "support-points",
            "description": "Combined view of bike parking, bike-share stations, and rest "
            "points — one bbox-filtered call instead of three.",
        },
    ],
)

app.state.limiter = limiter
register_error_handlers(app)

if settings.enable_observability and settings.environment != "production":
    from app.shared.observability import setup_observability

    setup_observability(app)
app.add_middleware(SecurityHeadersMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["GET"],
    allow_headers=["*"],
)

app.mount(
    "/static", StaticFiles(directory=str(Path(__file__).parent / "static")), name="static"
)


@app.get("/", include_in_schema=False)
def root():
    """Bare-domain visitors (e.g. from the README/portfolio link) land on the
    docs instead of a raw 404 — the API itself has no root resource."""
    return RedirectResponse("/docs")


# BikesAPI header + light/dark toggle for the real Swagger UI (docs/specs/
# 10-swagger-ui-styling.md). get_swagger_ui_html() has no hook to inject
# extra markup, so this replaces its single, always-empty
# `<div id="swagger-ui">` placeholder with the header immediately followed
# by that same div — every byte injected is this fixed file's content, no
# request-derived input touches it. The toggle just flips `dark-mode` on
# <html>, the same class swagger-ui.css already keys its own dark rules on.
_SWAGGER_HEADER = (
    (Path(__file__).parent / "templates" / "swagger-header.html").read_text().rstrip()
)
_SWAGGER_UI_PLACEHOLDER = '<div id="swagger-ui">\n    </div>'


_SWAGGER_CSS_PATH = Path(__file__).parent / "static" / "swagger-custom.css"


@app.get("/docs", include_in_schema=False)
def custom_swagger_ui():
    # Cache-busted on the CSS file's own mtime — StaticFiles sets no
    # explicit Cache-Control, so browsers were free to serve a stale copy
    # after every edit, hiding real fixes behind an unprompted hard
    # refresh. Recomputed per request (cheap stat call) so a running dev
    # server always reflects the file as last saved, not as it was when
    # the process started.
    css_version = int(_SWAGGER_CSS_PATH.stat().st_mtime)
    response = get_swagger_ui_html(
        openapi_url=app.openapi_url,
        title=f"{APP_NAME} — Documentation",
        swagger_css_url=f"/static/swagger-custom.css?v={css_version}",
    )
    html = response.body.decode("utf-8")
    if _SWAGGER_UI_PLACEHOLDER not in html:
        # A FastAPI/Starlette version bump changed get_swagger_ui_html()'s
        # generated markup — .replace() below would otherwise silently
        # no-op, dropping the header/theme-toggle with no error and no
        # test to catch it (code-review 2026-08-11). /docs still renders;
        # this just makes the regression loud in the logs instead of only
        # visible on a manual look at the page.
        logger.error(
            "Swagger UI placeholder div not found in generated HTML — "
            "custom header/theme-toggle was not injected into /docs."
        )
    else:
        html = html.replace(_SWAGGER_UI_PLACEHOLDER, _SWAGGER_HEADER)
    # The linked CSS is cache-busted (above), but this HTML document itself
    # had no Cache-Control at all — browsers were free to keep serving an
    # old cached page indefinitely, with no way to tell from the URL alone
    # (unlike the CSS's ?v=) that a newer one existed. Confirmed live: two
    # browsers open against the same running server showed different
    # content, one stale and one current (code-review 2026-08-12). This
    # page is cheap to regenerate — never worth a browser caching it.
    return HTMLResponse(html, headers={"Cache-Control": "no-store"})


@app.get(
    "/health",
    summary="Liveness check",
    description="Unauthenticated, unrated — used by uptime monitors.",
)
def health():
    """Unauthenticated, unrated: no @limiter.limit() here on purpose."""
    return {"status": "ok"}


@app.head("/health", include_in_schema=False)
def health_head():
    # Separate route, not methods=["GET","HEAD"] on one: FastAPI generated
    # the same operationId for both methods on a shared route, which is
    # invalid per the OpenAPI spec (duplicate operationId across the
    # document) and could break client/SDK codegen reading this schema.
    # HEAD is infra support for uptime monitors, not a documented product
    # operation, so it's excluded from the schema entirely instead.
    return {"status": "ok"}


# /health above is infrastructure (liveness probe for uptime monitors), not
# an API resource — it stays unversioned. Every resource endpoint mounts
# under /v1 (docs/ARCHITECTURE.md "API design standards"). Each resource
# router is included here as it ships; app.include_router(v1) must stay
# last — FastAPI copies a router's routes at include time, so anything
# added to v1 after that call would be silently dropped.
v1 = APIRouter(prefix="/v1")
v1.include_router(routes_router)
v1.include_router(parking_router)
v1.include_router(stations_router)
v1.include_router(rest_points_router)
v1.include_router(leisure_routes_router)
v1.include_router(support_points_router)

app.include_router(v1)
