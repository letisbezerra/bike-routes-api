from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.leisure_routes.models import LeisureRoute
from app.shared.spatial import apply_bbox_filter


def list_paginated(
    session: Session,
    *,
    page: int,
    page_size: int,
    bbox: tuple[float, float, float, float] | None = None,
) -> tuple[list[LeisureRoute], int]:
    stmt = select(LeisureRoute)
    if bbox is not None:
        stmt = apply_bbox_filter(stmt, LeisureRoute.geometry, bbox)

    total = session.execute(select(func.count()).select_from(stmt.subquery())).scalar_one()
    rows = (
        session.execute(
            stmt.order_by(LeisureRoute.id).offset((page - 1) * page_size).limit(page_size)
        )
        .scalars()
        .all()
    )
    return list(rows), total


def get_by_id(session: Session, leisure_route_id: int) -> LeisureRoute | None:
    return session.get(LeisureRoute, leisure_route_id)
