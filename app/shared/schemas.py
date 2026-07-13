from typing import Generic, Literal, TypeVar

from pydantic import BaseModel, ConfigDict, Field, field_validator

PropertiesT = TypeVar("PropertiesT")

_MAX_BBOX_AREA_DEG2 = 1.0


class PaginationMeta(BaseModel):
    page: int
    page_size: int
    total: int
    total_pages: int


class Feature(BaseModel, Generic[PropertiesT]):
    type: Literal["Feature"] = "Feature"
    geometry: dict
    properties: PropertiesT


class FeatureCollection(BaseModel, Generic[PropertiesT]):
    type: Literal["FeatureCollection"] = "FeatureCollection"
    features: list[Feature[PropertiesT]]
    meta: PaginationMeta


class ListQuery(BaseModel):
    """Base query params every resource's list endpoint accepts: pagination
    plus the bounding-box filter. `extra="forbid"` rejects unknown params
    (docs/ARCHITECTURE.md)."""

    model_config = ConfigDict(extra="forbid")

    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=50, ge=1, le=200)
    bbox: str | None = None

    @field_validator("bbox")
    @classmethod
    def validate_bbox(cls, value: str | None) -> str | None:
        if value is None:
            return value
        min_lon, min_lat, max_lon, max_lat = _split_bbox(value)
        if not (-180 <= min_lon <= 180 and -180 <= max_lon <= 180):
            raise ValueError("bbox longitude must be within [-180, 180]")
        if not (-90 <= min_lat <= 90 and -90 <= max_lat <= 90):
            raise ValueError("bbox latitude must be within [-90, 90]")
        if min_lon >= max_lon or min_lat >= max_lat:
            raise ValueError("bbox min must be less than max on both axes")
        area = (max_lon - min_lon) * (max_lat - min_lat)
        if area > _MAX_BBOX_AREA_DEG2:
            raise ValueError(f"bbox area exceeds the {_MAX_BBOX_AREA_DEG2} square-degree cap")
        return value

    @property
    def bbox_tuple(self) -> tuple[float, float, float, float] | None:
        """The validated `bbox` string, parsed once into floats."""
        return _split_bbox(self.bbox) if self.bbox else None


def _split_bbox(value: str) -> tuple[float, float, float, float]:
    parts = value.split(",")
    if len(parts) != 4:
        raise ValueError(
            "bbox must have exactly 4 comma-separated values: min_lon,min_lat,max_lon,max_lat"
        )
    try:
        min_lon, min_lat, max_lon, max_lat = (float(p) for p in parts)
    except ValueError:
        raise ValueError("bbox values must be numeric") from None
    return min_lon, min_lat, max_lon, max_lat
