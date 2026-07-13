from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.orm import Session

from app.parking.schemas import BikeParkingFeature, BikeParkingFeatureCollection, BikeParkingQuery
from app.parking.service import get_parking, list_parking
from app.shared.auth import verify_api_key
from app.shared.database import get_db
from app.shared.middleware import api_scope, default_limit, limiter

router = APIRouter(prefix="/parking", tags=["parking"], dependencies=[Depends(verify_api_key)])


@router.get("", response_model=BikeParkingFeatureCollection)
@limiter.shared_limit(default_limit, api_scope)
def list_bike_parking(
    request: Request,
    query: Annotated[BikeParkingQuery, Query()],
    session: Session = Depends(get_db),
) -> BikeParkingFeatureCollection:
    return list_parking(
        session,
        page=query.page,
        page_size=query.page_size,
        parking_type=query.type,
        bbox=query.bbox_tuple,
    )


@router.get("/{parking_id}", response_model=BikeParkingFeature)
@limiter.shared_limit(default_limit, api_scope)
def get_bike_parking(
    request: Request, parking_id: int, session: Session = Depends(get_db)
) -> BikeParkingFeature:
    feature = get_parking(session, parking_id)
    if feature is None:
        raise HTTPException(status_code=404, detail="Bike parking not found")
    return feature
