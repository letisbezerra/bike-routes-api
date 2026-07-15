from unittest.mock import patch

from geoalchemy2.shape import from_shape
from shapely.geometry import Point

from app.stations.models import BikeShareStation, StationStatus
from app.stations.service import get_station, list_stations


def _fake_station(station_id: int = 1) -> BikeShareStation:
    return BikeShareStation(
        id=station_id,
        source_id="123",
        name="Estação Teste",
        neighborhood="Centro",
        regional="Regional I",
        inaugurated_at=None,
        status=StationStatus.EXISTENTE,
        sponsor=None,
        current_slots=15,
        station_type=None,
        geometry=from_shape(Point(-38.5, -3.7), srid=4326),
    )


def test_list_stations_builds_correct_pagination_meta():
    with patch("app.stations.service.list_paginated", return_value=([_fake_station()], 101)):
        result = list_stations(session=None, page=2, page_size=50)
    assert result.meta.page == 2
    assert result.meta.page_size == 50
    assert result.meta.total == 101
    assert result.meta.total_pages == 3


def test_list_stations_pagination_meta_zero_total():
    with patch("app.stations.service.list_paginated", return_value=([], 0)):
        result = list_stations(session=None, page=1, page_size=50)
    assert result.meta.total == 0
    assert result.meta.total_pages == 0
    assert result.features == []


def test_list_stations_converts_rows_to_valid_features():
    with patch("app.stations.service.list_paginated", return_value=([_fake_station(7)], 1)):
        result = list_stations(session=None, page=1, page_size=50)
    feature = result.features[0]
    assert feature.type == "Feature"
    assert feature.geometry["type"] == "Point"
    assert feature.properties.id == 7
    assert feature.properties.status == StationStatus.EXISTENTE
    assert feature.properties.neighborhood == "Centro"


def test_get_station_returns_none_when_repository_returns_none():
    with patch("app.stations.service.get_by_id", return_value=None):
        assert get_station(session=None, station_id=999) is None


def test_get_station_returns_feature_for_existing_row():
    with patch("app.stations.service.get_by_id", return_value=_fake_station(5)):
        feature = get_station(session=None, station_id=5)
    assert feature is not None
    assert feature.properties.id == 5
