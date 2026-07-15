from fastapi import APIRouter, FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.leisure_routes.router import router as leisure_routes_router
from app.parking.router import router as parking_router
from app.rest_points.router import router as rest_points_router
from app.routes.router import router as routes_router
from app.shared.config import settings
from app.shared.errors import register_error_handlers
from app.shared.middleware import SecurityHeadersMiddleware, limiter
from app.stations.router import router as stations_router

app = FastAPI(
    title="bike-routes-api",
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

if settings.enable_observability:
    from app.shared.observability import setup_observability

    setup_observability(app)
app.add_middleware(SecurityHeadersMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["GET"],
)


@app.get(
    "/health",
    summary="Liveness check",
    description="Unauthenticated, unrated — used by uptime monitors.",
)
def health():
    """Unauthenticated, unrated: no @limiter.limit() here on purpose."""
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
