from sqlalchemy import func
from sqlalchemy.orm import InstrumentedAttribute
from sqlalchemy.sql import Select


def apply_bbox_filter(
    stmt: Select,
    geometry_column: InstrumentedAttribute,
    bbox: tuple[float, float, float, float],
) -> Select:
    min_lon, min_lat, max_lon, max_lat = bbox
    envelope = func.ST_MakeEnvelope(min_lon, min_lat, max_lon, max_lat, 4326)
    return stmt.where(func.ST_Intersects(geometry_column, envelope))
