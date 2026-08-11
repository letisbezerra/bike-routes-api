from geoalchemy2.types import WKBElement
from sqlalchemy import case, func, select
from sqlalchemy.orm import Session

from app.routes.models import BikeRoute, RouteCategory
from app.shared.spatial import apply_bbox_filter, apply_geometry_clip

# docs/specs/03-api-endpoints.md, pagination fairness fix — fixed, arbitrary
# tiebreak for the round-robin interleave below, not a priority ordering.
# Plain `id` ordering (the original design) put every "ciclofaixa"/
# "ciclovia" row before any "ciclorrota"/"passeio_compartilhado" row, since
# the source data was ingested in ID-contiguous blocks per category — a
# bbox with 200+ matches never reached the two smaller categories on page 1.
_CATEGORY_ORDER = {
    RouteCategory.CICLOFAIXA: 0,
    RouteCategory.CICLOVIA: 1,
    RouteCategory.CICLORROTA: 2,
    RouteCategory.PASSEIO_COMPARTILHADO: 3,
}


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

    # Round-robin order — (category_rank, category_order) — instead of
    # plain id: category_rank is each row's ascending-id position within
    # its own category, category_order only breaks ties between the 4
    # categories sharing a rank. Still fully deterministic and stable
    # across requests (a client paginating page-by-page never sees a row
    # shift); when `category` already narrows to one value, this
    # degenerates to a plain per-category `ORDER BY id`, same as before.
    category_rank = func.row_number().over(
        partition_by=BikeRoute.category, order_by=BikeRoute.id
    ).label("category_rank")
    category_order_case = case(
        *[(BikeRoute.category == cat, order) for cat, order in _CATEGORY_ORDER.items()]
    )
    rows = session.execute(
        stmt.add_columns(category_rank)
        .order_by(category_rank, category_order_case)
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).all()
    return [
        (row[0], getattr(row, "clipped_geometry", None), getattr(row, "is_clipped", False))
        for row in rows
    ], total


def get_by_id(session: Session, route_id: int) -> BikeRoute | None:
    return session.get(BikeRoute, route_id)
