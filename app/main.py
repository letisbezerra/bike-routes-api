import sentry_sdk
from fastapi import APIRouter, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse

from app.leisure_routes.router import router as leisure_routes_router
from app.parking.router import router as parking_router
from app.rest_points.router import router as rest_points_router
from app.routes.router import router as routes_router
from app.shared.config import APP_NAME, settings
from app.shared.errors import register_error_handlers
from app.shared.middleware import SecurityHeadersMiddleware, limiter
from app.stations.router import router as stations_router

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
sentry_sdk.init(
    dsn=settings.sentry_dsn,
    environment=settings.environment,
    include_local_variables=False,
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
)


@app.get("/", include_in_schema=False)
def root():
    """Bare-domain visitors (e.g. from the README/portfolio link) land on the
    docs instead of a raw 404 — the API itself has no root resource."""
    return RedirectResponse("/docs")


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

app.include_router(v1)
