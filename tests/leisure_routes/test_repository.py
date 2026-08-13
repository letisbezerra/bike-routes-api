import uuid

import pytest
from geoalchemy2.shape import from_shape
from shapely.geometry import MultiLineString
from sqlalchemy import text

from app.leisure_routes.models import LeisureRoute
from app.leisure_routes.repository import get_by_id, list_paginated
from app.shared.database import SessionLocal

# Same padding rationale as tests/routes/test_repository.py: derived from the
# real ST_Extent of leisure_routes, not docs/DATA_SOURCES.md's approximation.
FORTALEZA_BBOX = (-38.64, -3.89, -38.41, -3.68)
OUTSIDE_BBOX = (-40.0, -5.0, -39.9, -4.9)

# Isolated far from the real Fortaleza dataset — safe area for synthetic
# clipping fixtures that must not overlap the 3 real rows.
CLIPPING_BBOX = (0.0, 0.0, 10.0, 10.0)


@pytest.fixture
def leisure_route_factory():
    """Inserts a temporary LeisureRoute with a given single-line geometry,
    returns its id. All rows created via this fixture are deleted at
    teardown."""
    created_ids = []

    def _make(coordinates: list[tuple[float, float]]) -> int:
        with SessionLocal() as session:
            leisure_route = LeisureRoute(
                source_id=f"test-repo-clip-{uuid.uuid4()}",
                name="Fixture leisure route",
                support_count=None,
                geometry=from_shape(MultiLineString([coordinates]), srid=4326),
            )
            session.add(leisure_route)
            session.commit()
            created_ids.append(leisure_route.id)
            return leisure_route.id

    yield _make

    with SessionLocal() as session:
        session.query(LeisureRoute).filter(LeisureRoute.id.in_(created_ids)).delete(
            synchronize_session=False
        )
        session.commit()


def test_list_paginated_respects_page_and_page_size():
    with SessionLocal() as session:
        rows, total = list_paginated(session, page=1, page_size=2)
    assert len(rows) == 2
    assert total == 3


def test_list_paginated_second_page_returns_different_rows():
    with SessionLocal() as session:
        first_page, _ = list_paginated(session, page=1, page_size=2)
        second_page, _ = list_paginated(session, page=2, page_size=2)
    first_ids = {route.id for route, _, _ in first_page}
    second_ids = {route.id for route, _, _ in second_page}
    assert first_ids.isdisjoint(second_ids)
    assert len(second_page) == 1


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
                "SELECT ST_Extent(geometry) AS e FROM leisure_routes) sub"
            )
        ).one()
        # Narrow the real extent to a small corner — the planner still
        # prefers the GiST index over a sequential scan even on this
        # 3-row table (see tests/routes/test_repository.py for why a
        # near-whole-table bbox doesn't exercise this).
        mid_lon = (min_lon + max_lon) / 2
        mid_lat = (min_lat + max_lat) / 2
        plan = session.execute(
            text(
                "EXPLAIN SELECT * FROM leisure_routes WHERE ST_Intersects("
                "geometry, ST_MakeEnvelope(:min_lon, :min_lat, :mid_lon, :mid_lat, 4326))"
            ),
            {"min_lon": min_lon, "min_lat": min_lat, "mid_lon": mid_lon, "mid_lat": mid_lat},
        ).scalars().all()
    plan_text = "\n".join(plan)
    assert "Seq Scan" not in plan_text
    assert "idx_leisure_routes_geometry" in plan_text or "Bitmap" in plan_text


def test_get_by_id_returns_row_for_real_id():
    with SessionLocal() as session:
        rows, _ = list_paginated(session, page=1, page_size=1)
        real_id = rows[0][0].id
        leisure_route = get_by_id(session, real_id)
    assert leisure_route is not None
    assert leisure_route.id == real_id


def test_get_by_id_returns_none_for_missing_id():
    with SessionLocal() as session:
        leisure_route = get_by_id(session, 10_000_000)
    assert leisure_route is None


def test_list_paginated_with_bbox_reports_clipped_flag_and_geometry(leisure_route_factory):
    fully_inside_id = leisure_route_factory([(2, 2), (8, 8)])
    crossing_id = leisure_route_factory([(-5, 5), (15, 5)])
    with SessionLocal() as session:
        rows, _ = list_paginated(session, page=1, page_size=200, bbox=CLIPPING_BBOX)
    by_id = {
        leisure_route.id: (clipped_geometry, is_clipped)
        for leisure_route, clipped_geometry, is_clipped in rows
    }

    _, fully_inside_clipped = by_id[fully_inside_id]
    assert fully_inside_clipped is False

    crossing_geometry, crossing_clipped = by_id[crossing_id]
    assert crossing_clipped is True
    assert crossing_geometry is not None


def test_list_paginated_excludes_tangential_touch_and_keeps_total_consistent(
    leisure_route_factory,
):
    """Same guarantee as tests/routes/test_repository.py's equivalent test —
    a route only touching the bbox boundary at one point must be excluded
    both from `features` and from `total` (docs/specs/06-geometry-clipping.md,
    Decision 1)."""
    leisure_route_factory([(2, 2), (8, 8)])  # fully inside — included
    leisure_route_factory([(-5, 5), (15, 5)])  # partially crossing — included
    leisure_route_factory([(-5, -5), (0, 0), (-5, 5)])  # tangential touch only — excluded

    with SessionLocal() as session:
        rows, total = list_paginated(session, page=1, page_size=200, bbox=CLIPPING_BBOX)

    assert total == 2
    assert len(rows) == 2
