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

from sqlalchemy import inspect
from sqlalchemy.engine import Engine

from .models import Base


def create_missing_declared_indexes(engine: Engine) -> list[str]:
    """Create each model-declared index the database lacks; return their names.

    A declared index counts as present when its table already has an index
    with the same name, or with the same columns in the same order under
    another name. Upgraded databases carry some migration-created equivalents
    under different names (``idx_similarity_graph_track_id`` for the model's
    ``ix_similarity_graph_track_id_rank``), and a second copy would only slow
    writes. Tables that do not exist yet are left to ``create_all``.
    """
    inspector = inspect(engine)
    created: list[str] = []
    for table in Base.metadata.sorted_tables:
        if not table.indexes or not inspector.has_table(table.name):
            continue
        existing = inspector.get_indexes(table.name)
        names = {index["name"] for index in existing}
        column_orders = {tuple(index["column_names"]) for index in existing}
        for index in sorted(table.indexes, key=lambda i: str(i.name)):
            columns = tuple(column.name for column in index.columns)
            if index.name in names or columns in column_orders:
                continue
            index.create(engine)
            created.append(str(index.name))
    return created
