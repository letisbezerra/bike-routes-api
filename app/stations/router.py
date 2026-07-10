from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.shared.auth import verify_api_key
from app.shared.database import get_db
from app.shared.schemas import parse_bbox
from app.stations.schemas import (
    BikeShareStationFeature,
    BikeShareStationFeatureCollection,
    BikeShareStationQuery,
)
from app.stations.service import get_station, list_stations

router = APIRouter(prefix="/stations", tags=["stations"], dependencies=[Depends(verify_api_key)])


@router.get("", response_model=BikeShareStationFeatureCollection)
def list_bike_share_stations(
    query: Annotated[BikeShareStationQuery, Query()],
    session: Session = Depends(get_db),
) -> BikeShareStationFeatureCollection:
    bbox = parse_bbox(query.bbox) if query.bbox else None
    return list_stations(
        session,
        page=query.page,
        page_size=query.page_size,
        status=query.status,
        neighborhood=query.neighborhood,
        bbox=bbox,
    )


@router.get("/{station_id}", response_model=BikeShareStationFeature)
def get_bike_share_station(
    station_id: int, session: Session = Depends(get_db)
) -> BikeShareStationFeature:
    feature = get_station(session, station_id)
    if feature is None:
        raise HTTPException(status_code=404, detail="Bike share station not found")
    return feature
