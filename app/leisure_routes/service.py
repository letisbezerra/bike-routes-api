from geoalchemy2.types import WKBElement
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


def _to_feature(
    leisure_route: LeisureRoute,
    clipped_geometry: WKBElement | None = None,
    is_clipped: bool = False,
) -> LeisureRouteFeature:
    geometry = clipped_geometry if clipped_geometry is not None else leisure_route.geometry
    return LeisureRouteFeature(
        geometry=to_geojson_geometry(geometry),
        clipped=is_clipped,
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
    return LeisureRouteFeatureCollection(
        features=[
            _to_feature(leisure_route, clipped_geometry, is_clipped)
            for leisure_route, clipped_geometry, is_clipped in rows
        ],
        meta=PaginationMeta.build(page=page, page_size=page_size, total=total),
    )


def get_leisure_route(session: Session, leisure_route_id: int) -> LeisureRouteFeature | None:
    leisure_route = get_by_id(session, leisure_route_id)
    if leisure_route is None:
        return None
    return _to_feature(leisure_route)
