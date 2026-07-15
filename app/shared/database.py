from sqlalchemy import String, create_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, sessionmaker

from app.shared.config import settings

# pool_pre_ping: Neon suspends/recycles idle connections on its side without
# telling this pool — the next checkout can hand out a connection the server
# already closed, surfacing as psycopg.OperationalError ("SSL connection has
# been closed unexpectedly") on the first query. Verified live in production
# via Sentry. pre_ping tests each connection with a cheap SELECT 1 before
# use and transparently reopens it if dead, so the caller never sees it.
engine = create_engine(settings.database_url, pool_pre_ping=True)
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
