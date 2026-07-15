import enum

from geoalchemy2 import Geometry
from sqlalchemy import Enum as SAEnum
from sqlalchemy import Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.shared.database import Base, SourcedMixin


class ParkingType(str, enum.Enum):
    PARACICLO = "paraciclo"
    BICICLETARIO = "bicicletario"


class BikeParking(SourcedMixin, Base):
    __tablename__ = "bike_parking"

    name: Mapped[str] = mapped_column(String, nullable=False)
    spot_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    type: Mapped[ParkingType] = mapped_column(
        SAEnum(ParkingType, name="parking_type"), nullable=False, index=True
    )
    operating_hours: Mapped[str | None] = mapped_column(String, nullable=True)
    geometry: Mapped[str] = mapped_column(Geometry("POINT", srid=4326), nullable=False)
