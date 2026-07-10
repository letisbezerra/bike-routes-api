from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.parking.models import BikeParking


def list_paginated(
    session: Session,
    *,
    page: int,
    page_size: int,
    type: str | None = None,
    bbox: tuple[float, float, float, float] | None = None,
) -> tuple[list[BikeParking], int]:
    stmt = select(BikeParking)
    if type is not None:
        stmt = stmt.where(BikeParking.type == type)
    if bbox is not None:
        min_lon, min_lat, max_lon, max_lat = bbox
        envelope = func.ST_MakeEnvelope(min_lon, min_lat, max_lon, max_lat, 4326)
        stmt = stmt.where(func.ST_Intersects(BikeParking.geometry, envelope))

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
