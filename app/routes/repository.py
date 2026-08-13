from geoalchemy2.types import WKBElement
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.routes.models import BikeRoute, RouteCategory
from app.shared.spatial import (
    apply_bbox_filter,
    apply_geometry_clip,
    apply_round_robin_order,
    total_count,
)

# docs/specs/03-api-endpoints.md, pagination fairness fix — fixed, arbitrary
# tiebreak for the round-robin interleave below, not a priority ordering.
# Plain `id` ordering (the original design) put every "ciclofaixa"/
# "ciclovia" row before any "ciclorrota"/"passeio_compartilhado" row, since
# the source data was ingested in ID-contiguous blocks per category — a
# bbox with 200+ matches never reached the two smaller categories on page 1.
# Derived from the enum itself (not hand-copied) so a future 5th category is
# automatically covered — see apply_round_robin_order's docstring for why an
# uncovered value is worse than just "unranked".
_CATEGORY_ORDER = {cat: i for i, cat in enumerate(RouteCategory)}


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

    total = total_count(session, stmt)

    # Round-robin order instead of plain id — still fully deterministic and
    # stable across requests (a client paginating page-by-page never sees a
    # row shift); when `category` already narrows to one value, this
    # degenerates to a plain per-category `ORDER BY id`, same as before.
    stmt = apply_round_robin_order(stmt, BikeRoute.category, BikeRoute.id, _CATEGORY_ORDER)
    rows = session.execute(stmt.offset((page - 1) * page_size).limit(page_size)).all()
    return [
        (row[0], getattr(row, "clipped_geometry", None), getattr(row, "is_clipped", False))
        for row in rows
    ], total


def get_by_id(session: Session, route_id: int) -> BikeRoute | None:
    return session.get(BikeRoute, route_id)
