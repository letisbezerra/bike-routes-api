from sqlalchemy import case, func, not_, select
from sqlalchemy.orm import InstrumentedAttribute, Session
from sqlalchemy.sql import ColumnElement, Select


def total_count(session: Session, stmt: Select) -> int:
    """Row count for a list query's `stmt`, run as its own `SELECT count(*)`
    subquery — shared by parking/routes/stations/rest_points/leisure_routes'
    `list_paginated`, which all start from a plain `Select`. Takes a `Select`
    specifically (calls `.subquery()` itself) — support_points/service.py
    builds its count from an already-`union_all().subquery()`'d object
    instead, so it isn't a fit for this helper and hand-rolls its own count
    rather than being widened to accept both shapes for one call site."""
    return session.execute(select(func.count()).select_from(stmt.subquery())).scalar_one()


def apply_round_robin_order(
    stmt: Select,
    group_column: InstrumentedAttribute,
    id_column: InstrumentedAttribute,
    group_order: dict,
) -> Select:
    """Interleaves rows fairly across `group_column`'s values instead of a
    plain `ORDER BY id`, which structurally starves any group whose rows
    were ingested in one contiguous id block after a larger group's block
    (first found for bike routes — commit 093ed42 — then reproduced for bike
    parking, whose source data has the same id-contiguous-per-type shape).

    `group_order` must have an entry for every value `group_column` can
    take, or an uncovered value's rows sort last within their rank tier
    (Postgres `CASE` with no matching `WHEN` and no `ELSE` returns `NULL`,
    and `NULLS LAST` is the default for ascending `ORDER BY`) — silently
    reproducing the same starvation bug this exists to prevent. Build it as
    `{member: i for i, member in enumerate(SomeEnum)}` so a future enum
    member is automatically covered, never a hand-copied literal that can
    drift out of sync with the enum.

    Known cost, not a regression: `row_number() OVER (PARTITION BY ...)`
    can't be satisfied by a plain index walk to the requested page the way
    `ORDER BY id` could — Postgres has to materialize and sort every row
    matching the query's filters before any row can be trimmed by
    LIMIT/OFFSET, on every page including the first (code-review
    2026-08-12). This is the same cost the original routes fairness fix
    (commit 093ed42) already accepted; applying the same pattern to parking
    and stations here doesn't add a new class of cost, just extends an
    already-accepted one to fix the same bug in two more places. Only
    matters for a wide/unfiltered bbox against a large table — worth a
    covering `(group_column, id)` index if it ever shows up in practice.
    """
    rank = func.row_number().over(partition_by=group_column, order_by=id_column).label(
        "_fairness_rank"
    )
    tiebreak = case(*[(group_column == value, order) for value, order in group_order.items()])
    return stmt.add_columns(rank).order_by(rank, tiebreak)


def apply_bbox_filter(
    stmt: Select,
    geometry_column: InstrumentedAttribute,
    bbox: tuple[float, float, float, float],
) -> Select:
    min_lon, min_lat, max_lon, max_lat = bbox
    envelope = func.ST_MakeEnvelope(min_lon, min_lat, max_lon, max_lat, 4326)
    return stmt.where(func.ST_Intersects(geometry_column, envelope))


def apply_geometry_clip(
    stmt: Select,
    geometry_column: InstrumentedAttribute,
    bbox: tuple[float, float, float, float],
) -> tuple[Select, ColumnElement, ColumnElement]:
    """Clips `geometry_column` to `bbox` for a list query. Excludes results
    whose clip degenerates to a non-line geometry (the geometry only touches
    the bbox boundary tangentially, without crossing into the interior) —
    `bike_routes`/`leisure_routes` features must always have line geometry.
    Returns the filtered statement plus the computed clipped-geometry and
    is-clipped columns to select alongside the entity. Caller must combine
    this with `apply_bbox_filter` (the base `ST_Intersects` match)."""
    min_lon, min_lat, max_lon, max_lat = bbox
    envelope = func.ST_MakeEnvelope(min_lon, min_lat, max_lon, max_lat, 4326)
    intersection = func.ST_Intersection(geometry_column, envelope)
    line_only = func.ST_CollectionExtract(intersection, 2)  # 2 = LineString type code
    is_clipped = not_(func.ST_Within(geometry_column, envelope))
    stmt = stmt.where(not_(func.ST_IsEmpty(line_only)))
    return stmt, line_only.label("clipped_geometry"), is_clipped.label("is_clipped")
