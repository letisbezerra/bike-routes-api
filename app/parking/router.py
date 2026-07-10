from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.parking.schemas import BikeParkingFeature, BikeParkingFeatureCollection, BikeParkingQuery
from app.parking.service import get_parking, list_parking
from app.shared.auth import verify_api_key
from app.shared.database import get_db
from app.shared.schemas import parse_bbox

router = APIRouter(prefix="/parking", tags=["parking"], dependencies=[Depends(verify_api_key)])


@router.get("", response_model=BikeParkingFeatureCollection)
def list_bike_parking(
    query: Annotated[BikeParkingQuery, Query()],
    session: Session = Depends(get_db),
) -> BikeParkingFeatureCollection:
    bbox = parse_bbox(query.bbox) if query.bbox else None
    return list_parking(
        session,
        page=query.page,
        page_size=query.page_size,
        type=query.type,
        bbox=bbox,
    )


@router.get("/{parking_id}", response_model=BikeParkingFeature)
def get_bike_parking(parking_id: int, session: Session = Depends(get_db)) -> BikeParkingFeature:
    feature = get_parking(session, parking_id)
    if feature is None:
        raise HTTPException(status_code=404, detail="Bike parking not found")
    return feature
