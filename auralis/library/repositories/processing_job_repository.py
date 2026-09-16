"""
Processing Job Repository
~~~~~~~~~~~~~~~~~~~~~~~~~

Data access for durable processing-job records (#5278). The backend's job
store writes a job here at each lifecycle transition and reads the table back
on startup; the lifecycle rules themselves stay in the backend.

:copyright: (C) 2024 Auralis Team
:license: AGPL-3.0-or-later (dual-licensed, see LICENSE / COMMERCIAL_LICENSE.md)
"""

from collections.abc import Iterable
from datetime import datetime
from typing import Any

from sqlalchemy import delete, select, update

from ..models import ProcessingJobRecord
from .base import BaseRepository


class ProcessingJobRepository(BaseRepository):
    """Repository for processing-job records."""

    def save(self, **fields: Any) -> None:
        """Insert or replace the record for ``fields['job_id']``.

        ``fields`` are ProcessingJobRecord columns; the whole row is written,
        so the record always equals the job's last known state.
        """
        with self._session_scope() as session:
            session.merge(ProcessingJobRecord(**fields))
            session.commit()

    def get_all(self) -> list[ProcessingJobRecord]:
        """Every record, oldest first, detached from the session."""
        with self._session_scope() as session:
            records = list(
                session.execute(
                    select(ProcessingJobRecord).order_by(ProcessingJobRecord.created_at)
                ).scalars().all()
            )
            for record in records:
                session.expunge(record)
            return records

    def mark_unfinished(self, statuses: Iterable[str], new_status: str,
                        error_message: str, completed_at: datetime) -> int:
        """Move every record in ``statuses`` to ``new_status``; return how many."""
        with self._session_scope() as session:
            result = session.execute(
                update(ProcessingJobRecord)
                .where(ProcessingJobRecord.status.in_(list(statuses)))
                .values(status=new_status, error_message=error_message,
                        completed_at=completed_at)
            )
            session.commit()
            return int(getattr(result, "rowcount", 0) or 0)

    def delete(self, job_ids: Iterable[str]) -> int:
        """Delete the records for ``job_ids``; return how many were removed."""
        ids = list(job_ids)
        if not ids:
            return 0
        with self._session_scope() as session:
            result = session.execute(
                delete(ProcessingJobRecord).where(ProcessingJobRecord.job_id.in_(ids))
            )
            session.commit()
            return int(getattr(result, "rowcount", 0) or 0)
