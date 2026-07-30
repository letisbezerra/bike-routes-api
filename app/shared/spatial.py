from sqlalchemy import func, not_
from sqlalchemy.orm import InstrumentedAttribute
from sqlalchemy.sql import ColumnElement, Select


def apply_bbox_filter(
    stmt: Select,
    geometry_column: InstrumentedAttribute,
    bbox: tuple[float, float, float, float],
) -> Select:
    min_lon, min_lat, max_lon, max_lat = bbox
    envelope = func.ST_MakeEnvelope(min_lon, min_lat, max_lon, max_lat, 4326)
    return stmt.where(func.ST_Intersects(geometry_column, envelope))


def apply_geometry_clip(
    stmt: Select,
    geometry_column: InstrumentedAttribute,
    bbox: tuple[float, float, float, float],
) -> tuple[Select, ColumnElement, ColumnElement]:
    """Clips `geometry_column` to `bbox` for a list query. Excludes results
    whose clip degenerates to a non-line geometry (the geometry only touches
    the bbox boundary tangentially, without crossing into the interior) —
    `bike_routes`/`leisure_routes` features must always have line geometry.
    Returns the filtered statement plus the computed clipped-geometry and
    is-clipped columns to select alongside the entity. Caller must combine
    this with `apply_bbox_filter` (the base `ST_Intersects` match)."""
    min_lon, min_lat, max_lon, max_lat = bbox
    envelope = func.ST_MakeEnvelope(min_lon, min_lat, max_lon, max_lat, 4326)
    intersection = func.ST_Intersection(geometry_column, envelope)
    line_only = func.ST_CollectionExtract(intersection, 2)  # 2 = LineString type code
    is_clipped = not_(func.ST_Within(geometry_column, envelope))
    stmt = stmt.where(not_(func.ST_IsEmpty(line_only)))
    return stmt, line_only.label("clipped_geometry"), is_clipped.label("is_clipped")
