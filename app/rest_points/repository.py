from sqlalchemy import select
from sqlalchemy.orm import Session

from app.rest_points.models import RestPoint
from app.shared.spatial import apply_bbox_filter, total_count


def list_paginated(
    session: Session,
    *,
    page: int,
    page_size: int,
    bbox: tuple[float, float, float, float] | None = None,
) -> tuple[list[RestPoint], int]:
    stmt = select(RestPoint)
    if bbox is not None:
        stmt = apply_bbox_filter(stmt, RestPoint.geometry, bbox)

    total = total_count(session, stmt)
    rows = (
        session.execute(
            stmt.order_by(RestPoint.id).offset((page - 1) * page_size).limit(page_size)
        )
        .scalars()
        .all()
    )
    return list(rows), total


def get_by_id(session: Session, rest_point_id: int) -> RestPoint | None:
    return session.get(RestPoint, rest_point_id)
