from logging.config import fileConfig

from geoalchemy2.alembic_helpers import include_object as geoalchemy2_include_object
from geoalchemy2.alembic_helpers import render_item, writer
from sqlalchemy import engine_from_config, pool

from alembic import context
from app.leisure_routes.models import LeisureRoute  # noqa: F401
from app.parking.models import BikeParking  # noqa: F401
from app.rest_points.models import RestPoint  # noqa: F401
from app.routes.models import BikeRoute  # noqa: F401
from app.shared.config import settings
from app.shared.database import Base
from app.stations.models import BikeShareStation  # noqa: F401

config = context.config
config.set_main_option("sqlalchemy.url", settings.database_url)

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata

# postgis/postgis's docker image bootstraps the postgis_tiger_geocoder and
# postgis_topology extensions by default, adding dozens of tables (state,
# county, edges, ...) reachable via this DB's search_path. Autogenerate
# would otherwise propose dropping all of them. Filtering by schema instead
# of by name was tried and doesn't work: under default (non-schema-aware)
# reflection, Alembic reports these reflected tables with schema=None, the
# same as a real public-schema table — there's no schema signal available
# here to tell them apart from a table whose model import was simply
# forgotten below. If a 6th resource is added, add its model import here;
# _our_tables is derived from Base.metadata so nothing else needs to change.
_our_tables = set(target_metadata.tables)


def include_object(object, name, type_, reflected, compare_to):
    if type_ == "table" and reflected and name not in _our_tables:
        return False
    return geoalchemy2_include_object(object, name, type_, reflected, compare_to)


def run_migrations_offline() -> None:
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        render_item=render_item,
        include_object=include_object,
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,
            render_item=render_item,
            include_object=include_object,
            process_revision_directives=writer,
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
