from unittest.mock import patch

from geoalchemy2.shape import from_shape
from shapely.geometry import Point

from app.parking.models import BikeParking, ParkingType
from app.parking.service import get_parking, list_parking


def _fake_parking(parking_id: int = 1) -> BikeParking:
    return BikeParking(
        id=parking_id,
        source_id="123",
        name="Estação Teste",
        spot_count=10,
        type=ParkingType.PARACICLO,
        operating_hours="24h",
        geometry=from_shape(Point(-38.5, -3.7), srid=4326),
    )


def test_list_parking_builds_correct_pagination_meta():
    with patch("app.parking.service.list_paginated", return_value=([_fake_parking()], 101)):
        result = list_parking(session=None, page=2, page_size=50)
    assert result.meta.page == 2
    assert result.meta.page_size == 50
    assert result.meta.total == 101
    assert result.meta.total_pages == 3


def test_list_parking_pagination_meta_zero_total():
    with patch("app.parking.service.list_paginated", return_value=([], 0)):
        result = list_parking(session=None, page=1, page_size=50)
    assert result.meta.total == 0
    assert result.meta.total_pages == 0
    assert result.features == []


def test_list_parking_converts_rows_to_valid_features():
    with patch("app.parking.service.list_paginated", return_value=([_fake_parking(7)], 1)):
        result = list_parking(session=None, page=1, page_size=50)
    feature = result.features[0]
    assert feature.type == "Feature"
    assert feature.geometry["type"] == "Point"
    assert feature.properties.id == 7
    assert feature.properties.type == ParkingType.PARACICLO


def test_get_parking_returns_none_when_repository_returns_none():
    with patch("app.parking.service.get_by_id", return_value=None):
        assert get_parking(session=None, parking_id=999) is None


def test_get_parking_returns_feature_for_existing_row():
    with patch("app.parking.service.get_by_id", return_value=_fake_parking(5)):
        feature = get_parking(session=None, parking_id=5)
    assert feature is not None
    assert feature.properties.id == 5
