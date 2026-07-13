from unittest.mock import patch

from geoalchemy2.shape import from_shape
from shapely.geometry import Point

from app.rest_points.models import RestPoint
from app.rest_points.service import get_rest_point, list_rest_points


def _fake_rest_point(rest_point_id: int = 1, image_urls: list[str] | None = None) -> RestPoint:
    return RestPoint(
        id=rest_point_id,
        source_id="123",
        name="Ponto Teste",
        image_urls=image_urls if image_urls is not None else ["https://example.com/a.jpg"],
        geometry=from_shape(Point(-38.5, -3.7), srid=4326),
    )


def test_list_rest_points_builds_correct_pagination_meta():
    with patch(
        "app.rest_points.service.list_paginated", return_value=([_fake_rest_point()], 101)
    ):
        result = list_rest_points(session=None, page=2, page_size=50)
    assert result.meta.page == 2
    assert result.meta.page_size == 50
    assert result.meta.total == 101
    assert result.meta.total_pages == 3


def test_list_rest_points_pagination_meta_zero_total():
    with patch("app.rest_points.service.list_paginated", return_value=([], 0)):
        result = list_rest_points(session=None, page=1, page_size=50)
    assert result.meta.total == 0
    assert result.meta.total_pages == 0
    assert result.features == []


def test_list_rest_points_converts_rows_to_valid_features():
    with patch(
        "app.rest_points.service.list_paginated", return_value=([_fake_rest_point(7)], 1)
    ):
        result = list_rest_points(session=None, page=1, page_size=50)
    feature = result.features[0]
    assert feature.type == "Feature"
    assert feature.geometry["type"] == "Point"
    assert feature.properties.id == 7


def test_image_urls_drops_disallowed_schemes():
    mixed = [
        "https://example.com/a.jpg",
        "http://example.com/b.jpg",
        "javascript:alert(1)",
        "data:text/html,<script>alert(1)</script>",
        "ftp://example.com/c.jpg",
    ]
    with patch(
        "app.rest_points.service.list_paginated",
        return_value=([_fake_rest_point(1, image_urls=mixed)], 1),
    ):
        result = list_rest_points(session=None, page=1, page_size=50)
    assert result.features[0].properties.image_urls == [
        "https://example.com/a.jpg",
        "http://example.com/b.jpg",
    ]


def test_get_rest_point_returns_none_when_repository_returns_none():
    with patch("app.rest_points.service.get_by_id", return_value=None):
        assert get_rest_point(session=None, rest_point_id=999) is None


def test_get_rest_point_returns_feature_for_existing_row():
    with patch("app.rest_points.service.get_by_id", return_value=_fake_rest_point(5)):
        feature = get_rest_point(session=None, rest_point_id=5)
    assert feature is not None
    assert feature.properties.id == 5
