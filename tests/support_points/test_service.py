import uuid

import pytest
from geoalchemy2.shape import from_shape
from shapely.geometry import Point

import app.support_points.service as support_points_service
from app.parking.models import BikeParking, ParkingType
from app.rest_points.models import RestPoint
from app.shared.database import SessionLocal
from app.stations.models import BikeShareStation, StationStatus
from app.support_points.service import _fetch_page_rows, list_support_points

# Isolated far from the real Fortaleza dataset (lon ~-38, lat ~-3) — safe
# area for synthetic fixtures that must not overlap real ingested rows.
BBOX = (0.0, 0.0, 10.0, 10.0)


def test_fetch_page_rows_returns_empty_dict_for_empty_page():
    with SessionLocal() as session:
        assert _fetch_page_rows(session, []) == {}


@pytest.fixture
def support_point_fixtures():
    """Inserts one parking, one station, and one rest_point at known
    coordinates inside BBOX. Deletes all three at teardown."""
    created = []
    with SessionLocal() as session:
        parking = BikeParking(
            source_id=f"test-support-parking-{uuid.uuid4()}",
            name="Fixture parking",
            spot_count=5,
            type=ParkingType.PARACICLO,
            operating_hours=None,
            geometry=from_shape(Point(2, 2), srid=4326),
        )
        station = BikeShareStation(
            source_id=f"test-support-station-{uuid.uuid4()}",
            name="Fixture station",
            neighborhood=None,
            regional=None,
            inaugurated_at=None,
            status=StationStatus.EXISTENTE,
            sponsor=None,
            current_slots=None,
            station_type=None,
            geometry=from_shape(Point(5, 5), srid=4326),
        )
        rest_point = RestPoint(
            source_id=f"test-support-rest-{uuid.uuid4()}",
            name="Fixture rest point",
            image_urls=[],
            geometry=from_shape(Point(8, 8), srid=4326),
        )
        session.add_all([parking, station, rest_point])
        session.commit()
        created = [
            (BikeParking, parking.id),
            (BikeShareStation, station.id),
            (RestPoint, rest_point.id),
        ]

    yield

    with SessionLocal() as session:
        for model, row_id in created:
            session.query(model).filter(model.id == row_id).delete()
        session.commit()


def test_list_support_points_combines_all_three_resources(support_point_fixtures):
    with SessionLocal() as session:
        result = list_support_points(session, page=1, page_size=200, bbox=BBOX)

    assert result.meta.total == 3
    resource_types = [f.properties.resource_type for f in result.features]
    # Round-robin: with one fixture per type (all at type_rank 0), order
    # falls back to the type_order tiebreak — parking, station, rest_point.
    assert resource_types == ["parking", "station", "rest_point"]


def test_list_support_points_reports_total_by_type(support_point_fixtures):
    with SessionLocal() as session:
        result = list_support_points(session, page=1, page_size=200, bbox=BBOX)

    assert result.meta.total_by_type == {"parking": 1, "station": 1, "rest_point": 1}


def test_list_support_points_paginates_across_the_merged_sorted_list(support_point_fixtures):
    with SessionLocal() as session:
        first_page = list_support_points(session, page=1, page_size=2, bbox=BBOX)
        second_page = list_support_points(session, page=2, page_size=2, bbox=BBOX)

    assert first_page.meta.total == 3
    assert second_page.meta.total == 3
    assert [f.properties.resource_type for f in first_page.features] == ["parking", "station"]
    assert [f.properties.resource_type for f in second_page.features] == ["rest_point"]


def test_list_support_points_round_robin_prevents_one_type_starving_the_page(support_point_fixtures):
    """Regression test for the pagination-fairness bug: found live when a
    large-bbox query returned a page 1 that was 100% parking, because the
    original ordering was (resource_type, id) and "parking" sorts first
    alphabetically while also being the largest of the 3 tables. Seeds
    enough extra parking rows to fill a page by itself, alongside the
    single station/rest_point fixture, and asserts the page still contains
    a mix instead of being consumed entirely by parking."""
    extra_parking_ids = []
    with SessionLocal() as session:
        for i in range(15):
            row = BikeParking(
                source_id=f"test-support-parking-extra-{uuid.uuid4()}",
                name=f"Extra parking {i}",
                spot_count=1,
                type=ParkingType.PARACICLO,
                operating_hours=None,
                geometry=from_shape(Point(1 + i * 0.1, 1), srid=4326),
            )
            session.add(row)
            session.flush()
            extra_parking_ids.append(row.id)
        session.commit()

    try:
        with SessionLocal() as session:
            first_page = list_support_points(session, page=1, page_size=10, bbox=BBOX)

        resource_types_on_page = {f.properties.resource_type for f in first_page.features}
        assert resource_types_on_page == {"parking", "station", "rest_point"}
    finally:
        with SessionLocal() as session:
            session.query(BikeParking).filter(BikeParking.id.in_(extra_parking_ids)).delete(
                synchronize_session=False
            )
            session.commit()


def test_list_support_points_only_fetches_full_rows_for_the_requested_page(
    support_point_fixtures, monkeypatch
):
    """The page-size cap must hold at the DB-fetch level, not just on the
    returned response — regression test for the aggregation previously
    pulling every matching row into Python before slicing to a page."""
    real_fetch_page_rows = support_points_service._fetch_page_rows
    seen_page_ids = []

    def spy_fetch_page_rows(session, page_ids):
        seen_page_ids.append(page_ids)
        return real_fetch_page_rows(session, page_ids)

    monkeypatch.setattr(support_points_service, "_fetch_page_rows", spy_fetch_page_rows)

    with SessionLocal() as session:
        list_support_points(session, page=1, page_size=2, bbox=BBOX)

    assert len(seen_page_ids) == 1
    assert len(seen_page_ids[0]) == 2  # capped to page_size, not the total of 3


def test_list_support_points_bbox_matching_nothing_returns_empty_collection(
    support_point_fixtures,
):
    empty_bbox = (20.0, 20.0, 21.0, 21.0)
    with SessionLocal() as session:
        result = list_support_points(session, page=1, page_size=50, bbox=empty_bbox)

    assert result.features == []
    assert result.meta.total == 0
    assert result.meta.total_pages == 0
    assert result.meta.total_by_type == {"parking": 0, "station": 0, "rest_point": 0}


def test_list_support_points_page_beyond_total_pages_returns_empty_features(
    support_point_fixtures,
):
    with SessionLocal() as session:
        result = list_support_points(session, page=99, page_size=2, bbox=BBOX)

    assert result.features == []
    assert result.meta.total == 3
    assert result.meta.total_pages == 2
