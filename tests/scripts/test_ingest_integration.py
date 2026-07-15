import json

import pytest
from geoalchemy2.shape import from_shape
from shapely.geometry import Point
from sqlalchemy import func, select, text

from app.leisure_routes.models import LeisureRoute
from app.parking.models import BikeParking
from app.rest_points.models import RestPoint
from app.routes.models import BikeRoute
from app.shared.database import SessionLocal
from app.stations.models import BikeShareStation
from scripts.ingest import DATA_DIR, build_leisure_routes, main, upsert_and_prune

EXPECTED_COUNTS = {
    BikeRoute: 447,
    BikeParking: 301,
    BikeShareStation: 267,
    RestPoint: 18,
    LeisureRoute: 3,
}


def _restore_leisure_routes():
    with SessionLocal() as session:
        rows = build_leisure_routes(DATA_DIR / "rotas_ciclofaixa_de_lazer.geojson")
        upsert_and_prune(session, LeisureRoute, rows)
        session.commit()


def test_ingestion_row_counts_match_source_features():
    main()
    with SessionLocal() as session:
        for model, expected in EXPECTED_COUNTS.items():
            count = session.execute(select(func.count()).select_from(model)).scalar()
            assert count == expected, f"{model.__tablename__}: expected {expected}, got {count}"


def test_ingestion_twice_is_idempotent():
    main()
    with SessionLocal() as session:
        before = {
            model: sorted(session.execute(select(model.id, model.source_id)).all())
            for model in EXPECTED_COUNTS
        }

    main()
    with SessionLocal() as session:
        after = {
            model: sorted(session.execute(select(model.id, model.source_id)).all())
            for model in EXPECTED_COUNTS
        }
        counts = {
            model: session.execute(select(func.count()).select_from(model)).scalar()
            for model in EXPECTED_COUNTS
        }

    for model, expected_count in EXPECTED_COUNTS.items():
        assert before[model] == after[model], f"{model.__tablename__}: ids not stable"
        assert counts[model] == expected_count


def test_orphan_cleanup_removes_rows_missing_from_batch(tmp_path):
    main()

    source_path = DATA_DIR / "rotas_ciclofaixa_de_lazer.geojson"
    with source_path.open(encoding="utf-8") as f:
        data = json.load(f)
    reduced_path = tmp_path / "leisure_reduced.geojson"
    reduced_data = {**data, "features": data["features"][:2]}
    reduced_path.write_text(json.dumps(reduced_data), encoding="utf-8")

    try:
        with SessionLocal() as session:
            rows = build_leisure_routes(reduced_path)
            upsert_and_prune(session, LeisureRoute, rows)
            session.commit()

        with SessionLocal() as session:
            count = session.execute(select(func.count()).select_from(LeisureRoute)).scalar()
        assert count == 2
    finally:
        _restore_leisure_routes()
        with SessionLocal() as session:
            count = session.execute(select(func.count()).select_from(LeisureRoute)).scalar()
        assert count == 3


def test_upsert_and_prune_prunes_everything_on_empty_batch():
    main()
    try:
        with SessionLocal() as session:
            upsert_and_prune(session, LeisureRoute, [])
            session.commit()

        with SessionLocal() as session:
            count = session.execute(select(func.count()).select_from(LeisureRoute)).scalar()
        assert count == 0
    finally:
        _restore_leisure_routes()
        with SessionLocal() as session:
            count = session.execute(select(func.count()).select_from(LeisureRoute)).scalar()
        assert count == 3


def test_upsert_and_prune_raises_on_duplicate_source_id_in_batch():
    rows = [
        {
            "source_id": "dup",
            "name": "A",
            "support_count": 1,
            "geometry": from_shape(Point(-38.5, -3.7), srid=4326),
        },
        {
            "source_id": "dup",
            "name": "B",
            "support_count": 2,
            "geometry": from_shape(Point(-38.6, -3.7), srid=4326),
        },
    ]
    with SessionLocal() as session:
        with pytest.raises(ValueError):
            upsert_and_prune(session, LeisureRoute, rows)
        session.rollback()


def test_bike_share_stations_geometry_is_valid_wgs84_in_fortaleza():
    main()
    with SessionLocal() as session:
        rows = session.execute(
            text(
                "SELECT ST_SRID(geometry), ST_X(geometry), ST_Y(geometry) "
                "FROM bike_share_stations"
            )
        ).all()
    assert all(srid == 4326 for srid, _, _ in rows)
    assert all(-38.63 <= lon <= -38.42 for _, lon, _ in rows)
    assert all(-3.87 <= lat <= -3.69 for _, _, lat in rows)


def test_bike_share_station_geometry_matches_known_reprojected_pair():
    # source_id "1" (data/raw/estacoes_bicicletar.geojson, ID=1) is EPSG:4674
    # [-38.510288, -3.732311]. SIRGAS2000 and WGS84 are treated as coincident
    # by PROJ for Fortaleza (confirmed directly: zero delta), so the
    # reprojected EPSG:4326 coordinate matches the raw source pair.
    main()
    with SessionLocal() as session:
        lon, lat = session.execute(
            text(
                "SELECT ST_X(geometry), ST_Y(geometry) "
                "FROM bike_share_stations WHERE source_id = '1'"
            )
        ).one()
    assert lon == pytest.approx(-38.510288, abs=1e-6)
    assert lat == pytest.approx(-3.732311, abs=1e-6)
