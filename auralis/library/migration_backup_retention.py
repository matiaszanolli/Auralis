"""
Retention for pre-migration backups
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Each schema migration writes a full copy of the library beside it, and nothing
ever removed one: a profile that booted pending migrations a few hundred times
held ~9 GB of them, and a full disk then made the next upgrade abort at startup
because the backup step has to succeed (#5750). The backup file name is defined
here so the writer (``backup_database``) and the pruner cannot drift apart.

:copyright: (C) 2024 Auralis Team
:license: AGPL-3.0-or-later (dual-licensed, see LICENSE / COMMERCIAL_LICENSE.md)
"""

import logging
import re
from datetime import datetime
from pathlib import Path

logger = logging.getLogger(__name__)

BACKUP_TIMESTAMP_FORMAT = "%Y%m%d_%H%M%S"
# Newest pre-migration backups kept once a migration has succeeded.
KEEP_PRE_MIGRATION_BACKUPS = 3

_TIMESTAMP_PATTERN = r"\d{8}_\d{6}"


def backup_filename(db_path: Path, now: datetime | None = None) -> str:
    """``<stem>.backup_<timestamp><suffix>`` for a database file, stamped now by default."""
    timestamp = (now or datetime.now()).strftime(BACKUP_TIMESTAMP_FORMAT)
    return f"{db_path.stem}.backup_{timestamp}{db_path.suffix}"


def prune_old_backups(
    db_path: str,
    keep: int = KEEP_PRE_MIGRATION_BACKUPS,
    protect: str | None = None,
    backup_dir: str | None = None,
) -> int:
    """Delete all but the newest ``keep`` backups of ``db_path``; returns the count removed.

    Only files named exactly like ``backup_database`` writes them are touched,
    and ``protect`` (the backup of the migration in progress) is never deleted.
    Failures are logged, never raised: pruning is housekeeping and must not turn
    a successful migration into a failed one.
    """
    db = Path(db_path)
    directory = Path(backup_dir) if backup_dir else db.parent
    pattern = re.compile(
        rf"^{re.escape(db.stem)}\.backup_{_TIMESTAMP_PATTERN}{re.escape(db.suffix)}$"
    )
    try:
        # Zero-padded timestamps sort chronologically by name.
        backups = sorted(
            (p for p in directory.iterdir() if p.is_file() and pattern.match(p.name)),
            key=lambda p: p.name,
            reverse=True,
        )
    except OSError as exc:
        logger.warning(f"Could not list pre-migration backups: {exc}")
        return 0

    protected = Path(protect).resolve() if protect else None
    removed = 0
    for stale in backups[max(keep, 0):]:
        if protected is not None and stale.resolve() == protected:
            continue
        try:
            stale.unlink()
            removed += 1
        except OSError as exc:
            logger.warning(f"Could not remove old backup {stale.name}: {exc}")
    if removed:
        logger.info(f"Pruned {removed} old pre-migration backup(s)")
    return removed
