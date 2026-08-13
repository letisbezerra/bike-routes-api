from sqlalchemy import select
from sqlalchemy.orm import Session

from app.parking.models import BikeParking, ParkingType
from app.shared.spatial import apply_bbox_filter, apply_round_robin_order, total_count

# code-review 2026-08-11: data/raw/estacionamentos_de_bicicleta.geojson is
# ingested as ~296 contiguous "paraciclo" rows followed by only 5
# "bicicletario" rows, the same id-contiguous-per-type shape that caused the
# routes starvation bug (app/routes/repository.py) — plain `ORDER BY id`
# here reproduced it: an unfiltered/wide-bbox page never reached
# "bicicletario". Derived from the enum so a future 3rd type is covered.
_TYPE_ORDER = {t: i for i, t in enumerate(ParkingType)}


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

    total = total_count(session, stmt)
    stmt = apply_round_robin_order(stmt, BikeParking.type, BikeParking.id, _TYPE_ORDER)
    rows = session.execute(stmt.offset((page - 1) * page_size).limit(page_size)).scalars().all()
    return list(rows), total


def get_by_id(session: Session, parking_id: int) -> BikeParking | None:
    return session.get(BikeParking, parking_id)
