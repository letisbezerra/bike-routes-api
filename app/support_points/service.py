from math import ceil

from sqlalchemy import func, literal, select, union_all
from sqlalchemy.orm import Session

from app.parking.models import BikeParking
from app.rest_points.models import RestPoint
from app.shared.geojson import to_geojson_geometry
from app.shared.schemas import PaginationMeta
from app.shared.spatial import apply_bbox_filter
from app.stations.models import BikeShareStation
from app.support_points.schemas import (
    SupportPointFeature,
    SupportPointFeatureCollection,
    SupportPointParkingProperties,
    SupportPointRestPointProperties,
    SupportPointStationProperties,
)

BboxTuple = tuple[float, float, float, float] | None

# (model, properties schema) per resource_type — the single source of truth
# for which tables this endpoint aggregates.
_RESOURCES = {
    "parking": (BikeParking, SupportPointParkingProperties),
    "station": (BikeShareStation, SupportPointStationProperties),
    "rest_point": (RestPoint, SupportPointRestPointProperties),
}


def _resource_ids(resource_type: str, model: type, bbox: BboxTuple):
    """A cheap, id-only branch of the cross-table UNION ALL — ordering,
    counting, and pagination all run against this, so the database enforces
    the page-size cap instead of every matching row being pulled into
    Python first."""
    stmt = select(literal(resource_type).label("resource_type"), model.id.label("id"))
    if bbox is not None:
        stmt = apply_bbox_filter(stmt, model.geometry, bbox)
    return stmt


def _fetch_page_rows(session: Session, page_ids: list) -> dict:
    """Fetches full rows (geometry + properties) for exactly the ids on one
    page — at most one query per resource_type present on that page, never
    the full matching set."""
    ids_by_type: dict[str, list[int]] = {}
    for resource_type, row_id in page_ids:
        ids_by_type.setdefault(resource_type, []).append(row_id)

    rows_by_key = {}
    for resource_type, ids in ids_by_type.items():
        model, _ = _RESOURCES[resource_type]
        rows = session.execute(select(model).where(model.id.in_(ids))).scalars().all()
        for row in rows:
            rows_by_key[(resource_type, row.id)] = row
    return rows_by_key


def _to_feature(resource_type: str, row) -> SupportPointFeature:
    properties_cls = _RESOURCES[resource_type][1]
    return SupportPointFeature(
        geometry=to_geojson_geometry(row.geometry),
        properties=properties_cls.model_validate(row),
    )


def list_support_points(
    session: Session,
    *,
    page: int,
    page_size: int,
    bbox: BboxTuple = None,
) -> SupportPointFeatureCollection:
    id_union = union_all(
        *(
            _resource_ids(resource_type, model, bbox)
            for resource_type, (model, _) in _RESOURCES.items()
        )
    ).subquery()

    total = session.execute(select(func.count()).select_from(id_union)).scalar_one()
    total_pages = ceil(total / page_size) if total else 0
    if total == 0:
        return SupportPointFeatureCollection(
            features=[],
            meta=PaginationMeta(page=page, page_size=page_size, total=0, total_pages=0),
        )

    # Deterministic order — (resource_type, id) — so a client paginating
    # page-by-page never sees a row shift between requests. Decided in SQL:
    # only this page's ids ever leave the database.
    page_ids = session.execute(
        select(id_union.c.resource_type, id_union.c.id)
        .order_by(id_union.c.resource_type, id_union.c.id)
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).all()

    rows_by_key = _fetch_page_rows(session, page_ids)
    features = [
        _to_feature(resource_type, rows_by_key[(resource_type, row_id)])
        for resource_type, row_id in page_ids
    ]

    return SupportPointFeatureCollection(
        features=features,
        meta=PaginationMeta(page=page, page_size=page_size, total=total, total_pages=total_pages),
    )
