import uuid

import pytest
from geoalchemy2.shape import from_shape
from shapely.geometry import LineString
from sqlalchemy import text

from app.routes.models import BikeRoute, RouteCategory
from app.routes.repository import get_by_id, list_paginated
from app.shared.database import SessionLocal
from app.shared.geojson import to_geojson_geometry

# Padded 0.01deg beyond the real geometry extent (ST_Extent: lon -38.626923
# to -38.424137, lat -3.873407 to -3.694289) — docs/DATA_SOURCES.md's "lon
# ≈ -38.42 to -38.63" is an approximation and clips at least one real route.
FORTALEZA_BBOX = (-38.64, -3.89, -38.41, -3.68)
OUTSIDE_BBOX = (-40.0, -5.0, -39.9, -4.9)
SMALL_SELECTIVE_BBOX = (-38.53, -3.75, -38.52, -3.74)  # 5 of 447 rows

# Isolated far from the real Fortaleza dataset — safe area for synthetic
# clipping fixtures that must not overlap the 447 real rows.
CLIPPING_BBOX = (0.0, 0.0, 10.0, 10.0)


@pytest.fixture
def route_factory():
    """Inserts a temporary BikeRoute with a given geometry, returns its id.
    All rows created via this fixture are deleted at teardown."""
    created_ids = []

    def _make(coordinates: list[tuple[float, float]]) -> int:
        with SessionLocal() as session:
            route = BikeRoute(
                source_id=f"test-repo-clip-{uuid.uuid4()}",
                name="Fixture route",
                category=RouteCategory.CICLOVIA,
                length_km=None,
                segment=None,
                road_position=None,
                direction=None,
                pavement=None,
                separation_element=None,
                implemented_at=None,
                neighborhoods=[],
                reference_year=None,
                geometry=from_shape(LineString(coordinates), srid=4326),
            )
            session.add(route)
            session.commit()
            created_ids.append(route.id)
            return route.id

    yield _make

    with SessionLocal() as session:
        session.query(BikeRoute).filter(BikeRoute.id.in_(created_ids)).delete(
            synchronize_session=False
        )
        session.commit()


def test_list_paginated_respects_page_and_page_size():
    with SessionLocal() as session:
        rows, total = list_paginated(session, page=1, page_size=10)
    assert len(rows) == 10
    assert total == 447


def test_list_paginated_second_page_returns_different_rows():
    with SessionLocal() as session:
        first_page, _ = list_paginated(session, page=1, page_size=10)
        second_page, _ = list_paginated(session, page=2, page_size=10)
    first_ids = {route.id for route, _, _ in first_page}
    second_ids = {route.id for route, _, _ in second_page}
    assert first_ids.isdisjoint(second_ids)


def test_list_paginated_filters_by_category():
    with SessionLocal() as session:
        rows, total = list_paginated(
            session, page=1, page_size=200, category=RouteCategory.CICLOVIA
        )
    assert total == 93
    assert all(route.category == RouteCategory.CICLOVIA for route, _, _ in rows)


def test_list_paginated_filters_by_neighborhood():
    with SessionLocal() as session:
        rows, total = list_paginated(session, page=1, page_size=50, neighborhood="Bom Jardim")
    assert total == 17
    assert all("Bom Jardim" in route.neighborhoods for route, _, _ in rows)
    assert any(len(route.neighborhoods) > 1 for route, _, _ in rows)


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
        plan = (
            session.execute(
                text(
                    "EXPLAIN SELECT * FROM bike_routes WHERE ST_Intersects("
                    "geometry, ST_MakeEnvelope(:min_lon, :min_lat, :max_lon, :max_lat, 4326))"
                ),
                {"min_lon": min_lon, "min_lat": min_lat, "max_lon": max_lon, "max_lat": max_lat},
            )
            .scalars()
            .all()
        )
    plan_text = "\n".join(plan)
    assert "Seq Scan" not in plan_text
    assert "idx_bike_routes_geometry" in plan_text or "Bitmap" in plan_text


def test_get_by_id_returns_row_for_real_id():
    with SessionLocal() as session:
        rows, _ = list_paginated(session, page=1, page_size=1)
        real_id = rows[0][0].id
        route = get_by_id(session, real_id)
    assert route is not None
    assert route.id == real_id


def test_get_by_id_returns_none_for_missing_id():
    with SessionLocal() as session:
        route = get_by_id(session, 10_000_000)
    assert route is None


def test_list_paginated_without_bbox_never_reports_clipped(route_factory):
    route_factory([(2, 2), (8, 8)])
    with SessionLocal() as session:
        rows, _ = list_paginated(session, page=1, page_size=200)
    assert all(
        clipped_geometry is None and is_clipped is False for _, clipped_geometry, is_clipped in rows
    )


def test_list_paginated_with_bbox_reports_clipped_flag_and_geometry(route_factory):
    fully_inside_id = route_factory([(2, 2), (8, 8)])
    crossing_id = route_factory([(-5, 5), (15, 5)])
    with SessionLocal() as session:
        rows, _ = list_paginated(session, page=1, page_size=200, bbox=CLIPPING_BBOX)
    by_id = {
        route.id: (clipped_geometry, is_clipped) for route, clipped_geometry, is_clipped in rows
    }

    _, fully_inside_clipped = by_id[fully_inside_id]
    assert fully_inside_clipped is False

    crossing_geometry, crossing_clipped = by_id[crossing_id]
    assert crossing_clipped is True
    assert crossing_geometry is not None


def test_list_paginated_excludes_tangential_touch_and_keeps_total_consistent(route_factory):
    """A route only touching the bbox boundary at one point (never entering
    the interior) must be excluded both from `features` and from `total` —
    otherwise pagination metadata would count a row absent from the page
    (docs/specs/06-geometry-clipping.md, Decision 1)."""
    route_factory([(2, 2), (8, 8)])  # fully inside — included
    route_factory([(-5, 5), (15, 5)])  # partially crossing — included
    route_factory([(-5, -5), (0, 0), (-5, 5)])  # tangential touch only — excluded

    with SessionLocal() as session:
        rows, total = list_paginated(session, page=1, page_size=200, bbox=CLIPPING_BBOX)

    assert total == 2
    assert len(rows) == 2


def test_list_paginated_multi_crossing_produces_multilinestring(route_factory):
    """A route that exits and re-enters the bbox more than once clips to
    disjoint segments — PostGIS (and `to_geojson_geometry`) correctly
    represent that as a MultiLineString, even though `bike_routes` is always
    stored as a single LineString. Callers must not assume a clipped
    `bike_routes` feature keeps its stored geometry type
    (docs/specs/06-geometry-clipping.md, Decision 1)."""
    route_id = route_factory([(-5, 5), (5, 5), (15, 5), (5, 3), (-5, 3)])

    with SessionLocal() as session:
        rows, total = list_paginated(session, page=1, page_size=200, bbox=CLIPPING_BBOX)

    by_id = {
        route.id: (clipped_geometry, is_clipped) for route, clipped_geometry, is_clipped in rows
    }
    clipped_geometry, is_clipped = by_id[route_id]
    assert total == 1
    assert is_clipped is True
    geometry = to_geojson_geometry(clipped_geometry)
    assert geometry["type"] == "MultiLineString"
    assert len(geometry["coordinates"]) == 2
