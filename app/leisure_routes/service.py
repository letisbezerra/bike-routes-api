from math import ceil

from sqlalchemy.orm import Session

from app.leisure_routes.models import LeisureRoute
from app.leisure_routes.repository import get_by_id, list_paginated
from app.leisure_routes.schemas import (
    LeisureRouteFeature,
    LeisureRouteFeatureCollection,
    LeisureRouteProperties,
)
from app.shared.geojson import to_geojson_geometry
from app.shared.schemas import PaginationMeta


def _to_feature(leisure_route: LeisureRoute) -> LeisureRouteFeature:
    return LeisureRouteFeature(
        geometry=to_geojson_geometry(leisure_route.geometry),
        properties=LeisureRouteProperties.model_validate(leisure_route),
    )


def list_leisure_routes(
    session: Session,
    *,
    page: int,
    page_size: int,
    bbox: tuple[float, float, float, float] | None = None,
) -> LeisureRouteFeatureCollection:
    rows, total = list_paginated(session, page=page, page_size=page_size, bbox=bbox)
    total_pages = ceil(total / page_size)
    return LeisureRouteFeatureCollection(
        features=[_to_feature(row) for row in rows],
        meta=PaginationMeta(page=page, page_size=page_size, total=total, total_pages=total_pages),
    )


def get_leisure_route(session: Session, leisure_route_id: int) -> LeisureRouteFeature | None:
    leisure_route = get_by_id(session, leisure_route_id)
    if leisure_route is None:
        return None
    return _to_feature(leisure_route)
