"""
Processing Job Model
~~~~~~~~~~~~~~~~~~~~

Durable record of a mastering/export job (#5278). The backend's
``ProcessingEngine`` keeps its live jobs in memory; this row is what survives a
restart, so a job that was queued or running when the process died can be
reported as interrupted instead of vanishing.

:copyright: (C) 2024 Auralis Team
:license: AGPL-3.0-or-later (dual-licensed, see LICENSE / COMMERCIAL_LICENSE.md)
"""

from datetime import datetime

from sqlalchemy import DateTime, Float, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base


class ProcessingJobRecord(Base):
    """One processing job, as last persisted by the backend.

    Timestamps are naive local times, matching ``core.job_models.ProcessingJob``.
    ``settings`` and ``result_data`` are JSON text.
    """
    __tablename__ = 'processing_jobs'

    job_id: Mapped[str] = mapped_column(String, primary_key=True)
    input_path: Mapped[str] = mapped_column(Text, nullable=False)
    output_path: Mapped[str] = mapped_column(Text, nullable=False)
    mode: Mapped[str] = mapped_column(String, nullable=False, default='adaptive')
    status: Mapped[str] = mapped_column(String, nullable=False)
    progress: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    error_message: Mapped[str | None] = mapped_column(Text)
    settings: Mapped[str] = mapped_column(Text, nullable=False, default='{}')
    result_data: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    started_at: Mapped[datetime | None] = mapped_column(DateTime)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime)
