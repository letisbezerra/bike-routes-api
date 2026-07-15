from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.routes.models import RouteCategory
from app.shared.schemas import Feature, FeatureCollection, ListQuery


class BikeRouteProperties(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    category: RouteCategory
    length_km: float | None
    segment: str | None
    road_position: str | None
    direction: str | None
    pavement: str | None
    separation_element: str | None
    implemented_at: datetime | None
    neighborhoods: list[str]
    reference_year: int | None


BikeRouteFeature = Feature[BikeRouteProperties]
BikeRouteFeatureCollection = FeatureCollection[BikeRouteProperties]


class BikeRouteQuery(ListQuery):
    category: RouteCategory | None = None
    neighborhood: str | None = None
