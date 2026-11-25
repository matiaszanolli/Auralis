"""Bounded FIFO of processing jobs with loop-affine removal by cancellation."""

import asyncio

from core.job_models import ProcessingJob


class QueuedJobs(asyncio.Queue[ProcessingJob]):
    def discard(self, job: ProcessingJob) -> None:
        """Free the slot if the dispatcher has not dequeued this job."""
        # Use Queue's storage in place so the remaining jobs keep their FIFO
        # order and blocked producers see the newly available slot.
        try:
            self._queue.remove(job)  # type: ignore[attr-defined]
        except ValueError:
            return
        self.task_done()
        self._wakeup_next(self._putters)  # type: ignore[attr-defined]
