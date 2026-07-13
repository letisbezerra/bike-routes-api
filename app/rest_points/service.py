from math import ceil

from sqlalchemy.orm import Session

from app.rest_points.models import RestPoint
from app.rest_points.repository import get_by_id, list_paginated
from app.rest_points.schemas import (
    RestPointFeature,
    RestPointFeatureCollection,
    RestPointProperties,
)
from app.shared.geojson import to_geojson_geometry
from app.shared.schemas import PaginationMeta


def _to_feature(rest_point: RestPoint) -> RestPointFeature:
    return RestPointFeature(
        geometry=to_geojson_geometry(rest_point.geometry),
        properties=RestPointProperties.model_validate(rest_point),
    )


def list_rest_points(
    session: Session,
    *,
    page: int,
    page_size: int,
    bbox: tuple[float, float, float, float] | None = None,
) -> RestPointFeatureCollection:
    rows, total = list_paginated(session, page=page, page_size=page_size, bbox=bbox)
    total_pages = ceil(total / page_size)
    return RestPointFeatureCollection(
        features=[_to_feature(row) for row in rows],
        meta=PaginationMeta(page=page, page_size=page_size, total=total, total_pages=total_pages),
    )


def get_rest_point(session: Session, rest_point_id: int) -> RestPointFeature | None:
    rest_point = get_by_id(session, rest_point_id)
    if rest_point is None:
        return None
    return _to_feature(rest_point)
