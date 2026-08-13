from sqlalchemy import select
from sqlalchemy.orm import Session

from app.shared.spatial import apply_bbox_filter, apply_round_robin_order, total_count
from app.stations.models import BikeShareStation, StationStatus

# code-review 2026-08-11: today's data isn't block-ordered enough by status
# to visibly starve a page (see app/parking/repository.py for the sibling
# case that IS live), but nothing structurally protects against a future
# re-ingestion that groups by status the way the source data groups by
# category/type elsewhere — same fairness fix applied preemptively.
_STATUS_ORDER = {status: i for i, status in enumerate(StationStatus)}


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

    total = total_count(session, stmt)
    stmt = apply_round_robin_order(
        stmt, BikeShareStation.status, BikeShareStation.id, _STATUS_ORDER
    )
    rows = session.execute(stmt.offset((page - 1) * page_size).limit(page_size)).scalars().all()
    return list(rows), total


def get_by_id(session: Session, station_id: int) -> BikeShareStation | None:
    return session.get(BikeShareStation, station_id)
