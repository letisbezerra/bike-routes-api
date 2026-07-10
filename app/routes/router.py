from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.routes.schemas import BikeRouteFeature, BikeRouteFeatureCollection, BikeRouteQuery
from app.routes.service import get_route, list_routes
from app.shared.auth import verify_api_key
from app.shared.database import get_db
from app.shared.schemas import parse_bbox

router = APIRouter(prefix="/routes", tags=["routes"], dependencies=[Depends(verify_api_key)])


@router.get("", response_model=BikeRouteFeatureCollection)
def list_bike_routes(
    query: Annotated[BikeRouteQuery, Query()],
    session: Session = Depends(get_db),
) -> BikeRouteFeatureCollection:
    bbox = parse_bbox(query.bbox) if query.bbox else None
    return list_routes(
        session,
        page=query.page,
        page_size=query.page_size,
        category=query.category,
        neighborhood=query.neighborhood,
        bbox=bbox,
    )


@router.get("/{route_id}", response_model=BikeRouteFeature)
def get_bike_route(route_id: int, session: Session = Depends(get_db)) -> BikeRouteFeature:
    feature = get_route(session, route_id)
    if feature is None:
        raise HTTPException(status_code=404, detail="Bike route not found")
    return feature
