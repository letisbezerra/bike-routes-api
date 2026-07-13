from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.shared.spatial import apply_bbox_filter
from app.stations.models import BikeShareStation


def list_paginated(
    session: Session,
    *,
    page: int,
    page_size: int,
    status: str | None = None,
    neighborhood: str | None = None,
    bbox: tuple[float, float, float, float] | None = None,
) -> tuple[list[BikeShareStation], int]:
    stmt = select(BikeShareStation)
    if status is not None:
        stmt = stmt.where(BikeShareStation.status == status)
    if neighborhood is not None:
        stmt = stmt.where(BikeShareStation.neighborhood == neighborhood)
    if bbox is not None:
        stmt = apply_bbox_filter(stmt, BikeShareStation.geometry, bbox)

    total = session.execute(select(func.count()).select_from(stmt.subquery())).scalar_one()
    rows = (
        session.execute(
            stmt.order_by(BikeShareStation.id).offset((page - 1) * page_size).limit(page_size)
        )
        .scalars()
        .all()
    )
    return list(rows), total


def get_by_id(session: Session, station_id: int) -> BikeShareStation | None:
    return session.get(BikeShareStation, station_id)
