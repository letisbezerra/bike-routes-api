from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.orm import Session

from app.leisure_routes.schemas import (
    LeisureRouteFeature,
    LeisureRouteFeatureCollection,
    LeisureRouteQuery,
)
from app.leisure_routes.service import get_leisure_route, list_leisure_routes
from app.shared.auth import verify_api_key
from app.shared.database import get_db
from app.shared.middleware import api_scope, default_limit, limiter

router = APIRouter(
    prefix="/leisure-routes", tags=["leisure-routes"], dependencies=[Depends(verify_api_key)]
)


@router.get("", response_model=LeisureRouteFeatureCollection)
@limiter.shared_limit(default_limit, api_scope)
def list_leisure_routes_endpoint(
    request: Request,
    query: Annotated[LeisureRouteQuery, Query()],
    session: Session = Depends(get_db),
) -> LeisureRouteFeatureCollection:
    return list_leisure_routes(
        session, page=query.page, page_size=query.page_size, bbox=query.bbox_tuple
    )


@router.get("/{leisure_route_id}", response_model=LeisureRouteFeature)
@limiter.shared_limit(default_limit, api_scope)
def get_leisure_route_endpoint(
    request: Request, leisure_route_id: int, session: Session = Depends(get_db)
) -> LeisureRouteFeature:
    feature = get_leisure_route(session, leisure_route_id)
    if feature is None:
        raise HTTPException(status_code=404, detail="Leisure route not found")
    return feature
