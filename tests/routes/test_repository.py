from sqlalchemy import text

from app.routes.models import RouteCategory
from app.routes.repository import get_by_id, list_paginated
from app.shared.database import SessionLocal

# Padded 0.01deg beyond the real geometry extent (ST_Extent: lon -38.626923
# to -38.424137, lat -3.873407 to -3.694289) — docs/DATA_SOURCES.md's "lon
# ≈ -38.42 to -38.63" is an approximation and clips at least one real route.
FORTALEZA_BBOX = (-38.64, -3.89, -38.41, -3.68)
OUTSIDE_BBOX = (-40.0, -5.0, -39.9, -4.9)
SMALL_SELECTIVE_BBOX = (-38.53, -3.75, -38.52, -3.74)  # 5 of 447 rows


def test_list_paginated_respects_page_and_page_size():
    with SessionLocal() as session:
        rows, total = list_paginated(session, page=1, page_size=10)
    assert len(rows) == 10
    assert total == 447


def test_list_paginated_second_page_returns_different_rows():
    with SessionLocal() as session:
        first_page, _ = list_paginated(session, page=1, page_size=10)
        second_page, _ = list_paginated(session, page=2, page_size=10)
    assert {r.id for r in first_page}.isdisjoint({r.id for r in second_page})


def test_list_paginated_filters_by_category():
    with SessionLocal() as session:
        rows, total = list_paginated(
            session, page=1, page_size=200, category=RouteCategory.CICLOVIA
        )
    assert total == 93
    assert all(r.category == RouteCategory.CICLOVIA for r in rows)


def test_list_paginated_filters_by_neighborhood():
    with SessionLocal() as session:
        rows, total = list_paginated(session, page=1, page_size=50, neighborhood="Bom Jardim")
    assert total == 17
    assert all("Bom Jardim" in r.neighborhoods for r in rows)
    assert any(len(r.neighborhoods) > 1 for r in rows)


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
    # A narrow, selective bbox — the planner only prefers the GiST index
    # over a sequential scan when the predicate actually filters out most
    # rows (a near-whole-table bbox makes Seq Scan the cheaper, correct
    # choice, which isn't what this test is checking).
    min_lon, min_lat, max_lon, max_lat = SMALL_SELECTIVE_BBOX
    with SessionLocal() as session:
        plan = session.execute(
            text(
                "EXPLAIN SELECT * FROM bike_routes WHERE ST_Intersects("
                "geometry, ST_MakeEnvelope(:min_lon, :min_lat, :max_lon, :max_lat, 4326))"
            ),
            {"min_lon": min_lon, "min_lat": min_lat, "max_lon": max_lon, "max_lat": max_lat},
        ).scalars().all()
    plan_text = "\n".join(plan)
    assert "Seq Scan" not in plan_text
    assert "idx_bike_routes_geometry" in plan_text or "Bitmap" in plan_text


def test_get_by_id_returns_row_for_real_id():
    with SessionLocal() as session:
        rows, _ = list_paginated(session, page=1, page_size=1)
        real_id = rows[0].id
        route = get_by_id(session, real_id)
    assert route is not None
    assert route.id == real_id


def test_get_by_id_returns_none_for_missing_id():
    with SessionLocal() as session:
        route = get_by_id(session, 10_000_000)
    assert route is None
