from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.rest_points.schemas import RestPointFeature, RestPointFeatureCollection, RestPointQuery
from app.rest_points.service import get_rest_point, list_rest_points
from app.shared.auth import verify_api_key
from app.shared.database import get_db
from app.shared.schemas import parse_bbox

router = APIRouter(
    prefix="/rest-points", tags=["rest-points"], dependencies=[Depends(verify_api_key)]
)


@router.get("", response_model=RestPointFeatureCollection)
def list_rest_points_endpoint(
    query: Annotated[RestPointQuery, Query()],
    session: Session = Depends(get_db),
) -> RestPointFeatureCollection:
    bbox = parse_bbox(query.bbox) if query.bbox else None
    return list_rest_points(session, page=query.page, page_size=query.page_size, bbox=bbox)


@router.get("/{rest_point_id}", response_model=RestPointFeature)
def get_rest_point_endpoint(
    rest_point_id: int, session: Session = Depends(get_db)
) -> RestPointFeature:
    feature = get_rest_point(session, rest_point_id)
    if feature is None:
        raise HTTPException(status_code=404, detail="Rest point not found")
    return feature
