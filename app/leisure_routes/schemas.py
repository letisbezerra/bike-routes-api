from pydantic import BaseModel, ConfigDict

from app.shared.schemas import Feature, FeatureCollection, ListQuery


class LeisureRouteProperties(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    support_count: int | None


LeisureRouteFeature = Feature[LeisureRouteProperties]
LeisureRouteFeatureCollection = FeatureCollection[LeisureRouteProperties]


class LeisureRouteQuery(ListQuery):
    pass
