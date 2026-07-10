from fastapi import APIRouter, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware

from app.parking.router import router as parking_router
from app.rest_points.router import router as rest_points_router
from app.routes.router import router as routes_router
from app.shared.errors import register_error_handlers
from app.shared.middleware import SecurityHeadersMiddleware, limiter
from app.stations.router import router as stations_router

app = FastAPI(title="bike-routes-api")

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
register_error_handlers(app)
app.add_middleware(SlowAPIMiddleware)
app.add_middleware(SecurityHeadersMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["GET"],
)


@app.get("/health")
def health():
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

app.include_router(v1)
