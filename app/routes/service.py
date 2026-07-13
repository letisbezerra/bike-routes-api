from math import ceil

from sqlalchemy.orm import Session

from app.routes.models import BikeRoute, RouteCategory
from app.routes.repository import get_by_id, list_paginated
from app.routes.schemas import BikeRouteFeature, BikeRouteFeatureCollection, BikeRouteProperties
from app.shared.geojson import to_geojson_geometry
from app.shared.schemas import PaginationMeta


def _to_feature(route: BikeRoute) -> BikeRouteFeature:
    return BikeRouteFeature(
        geometry=to_geojson_geometry(route.geometry),
        properties=BikeRouteProperties.model_validate(route),
    )


def list_routes(
    session: Session,
    *,
    page: int,
    page_size: int,
    category: RouteCategory | None = None,
    neighborhood: str | None = None,
    bbox: tuple[float, float, float, float] | None = None,
) -> BikeRouteFeatureCollection:
    rows, total = list_paginated(
        session,
        page=page,
        page_size=page_size,
        category=category,
        neighborhood=neighborhood,
        bbox=bbox,
    )
    total_pages = ceil(total / page_size)
    return BikeRouteFeatureCollection(
        features=[_to_feature(row) for row in rows],
        meta=PaginationMeta(page=page, page_size=page_size, total=total, total_pages=total_pages),
    )


def get_route(session: Session, route_id: int) -> BikeRouteFeature | None:
    route = get_by_id(session, route_id)
    if route is None:
        return None
    return _to_feature(route)
