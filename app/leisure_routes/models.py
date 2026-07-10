from geoalchemy2 import Geometry
from sqlalchemy import Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.shared.database import Base, SourcedMixin


class LeisureRoute(SourcedMixin, Base):
    __tablename__ = "leisure_routes"

    name: Mapped[str] = mapped_column(String, nullable=False)
    support_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    geometry: Mapped[str] = mapped_column(Geometry("MULTILINESTRING", srid=4326), nullable=False)
