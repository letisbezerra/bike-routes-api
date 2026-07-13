from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.parking.models import BikeParking
from app.shared.spatial import apply_bbox_filter


def list_paginated(
    session: Session,
    *,
    page: int,
    page_size: int,
    parking_type: str | None = None,
    bbox: tuple[float, float, float, float] | None = None,
) -> tuple[list[BikeParking], int]:
    stmt = select(BikeParking)
    if parking_type is not None:
        stmt = stmt.where(BikeParking.type == parking_type)
    if bbox is not None:
        stmt = apply_bbox_filter(stmt, BikeParking.geometry, bbox)

    total = session.execute(select(func.count()).select_from(stmt.subquery())).scalar_one()
    rows = (
        session.execute(
            stmt.order_by(BikeParking.id).offset((page - 1) * page_size).limit(page_size)
        )
        .scalars()
        .all()
    )
    return list(rows), total


def get_by_id(session: Session, parking_id: int) -> BikeParking | None:
    return session.get(BikeParking, parking_id)
