from typing import Annotated, Literal, Union

from pydantic import Field

from app.parking.schemas import BikeParkingProperties
from app.rest_points.schemas import RestPointProperties
from app.shared.schemas import Feature, FeatureCollection, ListQuery
from app.stations.schemas import BikeShareStationProperties


class SupportPointParkingProperties(BikeParkingProperties):
    resource_type: Literal["parking"] = "parking"


class SupportPointStationProperties(BikeShareStationProperties):
    resource_type: Literal["station"] = "station"


class SupportPointRestPointProperties(RestPointProperties):
    resource_type: Literal["rest_point"] = "rest_point"


SupportPointProperties = Annotated[
    Union[
        SupportPointParkingProperties,
        SupportPointStationProperties,
        SupportPointRestPointProperties,
    ],
    Field(discriminator="resource_type"),
]

SupportPointFeature = Feature[SupportPointProperties]
SupportPointFeatureCollection = FeatureCollection[SupportPointProperties]


class SupportPointQuery(ListQuery):
    pass
