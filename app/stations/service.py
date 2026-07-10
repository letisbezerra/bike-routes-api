from math import ceil

from sqlalchemy.orm import Session

from app.shared.geojson import to_geojson_geometry
from app.shared.schemas import PaginationMeta
from app.stations.models import BikeShareStation, StationStatus
from app.stations.repository import get_by_id, list_paginated
from app.stations.schemas import (
    BikeShareStationFeature,
    BikeShareStationFeatureCollection,
    BikeShareStationProperties,
)


def _to_feature(station: BikeShareStation) -> BikeShareStationFeature:
    return BikeShareStationFeature(
        geometry=to_geojson_geometry(station.geometry),
        properties=BikeShareStationProperties.model_validate(station),
    )


def list_stations(
    session: Session,
    *,
    page: int,
    page_size: int,
    status: StationStatus | None = None,
    neighborhood: str | None = None,
    bbox: tuple[float, float, float, float] | None = None,
) -> BikeShareStationFeatureCollection:
    rows, total = list_paginated(
        session,
        page=page,
        page_size=page_size,
        status=status,
        neighborhood=neighborhood,
        bbox=bbox,
    )
    total_pages = ceil(total / page_size) if total else 0
    return BikeShareStationFeatureCollection(
        features=[_to_feature(row) for row in rows],
        meta=PaginationMeta(page=page, page_size=page_size, total=total, total_pages=total_pages),
    )


def get_station(session: Session, station_id: int) -> BikeShareStationFeature | None:
    station = get_by_id(session, station_id)
    if station is None:
        return None
    return _to_feature(station)
