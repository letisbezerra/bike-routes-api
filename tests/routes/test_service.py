from unittest.mock import patch

from geoalchemy2.shape import from_shape
from shapely.geometry import LineString

from app.routes.models import BikeRoute, RouteCategory
from app.routes.service import get_route, list_routes


def _fake_route(route_id: int = 1) -> BikeRoute:
    return BikeRoute(
        id=route_id,
        source_id="123",
        name="Av. Teste",
        category=RouteCategory.CICLOVIA,
        length_km=1.5,
        segment=None,
        road_position=None,
        direction=None,
        pavement=None,
        separation_element=None,
        implemented_at=None,
        neighborhoods=["Centro"],
        reference_year=2024,
        geometry=from_shape(LineString([(-38.5, -3.7), (-38.51, -3.71)]), srid=4326),
    )


def test_list_routes_builds_correct_pagination_meta():
    with patch("app.routes.service.list_paginated", return_value=([_fake_route()], 101)):
        result = list_routes(session=None, page=2, page_size=50)
    assert result.meta.page == 2
    assert result.meta.page_size == 50
    assert result.meta.total == 101
    assert result.meta.total_pages == 3


def test_list_routes_pagination_meta_zero_total():
    with patch("app.routes.service.list_paginated", return_value=([], 0)):
        result = list_routes(session=None, page=1, page_size=50)
    assert result.meta.total == 0
    assert result.meta.total_pages == 0
    assert result.features == []


def test_list_routes_converts_rows_to_valid_features():
    with patch("app.routes.service.list_paginated", return_value=([_fake_route(7)], 1)):
        result = list_routes(session=None, page=1, page_size=50)
    feature = result.features[0]
    assert feature.type == "Feature"
    assert feature.geometry["type"] == "LineString"
    assert feature.properties.id == 7
    assert feature.properties.category == RouteCategory.CICLOVIA
    assert feature.properties.neighborhoods == ["Centro"]


def test_get_route_returns_none_when_repository_returns_none():
    with patch("app.routes.service.get_by_id", return_value=None):
        assert get_route(session=None, route_id=999) is None


def test_get_route_returns_feature_for_existing_row():
    with patch("app.routes.service.get_by_id", return_value=_fake_route(5)):
        feature = get_route(session=None, route_id=5)
    assert feature is not None
    assert feature.properties.id == 5
