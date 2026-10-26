"""
Declared-Index Repair
~~~~~~~~~~~~~~~~~~~~~

``Base.metadata.create_all`` creates a table's indexes only when it creates
the table. A fresh install is built by ``create_all`` and never runs the SQL
migrations, and every later start finds its tables already present. So an
index declared on a model after that install was created never reaches it
(#5321: the migration-created range-query indexes were missing from every
fresh install, including the fingerprint indexes the KNN graph build relies
on). This creates those indexes on open, without a schema version bump.

:copyright: (C) 2024 Auralis Team
:license: AGPL-3.0-or-later (dual-licensed, see LICENSE / COMMERCIAL_LICENSE.md)
"""

import logging

from sqlalchemy import Table, delete, func, inspect, select
from sqlalchemy.engine import Engine

from .models import Base

logger = logging.getLogger(__name__)


def _remove_duplicates(engine: Engine, table: Table, columns: tuple[str, ...]) -> int:
    """Delete all but the lowest-``id`` row of each *columns* group; return the count.

    A unique index cannot be created over existing duplicates. Only the derived
    ``similarity_graph`` needs this today (two overlapping graph builds wrote the
    same edge twice, #5945), where keeping the first edge loses nothing. Rows
    are grouped on the declared columns, which must be NOT NULL: a NULL-bearing
    group would be merged here although a unique index treats NULLs as distinct.
    """
    if "id" not in table.c or any(table.c[name].nullable for name in columns):
        return 0
    keep = select(func.min(table.c.id)).group_by(*(table.c[name] for name in columns))
    with engine.begin() as connection:
        removed = connection.execute(delete(table).where(table.c.id.not_in(keep))).rowcount
    if removed:
        logger.warning(
            "Removed %d duplicate %s row(s) so the unique index over (%s) can be created",
            removed, table.name, ", ".join(columns),
        )
    return removed


def create_missing_declared_indexes(engine: Engine) -> list[str]:
    """Create each model-declared index the database lacks; return their names.

    A declared index counts as present when its table already has an index
    with the same name, or with the same columns in the same order under
    another name. Upgraded databases carry some migration-created equivalents
    under different names (``idx_similarity_graph_track_id`` for the model's
    ``ix_similarity_graph_track_id_rank``), and a second copy would only slow
    writes. A declared *unique* index is satisfied only by a unique index or a
    table-level UNIQUE constraint over the same columns (an upgraded database's
    ``UNIQUE(track_id, similar_track_id)`` is invisible to ``get_indexes``), and
    is created after removing any duplicates that would block it. Tables that do
    not exist yet are left to ``create_all``.
    """
    inspector = inspect(engine)
    created: list[str] = []
    for table in Base.metadata.sorted_tables:
        if not table.indexes or not inspector.has_table(table.name):
            continue
        existing = inspector.get_indexes(table.name)
        names = {index["name"] for index in existing}
        column_orders = {tuple(index["column_names"]) for index in existing}
        unique_orders = {tuple(index["column_names"]) for index in existing if index.get("unique")}
        unique_orders |= {
            tuple(constraint["column_names"])
            for constraint in inspector.get_unique_constraints(table.name)
        }
        for index in sorted(table.indexes, key=lambda i: str(i.name)):
            columns = tuple(column.name for column in index.columns)
            satisfied_by = unique_orders if index.unique else column_orders
            if index.name in names or columns in satisfied_by:
                continue
            if index.unique:
                _remove_duplicates(engine, table, columns)
            index.create(engine)
            created.append(str(index.name))
    return created
