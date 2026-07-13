from datetime import date

from pydantic import BaseModel, ConfigDict

from app.shared.schemas import Feature, FeatureCollection, ListQuery
from app.stations.models import StationStatus


class BikeShareStationProperties(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    neighborhood: str | None
    regional: str | None
    inaugurated_at: date | None
    status: StationStatus
    sponsor: str | None
    current_slots: int | None
    station_type: str | None


BikeShareStationFeature = Feature[BikeShareStationProperties]
BikeShareStationFeatureCollection = FeatureCollection[BikeShareStationProperties]


class BikeShareStationQuery(ListQuery):
    status: StationStatus | None = None
    neighborhood: str | None = None
