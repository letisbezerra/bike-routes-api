from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.routes.models import BikeRoute
from app.shared.spatial import apply_bbox_filter


def list_paginated(
    session: Session,
    *,
    page: int,
    page_size: int,
    category: str | None = None,
    neighborhood: str | None = None,
    bbox: tuple[float, float, float, float] | None = None,
) -> tuple[list[BikeRoute], int]:
    stmt = select(BikeRoute)
    if category is not None:
        stmt = stmt.where(BikeRoute.category == category)
    if neighborhood is not None:
        stmt = stmt.where(BikeRoute.neighborhoods.any(neighborhood))
    if bbox is not None:
        stmt = apply_bbox_filter(stmt, BikeRoute.geometry, bbox)

    total = session.execute(select(func.count()).select_from(stmt.subquery())).scalar_one()
    rows = (
        session.execute(stmt.order_by(BikeRoute.id).offset((page - 1) * page_size).limit(page_size))
        .scalars()
        .all()
    )
    return list(rows), total


def get_by_id(session: Session, route_id: int) -> BikeRoute | None:
    return session.get(BikeRoute, route_id)
