from sqlalchemy import String, create_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, sessionmaker

from app.shared.config import settings

engine = create_engine(settings.database_url)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


class Base(DeclarativeBase):
    pass


class SourcedMixin:
    """Every ingested table's identity contract: an own primary key plus the
    upsert key scripts/ingest.py's upsert_and_prune() depends on."""

    id: Mapped[int] = mapped_column(primary_key=True)
    source_id: Mapped[str] = mapped_column(String, unique=True, nullable=False, index=True)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
