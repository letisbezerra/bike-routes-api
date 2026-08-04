from typing import Annotated

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.orm import Session

from app.shared.auth import verify_api_key
from app.shared.database import get_db
from app.shared.middleware import api_scope, default_limit, limiter
from app.shared.openapi import LIST_RESPONSES
from app.support_points.schemas import SupportPointFeatureCollection, SupportPointQuery
from app.support_points.service import list_support_points

router = APIRouter(
    prefix="/support-points", tags=["support-points"], dependencies=[Depends(verify_api_key)]
)


@router.get(
    "",
    response_model=SupportPointFeatureCollection,
    summary="List support points (parking, stations, rest points combined)",
    description="Paginated, bbox-filterable combined list of bike parking, bike-share "
    "stations, and rest points — one call instead of three. Each feature's "
    "`properties.resource_type` (`parking`/`station`/`rest_point`) identifies its source.",
    responses=LIST_RESPONSES,
)
@limiter.shared_limit(default_limit, api_scope)
def list_support_points_endpoint(
    request: Request,
    query: Annotated[SupportPointQuery, Query()],
    session: Session = Depends(get_db),
) -> SupportPointFeatureCollection:
    return list_support_points(
        session, page=query.page, page_size=query.page_size, bbox=query.bbox_tuple
    )
