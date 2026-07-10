import json
import logging

import pytest
from shapely.geometry import Point

from app.parking.models import ParkingType
from app.routes.models import RouteCategory
from app.stations.models import StationStatus
from scripts.ingest import (
    SkippableRowError,
    build_rows,
    clean_str,
    extract_image_urls,
    map_category,
    map_parking_type,
    normalize_status,
    parse_int,
    parse_length_km,
    require_name,
    resolve_source_id,
    split_neighborhoods,
    synthetic_source_id,
)


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("  1.1", 1.1),
        ("  1,5", 1.5),
        ("  1.3 Km", 1.3),
        ("  0,8km", 0.8),
        (None, None),
        ("", None),
    ],
)
def test_parse_length_km(raw, expected):
    assert parse_length_km(raw) == expected


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("  Bom Jardim, Siqueira", ["Bom Jardim", "Siqueira"]),
        ("  Passaré", ["Passaré"]),
        (None, []),
        ("", []),
    ],
)
def test_split_neighborhoods(raw, expected):
    assert split_neighborhoods(raw) == expected


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("  Bidirecional  ", "Bidirecional"),
        ("  -  ", None),
        ("", None),
        (None, None),
    ],
)
def test_clean_str(raw, expected):
    assert clean_str(raw) == expected


def test_map_category_known_values():
    assert map_category("Ciclofaixas") == RouteCategory.CICLOFAIXA
    assert map_category("Ciclovias") == RouteCategory.CICLOVIA
    assert map_category("Ciclorrotas") == RouteCategory.CICLORROTA
    assert map_category("Passeios compartilhados") == RouteCategory.PASSEIO_COMPARTILHADO


def test_map_category_unknown_value_raises():
    with pytest.raises(ValueError):
        map_category("Rota Nova Inventada")


def test_map_parking_type_known_values():
    assert map_parking_type("Paraciclo") == ParkingType.PARACICLO
    assert map_parking_type("Bicicletário") == ParkingType.BICICLETARIO


def test_map_parking_type_unknown_value_raises():
    with pytest.raises(ValueError):
        map_parking_type("Garagem")


def test_normalize_status_distinct_values():
    assert normalize_status("EXISTENTE") == StationStatus.EXISTENTE
    assert normalize_status("EXISTENTE 3.0") == StationStatus.EXISTENTE_3_0


def test_normalize_status_unknown_value_raises():
    with pytest.raises(ValueError):
        normalize_status("REMOVIDA")


def test_extract_image_urls_single_img():
    html = '<img src="https://example.com/a.jpg" height="200" />'
    assert extract_image_urls(html) == ["https://example.com/a.jpg"]


def test_extract_image_urls_multiple_imgs():
    html = (
        '<img src="https://example.com/a.jpg" /><br><br>'
        '<img src="https://example.com/b.jpg" />'
    )
    assert extract_image_urls(html) == [
        "https://example.com/a.jpg",
        "https://example.com/b.jpg",
    ]


def test_extract_image_urls_empty():
    assert extract_image_urls(None) == []
    assert extract_image_urls("") == []


def test_extract_image_urls_never_returns_raw_html():
    html = '<img src="https://example.com/a.jpg" /><script>alert(1)</script>'
    urls = extract_image_urls(html)
    assert all("<" not in url and ">" not in url for url in urls)


def test_synthetic_source_id_is_deterministic():
    geom = Point(-38.5, -3.7)
    assert synthetic_source_id("Estação X", geom) == synthetic_source_id("Estação X", geom)


def test_synthetic_source_id_changes_with_geometry():
    name = "Estação X"
    first = synthetic_source_id(name, Point(-38.5, -3.7))
    second = synthetic_source_id(name, Point(-38.6, -3.7))
    assert first != second


def test_synthetic_source_id_changes_with_name():
    geom = Point(-38.5, -3.7)
    assert synthetic_source_id("Estação X", geom) != synthetic_source_id("Estação Y", geom)


def test_resolve_source_id_uses_native_when_present():
    geom = Point(-38.5, -3.7)
    assert resolve_source_id("42", "Some Name", geom) == "42"


def test_resolve_source_id_falls_back_to_synthetic_when_blank():
    geom = Point(-38.5, -3.7)
    expected = synthetic_source_id("Some Name", geom)
    assert resolve_source_id("", "Some Name", geom) == expected
    assert resolve_source_id(None, "Some Name", geom) == expected


def test_require_name_raises_skippable_error_on_blank():
    with pytest.raises(SkippableRowError):
        require_name("  ", "Nome")
    with pytest.raises(SkippableRowError):
        require_name(None, "Nome")


def test_parse_int_non_numeric_placeholder_returns_none_and_warns(caplog):
    with caplog.at_level(logging.WARNING):
        result = parse_int("S/N")
    assert result is None
    assert "Could not parse integer" in caplog.text


def _write_geojson(path, features):
    path.write_text(
        json.dumps({"type": "FeatureCollection", "features": features}), encoding="utf-8"
    )


def test_build_rows_skips_feature_with_malformed_geometry(tmp_path, caplog):
    path = tmp_path / "features.geojson"
    _write_geojson(
        path,
        [
            {
                "type": "Feature",
                "properties": {"name": "ok"},
                "geometry": {"type": "Point", "coordinates": [-38.5, -3.7]},
            },
            {"type": "Feature", "properties": {"name": "bad"}, "geometry": None},
        ],
    )

    def row_fn(props, geom):
        return {"name": props["name"]}

    with caplog.at_level(logging.WARNING):
        rows = build_rows(path, row_fn)

    assert [row["name"] for row in rows] == ["ok"]
    assert "Skipping feature" in caplog.text


def test_build_rows_skips_feature_with_missing_required_field(tmp_path):
    path = tmp_path / "features.geojson"
    _write_geojson(
        path,
        [
            {
                "type": "Feature",
                "properties": {"name": "Valid"},
                "geometry": {"type": "Point", "coordinates": [-38.5, -3.7]},
            },
            {
                "type": "Feature",
                "properties": {"name": "  "},
                "geometry": {"type": "Point", "coordinates": [-38.6, -3.7]},
            },
        ],
    )

    def row_fn(props, geom):
        name = require_name(props.get("name"), "name")
        return {"name": name}

    rows = build_rows(path, row_fn)

    assert [row["name"] for row in rows] == ["Valid"]


def test_build_rows_propagates_value_error_for_unmapped_enum(tmp_path):
    path = tmp_path / "features.geojson"
    _write_geojson(
        path,
        [
            {
                "type": "Feature",
                "properties": {},
                "geometry": {"type": "Point", "coordinates": [-38.5, -3.7]},
            }
        ],
    )

    def row_fn(props, geom):
        raise ValueError("unmapped enum")

    with pytest.raises(ValueError):
        build_rows(path, row_fn)
