from geoalchemy2.types import WKBElement
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.routes.models import BikeRoute
from app.shared.spatial import apply_bbox_filter, apply_geometry_clip


def list_paginated(
    session: Session,
    *,
    page: int,
    page_size: int,
    category: str | None = None,
    neighborhood: str | None = None,
    bbox: tuple[float, float, float, float] | None = None,
) -> tuple[list[tuple[BikeRoute, WKBElement | None, bool]], int]:
    """Returns `(route, clipped_geometry, is_clipped)` per row — `bbox=None`
    means `clipped_geometry` is always `None` and `is_clipped` always
    `False` (docs/specs/06-geometry-clipping.md)."""
    stmt = select(BikeRoute)
    if category is not None:
        stmt = stmt.where(BikeRoute.category == category)
    if neighborhood is not None:
        stmt = stmt.where(BikeRoute.neighborhoods.any(neighborhood))
    if bbox is not None:
        stmt = apply_bbox_filter(stmt, BikeRoute.geometry, bbox)
        stmt, clipped_geometry, is_clipped = apply_geometry_clip(stmt, BikeRoute.geometry, bbox)
        stmt = stmt.add_columns(clipped_geometry, is_clipped)

    total = session.execute(select(func.count()).select_from(stmt.subquery())).scalar_one()
    rows = session.execute(
        stmt.order_by(BikeRoute.id).offset((page - 1) * page_size).limit(page_size)
    ).all()
    return [
        (row[0], getattr(row, "clipped_geometry", None), getattr(row, "is_clipped", False))
        for row in rows
    ], total


def get_by_id(session: Session, route_id: int) -> BikeRoute | None:
    return session.get(BikeRoute, route_id)
