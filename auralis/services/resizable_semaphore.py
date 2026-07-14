"""
Resizable Semaphore
~~~~~~~~~~~~~~~~~~~~

A counting semaphore whose capacity can be changed at runtime.

``threading.Semaphore`` cannot be resized safely once created, which is why the
fingerprint queue's adaptive resource monitor could only *log* its recommended
concurrency and never apply it (#4404). This wrapper backs the counter with a
``Condition`` so ``resize()`` can raise or lower the effective limit while
acquire/release keep the exact same blocking API as ``threading.Semaphore``.

:copyright: (C) 2024 Auralis Team
:license: GPLv3, see LICENSE for more details.
"""

from __future__ import annotations

import threading


class ResizableSemaphore:
    """A counting semaphore with a runtime-adjustable capacity.

    Drop-in for the subset of ``threading.Semaphore`` the fingerprint queue
    uses: blocking ``acquire()`` and ``release()``. Adds ``resize()`` to change
    the capacity, and ``capacity`` / ``in_use`` for observability/tests.
    """

    def __init__(self, initial: int) -> None:
        if initial < 1:
            initial = 1
        self._cond = threading.Condition()
        self._capacity = initial
        self._in_use = 0

    def acquire(self) -> None:
        """Block until a slot is free, then take it."""
        with self._cond:
            while self._in_use >= self._capacity:
                self._cond.wait()
            self._in_use += 1

    def release(self) -> None:
        """Return a slot and wake one waiter."""
        with self._cond:
            # Guard against over-release so the counter can't go negative and
            # silently inflate effective capacity.
            if self._in_use > 0:
                self._in_use -= 1
            self._cond.notify()

    def resize(self, new_capacity: int) -> None:
        """Change the capacity. Growing wakes waiters that may now proceed;
        shrinking takes effect as in-flight holders release (never preempts)."""
        if new_capacity < 1:
            new_capacity = 1
        with self._cond:
            grew = new_capacity > self._capacity
            self._capacity = new_capacity
            if grew:
                # Newly available slots — wake everyone and let the acquire loop
                # re-check capacity so exactly the freed count proceeds.
                self._cond.notify_all()

    @property
    def capacity(self) -> int:
        with self._cond:
            return self._capacity

    @property
    def in_use(self) -> int:
        with self._cond:
            return self._in_use

    # Context-manager support for parity with threading.Semaphore, in case a
    # future call site uses `with`.
    def __enter__(self) -> "ResizableSemaphore":
        self.acquire()
        return self

    def __exit__(self, *_exc: object) -> None:
        self.release()
