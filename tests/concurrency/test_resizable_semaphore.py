"""Tests for ResizableSemaphore (#4404).

The fingerprint queue's adaptive monitor could previously only log its
recommended concurrency because threading.Semaphore can't be resized.
ResizableSemaphore applies the recommendation at runtime: growing wakes waiters,
shrinking takes effect as holders release, and capacity is always enforced.
"""

import threading
import time

from auralis.services.resizable_semaphore import ResizableSemaphore


def test_capacity_is_enforced():
    sem = ResizableSemaphore(2)
    sem.acquire()
    sem.acquire()
    assert sem.in_use == 2
    assert sem.capacity == 2

    # Third acquire must block while the semaphore is full.
    acquired_third = threading.Event()

    def _third():
        sem.acquire()
        acquired_third.set()

    t = threading.Thread(target=_third, daemon=True)
    t.start()
    assert not acquired_third.wait(timeout=0.2)  # still blocked

    sem.release()  # frees one slot
    assert acquired_third.wait(timeout=1.0)  # now proceeds
    t.join(timeout=1.0)


def test_resize_up_wakes_a_blocked_waiter():
    sem = ResizableSemaphore(1)
    sem.acquire()  # capacity now full

    proceeded = threading.Event()

    def _waiter():
        sem.acquire()
        proceeded.set()

    t = threading.Thread(target=_waiter, daemon=True)
    t.start()
    assert not proceeded.wait(timeout=0.2)  # blocked at capacity 1

    sem.resize(2)  # raise capacity → waiter can proceed without any release
    assert proceeded.wait(timeout=1.0)
    assert sem.in_use == 2
    t.join(timeout=1.0)


def test_resize_down_takes_effect_as_holders_release():
    sem = ResizableSemaphore(3)
    sem.acquire()
    sem.acquire()  # 2 in use, capacity 3

    sem.resize(1)  # shrink below current in_use — must not preempt holders
    assert sem.in_use == 2
    assert sem.capacity == 1

    # A new acquire must block until in_use drops below the new capacity (1).
    got_slot = threading.Event()

    def _acq():
        sem.acquire()
        got_slot.set()

    t = threading.Thread(target=_acq, daemon=True)
    t.start()
    sem.release()  # in_use 2 → 1, still >= capacity 1, so still blocked
    assert not got_slot.wait(timeout=0.2)
    sem.release()  # in_use 1 → 0, now below capacity → proceeds
    assert got_slot.wait(timeout=1.0)
    t.join(timeout=1.0)


def test_resize_floor_is_one():
    sem = ResizableSemaphore(0)  # clamped up to 1
    assert sem.capacity == 1
    sem.resize(-5)
    assert sem.capacity == 1


def test_over_release_does_not_inflate_capacity():
    sem = ResizableSemaphore(1)
    sem.release()  # release without a prior acquire
    sem.release()
    assert sem.in_use == 0

    # Only ONE slot should be available despite the spurious releases.
    sem.acquire()
    assert sem.in_use == 1

    blocked = threading.Event()

    def _second():
        sem.acquire()
        blocked.set()

    t = threading.Thread(target=_second, daemon=True)
    t.start()
    assert not blocked.wait(timeout=0.2)  # capacity still 1, so blocked
    sem.release()
    assert blocked.wait(timeout=1.0)
    t.join(timeout=1.0)


def test_context_manager_releases():
    sem = ResizableSemaphore(1)
    with sem:
        assert sem.in_use == 1
    assert sem.in_use == 0


def test_concurrent_stress_never_exceeds_capacity():
    sem = ResizableSemaphore(4)
    peak = 0
    peak_lock = threading.Lock()
    current = 0
    cur_lock = threading.Lock()

    def _worker():
        nonlocal peak, current
        for _ in range(50):
            sem.acquire()
            with cur_lock:
                current += 1
                now = current
            with peak_lock:
                peak = max(peak, now)
            time.sleep(0.0005)
            with cur_lock:
                current -= 1
            sem.release()

    threads = [threading.Thread(target=_worker) for _ in range(12)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=10.0)

    # Capacity was 4 throughout, so concurrent holders never exceeded it.
    assert peak <= 4
    assert sem.in_use == 0
