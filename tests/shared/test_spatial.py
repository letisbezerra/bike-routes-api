import uuid

import pytest
from geoalchemy2.shape import from_shape, to_shape
from shapely.geometry import LineString, mapping
from sqlalchemy import select

from app.routes.models import BikeRoute, RouteCategory
from app.shared.database import SessionLocal
from app.shared.spatial import apply_bbox_filter, apply_geometry_clip

# Isolated far from the real Fortaleza dataset (lon ~-38, lat ~-3) so these
# synthetic fixtures never overlap real ingested rows.
BBOX = (0.0, 0.0, 10.0, 10.0)


@pytest.fixture
def route_factory():
    """Inserts a temporary BikeRoute with a given geometry, returns its id.
    All rows created via this fixture are deleted at teardown."""
    created_ids = []

    def _make(coordinates: list[tuple[float, float]]) -> int:
        with SessionLocal() as session:
            route = BikeRoute(
                source_id=f"test-spatial-{uuid.uuid4()}",
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


def _clipped_row(session, route_id: int):
    stmt = select(BikeRoute).where(BikeRoute.id == route_id)
    stmt = apply_bbox_filter(stmt, BikeRoute.geometry, BBOX)
    stmt, clipped_geometry, is_clipped = apply_geometry_clip(stmt, BikeRoute.geometry, BBOX)
    stmt = stmt.add_columns(clipped_geometry, is_clipped)
    return session.execute(stmt).first()


def test_line_fully_inside_bbox_is_not_marked_clipped(route_factory):
    route_id = route_factory([(2, 2), (8, 8)])
    with SessionLocal() as session:
        row = _clipped_row(session, route_id)
    assert row is not None
    assert row.is_clipped is False
    assert mapping(to_shape(row.clipped_geometry))["coordinates"] == ((2.0, 2.0), (8.0, 8.0))


def test_line_partially_crossing_bbox_returns_clipped_subset(route_factory):
    # Spans from x=-5 to x=15, straight through the bbox at y=5 — only the
    # x in [0, 10] portion should survive the clip.
    route_id = route_factory([(-5, 5), (15, 5)])
    with SessionLocal() as session:
        row = _clipped_row(session, route_id)
    assert row is not None
    assert row.is_clipped is True
    coords = mapping(to_shape(row.clipped_geometry))["coordinates"]
    assert coords == ((0.0, 5.0), (10.0, 5.0))


def test_line_touching_bbox_boundary_at_one_point_is_excluded(route_factory):
    # V-shape whose only point at x>=0 is the single vertex (0, 0), sitting
    # exactly on the bbox's corner — never crosses into the interior.
    route_id = route_factory([(-5, -5), (0, 0), (-5, 5)])
    with SessionLocal() as session:
        row = _clipped_row(session, route_id)
    assert row is None


def test_line_fully_outside_bbox_is_absent_before_clip_even_applies(route_factory):
    route_id = route_factory([(-5, -5), (-6, -6)])
    with SessionLocal() as session:
        row = _clipped_row(session, route_id)
    assert row is None
