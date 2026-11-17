"""Run job DSP on the job pool with a budget that starts when the call starts (#5978).

`asyncio.wait_for(run_in_job_executor(...), timeout)` starts its clock at submission. A DSP
call that timed out or was cancelled cannot be stopped, so it keeps its pool thread until it
finishes; the next job then queues behind it and is billed that wait against its own budget,
failing with "timed out" before it has computed anything (the failure #5086 documents for the
chunk pool). Here the clock starts only when a pool thread picks the call up.

:copyright: (C) 2024 Auralis Team
:license: AGPL-3.0-or-later (dual-licensed, see LICENSE / COMMERCIAL_LICENSE.md)
"""

import asyncio
from collections.abc import Callable
from typing import Any, TypeVar

from core.executors import run_in_job_executor

T = TypeVar("T")


async def run_job_dsp(timeout: float, func: Callable[..., T], /, *args: Any) -> T:
    """Run ``func(*args)`` on the job pool; raise TimeoutError if it RUNS longer than ``timeout``.

    Time spent queued for a pool thread is not counted. Cancelling the caller while the call is
    still queued withdraws it before it ever starts.
    """
    loop = asyncio.get_running_loop()
    started = asyncio.Event()

    def _mark_started_then_run() -> T:
        try:
            loop.call_soon_threadsafe(started.set)
        except RuntimeError:  # the loop closed under an orphaned call; nobody is waiting
            pass
        return func(*args)

    call = asyncio.ensure_future(run_in_job_executor(_mark_started_then_run))
    started_waiter = asyncio.ensure_future(started.wait())
    try:
        await asyncio.wait({call, started_waiter}, return_when=asyncio.FIRST_COMPLETED)
        started_waiter.cancel()
        return await asyncio.wait_for(call, timeout=timeout)
    except BaseException:
        started_waiter.cancel()
        call.cancel()
        raise
