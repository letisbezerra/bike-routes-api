import enum
from datetime import date

from geoalchemy2 import Geometry
from sqlalchemy import Enum as SAEnum
from sqlalchemy import Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.shared.database import Base, SourcedMixin


class StationStatus(str, enum.Enum):
    EXISTENTE = "existente"
    EXISTENTE_3_0 = "existente_3_0"


class BikeShareStation(SourcedMixin, Base):
    __tablename__ = "bike_share_stations"

    name: Mapped[str] = mapped_column(String, nullable=False)
    neighborhood: Mapped[str | None] = mapped_column(String, nullable=True, index=True)
    regional: Mapped[str | None] = mapped_column(String, nullable=True)
    inaugurated_at: Mapped[date | None] = mapped_column(nullable=True)
    status: Mapped[StationStatus] = mapped_column(
        SAEnum(StationStatus, name="station_status"), nullable=False, index=True
    )
    sponsor: Mapped[str | None] = mapped_column(String, nullable=True)
    current_slots: Mapped[int | None] = mapped_column(Integer, nullable=True)
    station_type: Mapped[str | None] = mapped_column(String, nullable=True)
    geometry: Mapped[str] = mapped_column(Geometry("POINT", srid=4326), nullable=False)
