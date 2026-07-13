from pydantic import BaseModel, ConfigDict

from app.parking.models import ParkingType
from app.shared.schemas import Feature, FeatureCollection, ListQuery


class BikeParkingProperties(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    spot_count: int | None
    type: ParkingType
    operating_hours: str | None


BikeParkingFeature = Feature[BikeParkingProperties]
BikeParkingFeatureCollection = FeatureCollection[BikeParkingProperties]


class BikeParkingQuery(ListQuery):
    type: ParkingType | None = None
