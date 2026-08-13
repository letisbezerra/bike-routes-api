from geoalchemy2.types import WKBElement
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.leisure_routes.models import LeisureRoute
from app.shared.spatial import apply_bbox_filter, apply_geometry_clip, total_count


def list_paginated(
    session: Session,
    *,
    page: int,
    page_size: int,
    bbox: tuple[float, float, float, float] | None = None,
) -> tuple[list[tuple[LeisureRoute, WKBElement | None, bool]], int]:
    """Returns `(leisure_route, clipped_geometry, is_clipped)` per row —
    `bbox=None` means `clipped_geometry` is always `None` and `is_clipped`
    always `False` (docs/specs/06-geometry-clipping.md)."""
    stmt = select(LeisureRoute)
    if bbox is not None:
        stmt = apply_bbox_filter(stmt, LeisureRoute.geometry, bbox)
        stmt, clipped_geometry, is_clipped = apply_geometry_clip(stmt, LeisureRoute.geometry, bbox)
        stmt = stmt.add_columns(clipped_geometry, is_clipped)

    total = total_count(session, stmt)
    rows = session.execute(
        stmt.order_by(LeisureRoute.id).offset((page - 1) * page_size).limit(page_size)
    ).all()
    return [
        (row[0], getattr(row, "clipped_geometry", None), getattr(row, "is_clipped", False))
        for row in rows
    ], total


def get_by_id(session: Session, leisure_route_id: int) -> LeisureRoute | None:
    return session.get(LeisureRoute, leisure_route_id)
