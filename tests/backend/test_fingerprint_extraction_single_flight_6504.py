"""Concurrent requests for one track's fingerprint run one Tier-3 extraction (#6504).

Every play and seek builds a ChunkedAudioProcessor, which asks MasteringTargetService for the
fingerprint with extract_if_missing=True. The service lock covered only its cache dict, so a seek or
the init-timeout retry during a first play decoded and analysed the same file a second time. The
extraction is now single-flight per (track, file signature), like chunk renders (#5258).
"""

import sys
import threading
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "auralis-web" / "backend"))

from core.fingerprint_single_flight import extraction_flights  # noqa: E402
from core.mastering_target_service import MasteringTargetService  # noqa: E402

RESULT = ({"lufs": -14.0}, {"target_lufs": -14.0})


def _service(monkeypatch, extract):
    service = MasteringTargetService()
    monkeypatch.setattr(service, "load_fingerprint_from_database", lambda track_id: None)
    monkeypatch.setattr(service, "load_fingerprint_from_file", lambda filepath: None)
    monkeypatch.setattr(service, "extract_fingerprint_from_audio", extract)
    return service


def _concurrently(n, target):
    results = [None] * n
    threads = [threading.Thread(target=lambda i=i: results.__setitem__(i, target())) for i in range(n)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(10)
    return results


def test_concurrent_callers_share_one_extraction(monkeypatch):
    calls = []
    leader_started, release = threading.Event(), threading.Event()

    def extract(filepath, save_to_file=True, should_stop=None):
        calls.append(filepath)
        leader_started.set()
        release.wait(5)
        return RESULT

    service = _service(monkeypatch, extract)
    load = lambda: service.load_fingerprint(7, "/m/a.flac", file_signature="sig")  # noqa: E731
    threading.Timer(0.3, release.set).start()  # followers have queued behind the leader by then

    results = _concurrently(4, load)

    assert calls == ["/m/a.flac"], "the same file was analysed more than once"
    assert results == [RESULT] * 4
    assert extraction_flights.in_flight() == 0


def test_a_failed_leader_does_not_fail_the_followers(monkeypatch):
    attempts = []

    def extract(filepath, save_to_file=True, should_stop=None):
        attempts.append(filepath)
        return None if len(attempts) == 1 else RESULT  # the first try fails

    service = _service(monkeypatch, extract)

    assert service.load_fingerprint(8, "/m/b.flac", file_signature="sig") is None
    assert service.load_fingerprint(8, "/m/b.flac", file_signature="sig") == RESULT
    assert extraction_flights.in_flight() == 0


def test_a_waiting_caller_can_abandon(monkeypatch):
    release = threading.Event()
    started = threading.Event()

    def extract(filepath, save_to_file=True, should_stop=None):
        started.set()
        release.wait(5)
        return RESULT

    service = _service(monkeypatch, extract)
    leader = threading.Thread(target=lambda: service.load_fingerprint(9, "/m/c.flac", file_signature="sig"))
    leader.start()
    assert started.wait(5)

    abandoned = service.load_fingerprint(9, "/m/c.flac", file_signature="sig", should_stop=lambda: True)
    release.set()
    leader.join(5)

    assert abandoned is None
