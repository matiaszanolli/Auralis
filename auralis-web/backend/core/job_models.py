#!/usr/bin/env python3

"""
Processing job model + status enum
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Shared value types for the processing engine and its worker. Extracted from
processing_engine.py (#4250) so job_worker.py can reference them without a
circular import back into ProcessingEngine. Re-exported from
processing_engine.py, so `from core.processing_engine import ProcessingJob,
ProcessingStatus` keeps working.

:copyright: (C) 2024 Auralis Team
:license: GPLv3, see LICENSE for more details.
"""

from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any


class ProcessingStatus(str, Enum):
    """Processing job status"""
    QUEUED = "queued"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class ProcessingJob:
    """Represents a single audio processing job"""

    def __init__(
        self,
        job_id: str,
        input_path: str,
        output_path: str,
        settings: dict[str, Any],
        mode: str = "adaptive"
    ):
        self.job_id = job_id
        self.input_path = input_path
        self.output_path = output_path
        self.settings = settings
        self.mode = mode  # "adaptive", "reference", "hybrid"

        self.status = ProcessingStatus.QUEUED
        self.progress = 0.0
        self.error_message: str | None = None
        self.result_data: dict[str, Any] | None = None

        self.created_at = datetime.now()
        self.started_at: datetime | None = None
        self.completed_at: datetime | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert job to dictionary for API responses.

        Exposes filenames only (no absolute paths) to avoid leaking
        server-side directory structure (#3322).
        """
        return {
            "job_id": self.job_id,
            "input_file": Path(self.input_path).name,
            "output_file": Path(self.output_path).name,
            "mode": self.mode,
            "status": self.status.value,
            "progress": self.progress,
            "error_message": self.error_message,
            "result_data": self.result_data,
            "created_at": self.created_at.isoformat(),
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
        }
