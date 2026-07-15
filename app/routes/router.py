from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.orm import Session

from app.routes.schemas import BikeRouteFeature, BikeRouteFeatureCollection, BikeRouteQuery
from app.routes.service import get_route, list_routes
from app.shared.auth import verify_api_key
from app.shared.database import get_db
from app.shared.middleware import api_scope, default_limit, limiter
from app.shared.openapi import LIST_RESPONSES, detail_responses

router = APIRouter(prefix="/routes", tags=["routes"], dependencies=[Depends(verify_api_key)])


@router.get(
    "",
    response_model=BikeRouteFeatureCollection,
    summary="List bike routes",
    description="Paginated, bbox-filterable list of Fortaleza's ciclovias/ciclofaixas/"
    "ciclorrotas/passeios compartilhados. Filter by `category` and/or `neighborhood`.",
    responses=LIST_RESPONSES,
)
@limiter.shared_limit(default_limit, api_scope)
def list_bike_routes(
    request: Request,
    query: Annotated[BikeRouteQuery, Query()],
    session: Session = Depends(get_db),
) -> BikeRouteFeatureCollection:
    return list_routes(
        session,
        page=query.page,
        page_size=query.page_size,
        category=query.category,
        neighborhood=query.neighborhood,
        bbox=query.bbox_tuple,
    )


@router.get(
    "/{route_id}",
    response_model=BikeRouteFeature,
    summary="Get a bike route by id",
    description="Single bike route as a GeoJSON Feature.",
    responses=detail_responses("Bike route not found"),
)
@limiter.shared_limit(default_limit, api_scope)
def get_bike_route(
    request: Request, route_id: int, session: Session = Depends(get_db)
) -> BikeRouteFeature:
    feature = get_route(session, route_id)
    if feature is None:
        raise HTTPException(status_code=404, detail="Bike route not found")
    return feature
