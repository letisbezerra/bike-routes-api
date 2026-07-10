from geoalchemy2 import Geometry
from sqlalchemy import String
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.orm import Mapped, mapped_column

from app.shared.database import Base, SourcedMixin


class RestPoint(SourcedMixin, Base):
    __tablename__ = "rest_points"

    name: Mapped[str] = mapped_column(String, nullable=False)
    image_urls: Mapped[list[str]] = mapped_column(ARRAY(String), nullable=False, default=list)
    geometry: Mapped[str] = mapped_column(Geometry("POINT", srid=4326), nullable=False)
