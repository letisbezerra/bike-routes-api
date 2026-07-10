import enum
from datetime import datetime

from geoalchemy2 import Geometry
from sqlalchemy import Enum as SAEnum
from sqlalchemy import Float, Index, Integer, String
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.orm import Mapped, mapped_column

from app.shared.database import Base, SourcedMixin


class RouteCategory(str, enum.Enum):
    CICLOFAIXA = "ciclofaixa"
    CICLOVIA = "ciclovia"
    CICLORROTA = "ciclorrota"
    PASSEIO_COMPARTILHADO = "passeio_compartilhado"


class BikeRoute(SourcedMixin, Base):
    __tablename__ = "bike_routes"
    __table_args__ = (
        Index("ix_bike_routes_neighborhoods", "neighborhoods", postgresql_using="gin"),
    )

    name: Mapped[str] = mapped_column(String, nullable=False)
    category: Mapped[RouteCategory] = mapped_column(
        SAEnum(RouteCategory, name="route_category"), nullable=False, index=True
    )
    length_km: Mapped[float | None] = mapped_column(Float, nullable=True)
    segment: Mapped[str | None] = mapped_column(String, nullable=True)
    road_position: Mapped[str | None] = mapped_column(String, nullable=True)
    direction: Mapped[str | None] = mapped_column(String, nullable=True)
    pavement: Mapped[str | None] = mapped_column(String, nullable=True)
    separation_element: Mapped[str | None] = mapped_column(String, nullable=True)
    implemented_at: Mapped[datetime | None] = mapped_column(nullable=True)
    neighborhoods: Mapped[list[str]] = mapped_column(ARRAY(String), nullable=False, default=list)
    reference_year: Mapped[int | None] = mapped_column(Integer, nullable=True)
    geometry: Mapped[str] = mapped_column(Geometry("LINESTRING", srid=4326), nullable=False)
