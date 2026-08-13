from typing import Annotated, Literal, Union

from pydantic import Field

from app.parking.schemas import BikeParkingProperties
from app.rest_points.schemas import RestPointProperties
from app.shared.schemas import Feature, FeatureCollection, ListQuery, PaginationMeta
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


class SupportPointFeature(Feature[SupportPointProperties]):
    pass


class SupportPointsPaginationMeta(PaginationMeta):
    # docs/specs/07-support-points-endpoint.md, pagination fairness fix —
    # per-subtype total. All 3 keys always present, even at 0, so "no
    # matches" and "not counted" can't be confused by a client reading this.
    total_by_type: dict[str, int]


class SupportPointFeatureCollection(FeatureCollection[SupportPointProperties]):
    # Overrides the inherited `list[Feature[PropertiesT]]` so the OpenAPI
    # schema names this after SupportPointFeature — otherwise Pydantic
    # resolves the generic inline and the item type gets an unreadable
    # auto-generated name in Swagger, even though the collection itself
    # is named.
    features: list[SupportPointFeature]
    meta: SupportPointsPaginationMeta


class SupportPointQuery(ListQuery):
    pass
