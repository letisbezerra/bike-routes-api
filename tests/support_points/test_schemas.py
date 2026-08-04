import pytest
from pydantic import ValidationError

from app.support_points.schemas import (
    SupportPointParkingProperties,
    SupportPointRestPointProperties,
    SupportPointStationProperties,
)


def test_parking_shaped_dict_validates_into_parking_properties():
    props = SupportPointParkingProperties.model_validate(
        {
            "resource_type": "parking",
            "id": 1,
            "name": "Paraciclo Centro",
            "spot_count": 8,
            "type": "paraciclo",
            "operating_hours": "24h",
        }
    )
    assert props.resource_type == "parking"
    assert props.spot_count == 8


def test_station_shaped_dict_validates_into_station_properties():
    props = SupportPointStationProperties.model_validate(
        {
            "resource_type": "station",
            "id": 2,
            "name": "Estação Aldeota",
            "neighborhood": "Aldeota",
            "regional": "II",
            "inaugurated_at": None,
            "status": "existente",
            "sponsor": None,
            "current_slots": 12,
            "station_type": None,
        }
    )
    assert props.resource_type == "station"
    assert props.status == "existente"


def test_rest_point_shaped_dict_validates_into_rest_point_properties():
    props = SupportPointRestPointProperties.model_validate(
        {"resource_type": "rest_point", "id": 3, "name": "Ponto de descanso", "image_urls": []}
    )
    assert props.resource_type == "rest_point"


def test_unknown_resource_type_is_rejected():
    with pytest.raises(ValidationError):
        SupportPointParkingProperties.model_validate(
            {
                "resource_type": "not_a_real_type",
                "id": 1,
                "name": "x",
                "spot_count": None,
                "type": "paraciclo",
                "operating_hours": None,
            }
        )
