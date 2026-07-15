from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.orm import Session

from app.rest_points.schemas import RestPointFeature, RestPointFeatureCollection, RestPointQuery
from app.rest_points.service import get_rest_point, list_rest_points
from app.shared.auth import verify_api_key
from app.shared.database import get_db
from app.shared.middleware import api_scope, default_limit, limiter
from app.shared.openapi import LIST_RESPONSES, detail_responses

router = APIRouter(
    prefix="/rest-points", tags=["rest-points"], dependencies=[Depends(verify_api_key)]
)


@router.get(
    "",
    response_model=RestPointFeatureCollection,
    summary="List rest points",
    description="Paginated, bbox-filterable list of rest points along bike routes.",
    responses=LIST_RESPONSES,
)
@limiter.shared_limit(default_limit, api_scope)
def list_rest_points_endpoint(
    request: Request,
    query: Annotated[RestPointQuery, Query()],
    session: Session = Depends(get_db),
) -> RestPointFeatureCollection:
    return list_rest_points(
        session, page=query.page, page_size=query.page_size, bbox=query.bbox_tuple
    )


@router.get(
    "/{rest_point_id}",
    response_model=RestPointFeature,
    summary="Get a rest point by id",
    description="Single rest point as a GeoJSON Feature.",
    responses=detail_responses("Rest point not found"),
)
@limiter.shared_limit(default_limit, api_scope)
def get_rest_point_endpoint(
    request: Request, rest_point_id: int, session: Session = Depends(get_db)
) -> RestPointFeature:
    feature = get_rest_point(session, rest_point_id)
    if feature is None:
        raise HTTPException(status_code=404, detail="Rest point not found")
    return feature
