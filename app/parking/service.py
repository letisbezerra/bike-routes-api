from math import ceil

from sqlalchemy.orm import Session

from app.parking.models import BikeParking, ParkingType
from app.parking.repository import get_by_id, list_paginated
from app.parking.schemas import (
    BikeParkingFeature,
    BikeParkingFeatureCollection,
    BikeParkingProperties,
)
from app.shared.geojson import to_geojson_geometry
from app.shared.schemas import PaginationMeta


def _to_feature(parking: BikeParking) -> BikeParkingFeature:
    return BikeParkingFeature(
        geometry=to_geojson_geometry(parking.geometry),
        properties=BikeParkingProperties.model_validate(parking),
    )


def list_parking(
    session: Session,
    *,
    page: int,
    page_size: int,
    parking_type: ParkingType | None = None,
    bbox: tuple[float, float, float, float] | None = None,
) -> BikeParkingFeatureCollection:
    rows, total = list_paginated(
        session, page=page, page_size=page_size, parking_type=parking_type, bbox=bbox
    )
    total_pages = ceil(total / page_size)
    return BikeParkingFeatureCollection(
        features=[_to_feature(row) for row in rows],
        meta=PaginationMeta(page=page, page_size=page_size, total=total, total_pages=total_pages),
    )


def get_parking(session: Session, parking_id: int) -> BikeParkingFeature | None:
    parking = get_by_id(session, parking_id)
    if parking is None:
        return None
    return _to_feature(parking)
