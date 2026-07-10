from sqlalchemy import text

from app.parking.models import ParkingType
from app.parking.repository import get_by_id, list_paginated
from app.shared.database import SessionLocal

# Same padding rationale as tests/routes/test_repository.py: derived from the
# real ST_Extent of bike_parking, not docs/DATA_SOURCES.md's approximation.
FORTALEZA_BBOX = (-38.64, -3.89, -38.41, -3.68)
OUTSIDE_BBOX = (-40.0, -5.0, -39.9, -4.9)


def test_list_paginated_respects_page_and_page_size():
    with SessionLocal() as session:
        rows, total = list_paginated(session, page=1, page_size=10)
    assert len(rows) == 10
    assert total == 301


def test_list_paginated_second_page_returns_different_rows():
    with SessionLocal() as session:
        first_page, _ = list_paginated(session, page=1, page_size=10)
        second_page, _ = list_paginated(session, page=2, page_size=10)
    assert {r.id for r in first_page}.isdisjoint({r.id for r in second_page})


def test_list_paginated_filters_by_type():
    with SessionLocal() as session:
        rows, total = list_paginated(
            session, page=1, page_size=10, type=ParkingType.BICICLETARIO
        )
    assert total == 5
    assert all(r.type == ParkingType.BICICLETARIO for r in rows)


def test_list_paginated_filters_by_bbox_covering_fortaleza():
    with SessionLocal() as session:
        _, total_all = list_paginated(session, page=1, page_size=1)
        _, total_bbox = list_paginated(session, page=1, page_size=1, bbox=FORTALEZA_BBOX)
    assert total_bbox == total_all


def test_list_paginated_filters_by_bbox_outside_fortaleza_returns_nothing():
    with SessionLocal() as session:
        rows, total = list_paginated(session, page=1, page_size=10, bbox=OUTSIDE_BBOX)
    assert rows == []
    assert total == 0


def test_bbox_query_uses_gist_index_not_sequential_scan():
    with SessionLocal() as session:
        min_lon, min_lat, max_lon, max_lat = session.execute(
            text(
                "SELECT ST_XMin(e), ST_YMin(e), ST_XMax(e), ST_YMax(e) FROM ("
                "SELECT ST_Extent(geometry) AS e FROM bike_parking) sub"
            )
        ).one()
        # Narrow the real extent to a small corner — selective enough that
        # the planner prefers the GiST index over a sequential scan (see
        # tests/routes/test_repository.py for why a near-whole-table bbox
        # doesn't exercise this).
        mid_lon = (min_lon + max_lon) / 2
        mid_lat = (min_lat + max_lat) / 2
        plan = session.execute(
            text(
                "EXPLAIN SELECT * FROM bike_parking WHERE ST_Intersects("
                "geometry, ST_MakeEnvelope(:min_lon, :min_lat, :mid_lon, :mid_lat, 4326))"
            ),
            {"min_lon": min_lon, "min_lat": min_lat, "mid_lon": mid_lon, "mid_lat": mid_lat},
        ).scalars().all()
    plan_text = "\n".join(plan)
    assert "Seq Scan" not in plan_text
    assert "idx_bike_parking_geometry" in plan_text or "Bitmap" in plan_text


def test_get_by_id_returns_row_for_real_id():
    with SessionLocal() as session:
        rows, _ = list_paginated(session, page=1, page_size=1)
        real_id = rows[0].id
        parking = get_by_id(session, real_id)
    assert parking is not None
    assert parking.id == real_id


def test_get_by_id_returns_none_for_missing_id():
    with SessionLocal() as session:
        parking = get_by_id(session, 10_000_000)
    assert parking is None
