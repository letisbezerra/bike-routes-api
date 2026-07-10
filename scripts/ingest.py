"""Reads data/raw/*.geojson, cleans/normalizes per docs/DATA_SOURCES.md, and
upserts into PostGIS. Manual trigger only — run with `uv run python -m scripts.ingest`.
"""

import hashlib
import json
import logging
import re
from datetime import date, datetime
from pathlib import Path
from typing import Callable

from bs4 import BeautifulSoup
from geoalchemy2.shape import from_shape
from pyproj import Transformer
from shapely.geometry import shape
from shapely.geometry.base import BaseGeometry
from shapely.ops import transform
from shapely.wkt import dumps as wkt_dumps
from shapely.wkt import loads as wkt_loads
from sqlalchemy import delete
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.leisure_routes.models import LeisureRoute
from app.parking.models import BikeParking, ParkingType
from app.rest_points.models import RestPoint
from app.routes.models import BikeRoute, RouteCategory
from app.shared.database import SessionLocal
from app.stations.models import BikeShareStation, StationStatus

logger = logging.getLogger(__name__)

DATA_DIR = Path(__file__).resolve().parent.parent / "data" / "raw"

_KM_SUFFIX_RE = re.compile(r"km$", re.IGNORECASE)

_CATEGORY_MAP = {
    "Ciclofaixas": RouteCategory.CICLOFAIXA,
    "Ciclovias": RouteCategory.CICLOVIA,
    "Ciclorrotas": RouteCategory.CICLORROTA,
    "Passeios compartilhados": RouteCategory.PASSEIO_COMPARTILHADO,
}

_PARKING_TYPE_MAP = {
    "Paraciclo": ParkingType.PARACICLO,
    "Bicicletário": ParkingType.BICICLETARIO,
}

_STATUS_MAP = {
    "EXISTENTE": StationStatus.EXISTENTE,
    "EXISTENTE 3.0": StationStatus.EXISTENTE_3_0,
}


class SkippableRowError(Exception):
    """A single row is unusable (bad geometry, missing required field) —
    skipped with a warning, not a batch failure. Distinct from ValueError,
    which map_category/map_parking_type/normalize_status raise to mean the
    opposite: an unmapped enum value means the code is out of date, so the
    whole run should stop rather than silently miscategorize data."""


# --- cleaning / normalization -----------------------------------------------


def clean_str(raw: str | None) -> str | None:
    """Strip whitespace; blank or "-" placeholder values become None."""
    if raw is None:
        return None
    value = raw.strip()
    if not value or value == "-":
        return None
    return value


def require_name(raw: str | None, field_label: str) -> str:
    name = clean_str(raw)
    if name is None:
        raise SkippableRowError(f"missing required field {field_label!r}")
    return name


def parse_length_km(raw: str | None) -> float | None:
    """Handles the mixed formats in Extensão (km): comma decimals and a
    trailing km/Km unit (docs/DATA_SOURCES.md #10)."""
    value = clean_str(raw)
    if value is None:
        return None
    value = _KM_SUFFIX_RE.sub("", value).strip()
    return float(value.replace(",", "."))


def split_neighborhoods(raw: str | None) -> list[str]:
    """Bairros is comma-separated when a route spans more than one
    neighborhood (docs/DATA_SOURCES.md #11)."""
    value = clean_str(raw)
    if value is None:
        return []
    return [part.strip() for part in value.split(",") if part.strip()]


def parse_int(raw) -> int | None:
    if raw is None:
        return None
    if isinstance(raw, str):
        raw = clean_str(raw)
        if raw is None:
            return None
    try:
        return int(float(raw))
    except (TypeError, ValueError):
        logger.warning("Could not parse integer value %r — storing as null", raw)
        return None


def parse_iso_datetime(raw: str | None) -> datetime | None:
    value = clean_str(raw)
    if value is None:
        return None
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def parse_br_date(raw: str | None) -> date | None:
    value = clean_str(raw)
    if value is None:
        return None
    return datetime.strptime(value, "%d/%m/%Y").date()


def map_category(raw: str | None) -> RouteCategory:
    key = clean_str(raw)
    try:
        return _CATEGORY_MAP[key]
    except KeyError:
        raise ValueError(f"Unmapped route category: {raw!r}") from None


def map_parking_type(raw: str | None) -> ParkingType:
    key = clean_str(raw)
    try:
        return _PARKING_TYPE_MAP[key]
    except KeyError:
        raise ValueError(f"Unmapped parking type: {raw!r}") from None


def normalize_status(raw: str | None) -> StationStatus:
    key = clean_str(raw)
    key = key.upper() if key else key
    try:
        return _STATUS_MAP[key]
    except KeyError:
        raise ValueError(f"Unmapped station status: {raw!r}") from None


def extract_image_urls(raw_html: str | None) -> list[str]:
    """Extracts every <img src> from the raw Imagem HTML. The raw HTML is
    never persisted — known stored-XSS risk (docs/DATA_SOURCES.md #8)."""
    if not raw_html:
        return []
    soup = BeautifulSoup(raw_html, "html.parser")
    return [img["src"] for img in soup.find_all("img") if img.get("src")]


# --- geometry -----------------------------------------------------------


def round_geometry(geometry: BaseGeometry, precision: int = 6) -> BaseGeometry:
    """Rounds coordinates to `precision` decimal places (~0.11m at 6) so
    floating-point noise can't change a synthetic source_id between runs."""
    return wkt_loads(wkt_dumps(geometry, rounding_precision=precision))


def build_geometry(raw_geometry: dict, transformer: Transformer | None = None) -> BaseGeometry:
    geom = shape(raw_geometry)
    if transformer is not None:
        geom = transform(transformer.transform, geom)
    return round_geometry(geom)


def synthetic_source_id(name: str | None, geometry: BaseGeometry) -> str:
    """Deterministic id for sources with no native Id/ID field, or a blank
    one — stable across re-ingestion as long as name/geometry don't change."""
    key = f"{(name or '').strip().lower()}|{geometry.wkt}"
    return hashlib.sha256(key.encode("utf-8")).hexdigest()[:16]


def resolve_source_id(native_id: str | None, name: str | None, geometry: BaseGeometry) -> str:
    """Uniform id-or-synthetic rule for every table (docs/specs/02-data-ingestion.md
    'Source id strategy'): a non-blank native id wins, otherwise a stable hash."""
    return clean_str(native_id) or synthetic_source_id(name, geometry)


def _read_features(path: Path) -> list[dict]:
    with path.open(encoding="utf-8") as f:
        return json.load(f)["features"]


# --- per-resource row builders -------------------------------------------


def build_rows(
    path: Path,
    row_fn: Callable[[dict, BaseGeometry], dict],
    transformer: Transformer | None = None,
) -> list[dict]:
    """Shared shell for every resource: read features, build geometry, map
    to a row via row_fn. A single bad feature (unparseable geometry, missing
    required field) is logged and skipped, not a batch failure — except an
    unmapped enum (ValueError), which means the code needs updating and
    should stop the whole run (docs/specs/02-data-ingestion.md 'Error/edge
    cases')."""
    rows = []
    for feature in _read_features(path):
        props = feature["properties"]
        try:
            geom = build_geometry(feature["geometry"], transformer=transformer)
            rows.append(row_fn(props, geom))
        except ValueError:
            raise
        except Exception as exc:
            logger.warning("Skipping feature in %s: %s", path.name, exc)
    return rows


def _bike_route_row(props: dict, geom: BaseGeometry) -> dict:
    name = require_name(props.get("Nome"), "Nome")
    return {
        "source_id": resolve_source_id(props.get("Id"), name, geom),
        "name": name,
        "category": map_category(props.get("Tipologia")),
        "length_km": parse_length_km(props.get("Extensão (km)")),
        "segment": clean_str(props.get("Trecho")),
        "road_position": clean_str(props.get("Posição na via")),
        "direction": clean_str(props.get("Sentido de circulação")),
        "pavement": clean_str(props.get("Pavimento")),
        "separation_element": clean_str(props.get("Elementos de separação")),
        "implemented_at": parse_iso_datetime(props.get("Data de implantação")),
        "neighborhoods": split_neighborhoods(props.get("Bairros")),
        "reference_year": parse_int(props.get("anoref")),
        "geometry": from_shape(geom, srid=4326),
    }


def build_bike_routes(path: Path) -> list[dict]:
    return build_rows(path, _bike_route_row)


def _bike_parking_row(props: dict, geom: BaseGeometry) -> dict:
    name = require_name(props.get("Local"), "Local")
    return {
        "source_id": synthetic_source_id(name, geom),
        "name": name,
        "spot_count": parse_int(props.get("Quantidade de paraciclos")),
        "type": map_parking_type(props.get("Tipo")),
        "operating_hours": clean_str(props.get("Horário de funcionamento")),
        "geometry": from_shape(geom, srid=4326),
    }


def build_bike_parking(path: Path) -> list[dict]:
    return build_rows(path, _bike_parking_row)


def _bike_share_station_row(props: dict, geom: BaseGeometry) -> dict:
    name = require_name(props.get("NOME"), "NOME")
    raw_id = props.get("ID")
    return {
        "source_id": resolve_source_id(str(raw_id) if raw_id is not None else None, name, geom),
        "name": name,
        "neighborhood": clean_str(props.get("BAIRRO")),
        "regional": clean_str(props.get("REGIONAL")),
        "inaugurated_at": parse_br_date(props.get("DATA INAUGURAÇÃO")),
        "status": normalize_status(props.get("STATUS")),
        "sponsor": clean_str(props.get("PATROCINADOR")),
        "current_slots": parse_int(props.get("VAGAS ATUAIS")),
        "station_type": clean_str(props.get("TIPO")),
        "geometry": from_shape(geom, srid=4326),
    }


def build_bike_share_stations(path: Path) -> list[dict]:
    transformer = Transformer.from_crs("EPSG:4674", "EPSG:4326", always_xy=True)
    return build_rows(path, _bike_share_station_row, transformer=transformer)


def _rest_point_row(props: dict, geom: BaseGeometry) -> dict:
    name = require_name(props.get("Nome"), "Nome")
    return {
        "source_id": synthetic_source_id(name, geom),
        "name": name,
        "image_urls": extract_image_urls(props.get("Imagem")),
        "geometry": from_shape(geom, srid=4326),
    }


def build_rest_points(path: Path) -> list[dict]:
    return build_rows(path, _rest_point_row)


def _leisure_route_row(props: dict, geom: BaseGeometry) -> dict:
    name = require_name(props.get("Rota"), "Rota")
    return {
        "source_id": synthetic_source_id(name, geom),
        "name": name,
        "support_count": parse_int(props.get("n.apoios")),
        "geometry": from_shape(geom, srid=4326),
    }


def build_leisure_routes(path: Path) -> list[dict]:
    return build_rows(path, _leisure_route_row)


# --- upsert + orphan cleanup ----------------------------------------------


def _check_no_duplicate_source_ids(model: type, rows: list[dict]) -> None:
    """A collision here means two different features hashed to the same
    synthetic id (or share a native id) — a real data anomaly worth failing
    loudly on, not silently dropping one side of."""
    seen: dict[str, dict] = {}
    for row in rows:
        source_id = row["source_id"]
        clash = seen.get(source_id)
        if clash is not None:
            raise ValueError(
                f"{model.__tablename__}: duplicate source_id {source_id!r} for "
                f"{clash['name']!r} and {row['name']!r}"
            )
        seen[source_id] = row


def upsert_and_prune(session: Session, model: type, rows: list[dict]) -> None:
    """Upserts every row by source_id, then deletes any existing row whose
    source_id isn't in this batch — re-ingestion never accumulates
    duplicates or stale rows, even when a source legitimately has zero
    features left (docs/specs/02-data-ingestion.md)."""
    table = model.__table__

    if rows:
        _check_no_duplicate_source_ids(model, rows)
        stmt = insert(table).values(rows)
        update_columns = {
            column_name: stmt.excluded[column_name]
            for column_name in rows[0]
            if column_name not in ("id", "source_id")
        }
        stmt = stmt.on_conflict_do_update(index_elements=["source_id"], set_=update_columns)
        session.execute(stmt)

    current_ids = [row["source_id"] for row in rows]
    session.execute(delete(table).where(table.c.source_id.notin_(current_ids)))


def main() -> None:
    with SessionLocal() as session:
        upsert_and_prune(
            session, BikeRoute, build_bike_routes(DATA_DIR / "fortaleza_ciclovias.geojson")
        )
        upsert_and_prune(
            session,
            BikeParking,
            build_bike_parking(DATA_DIR / "estacionamentos_de_bicicleta.geojson"),
        )
        upsert_and_prune(
            session,
            BikeShareStation,
            build_bike_share_stations(DATA_DIR / "estacoes_bicicletar.geojson"),
        )
        upsert_and_prune(
            session, RestPoint, build_rest_points(DATA_DIR / "pontos_de_descanso.geojson")
        )
        upsert_and_prune(
            session,
            LeisureRoute,
            build_leisure_routes(DATA_DIR / "rotas_ciclofaixa_de_lazer.geojson"),
        )
        session.commit()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    main()
