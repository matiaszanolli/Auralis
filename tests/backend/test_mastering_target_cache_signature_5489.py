"""
Regression tests: MasteringTargetService keys its cache on file content (#5489)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

The fingerprint/target cache was keyed on md5(filepath), so a track replaced
in place kept being mastered against its pre-edit targets until a restart or
a blanket cache clear. It now keys on FileSignatureService's signature, like
the chunk and processor caches.

:copyright: (C) 2026 Auralis Team
:license: AGPL-3.0-or-later (dual-licensed, see LICENSE / COMMERCIAL_LICENSE.md)
"""

import os
import sys
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "auralis-web" / "backend"))

from core.file_signature import FileSignatureService
from core.mastering_target_service import MasteringTargetService

TRACK_ID = 5489


def _service_counting_db_loads() -> tuple[MasteringTargetService, list[int]]:
    service = MasteringTargetService()
    loads: list[int] = []

    def load_from_db(track_id: int) -> object:
        loads.append(track_id)
        return object()

    service.load_fingerprint_from_database = load_from_db  # type: ignore[method-assign]
    service.generate_targets_from_fingerprint = lambda fp: {"fp": fp}  # type: ignore[method-assign]
    return service, loads


def test_unchanged_file_is_served_from_cache(tmp_path):
    audio = tmp_path / "track.wav"
    audio.write_bytes(b"version one")
    service, loads = _service_counting_db_loads()

    first = service.load_fingerprint(TRACK_ID, str(audio))
    second = service.load_fingerprint(TRACK_ID, str(audio))

    assert first is second
    assert loads == [TRACK_ID]


def test_file_replaced_in_place_is_reloaded(tmp_path):
    audio = tmp_path / "track.wav"
    audio.write_bytes(b"version one")
    service, loads = _service_counting_db_loads()

    first = service.load_fingerprint(TRACK_ID, str(audio))
    audio.write_bytes(b"version two, re-encoded")
    stat = audio.stat()
    os.utime(audio, ns=(stat.st_atime_ns, stat.st_mtime_ns + 1_000_000_000))
    second = service.load_fingerprint(TRACK_ID, str(audio))

    assert second is not first
    assert loads == [TRACK_ID, TRACK_ID]


def test_caller_supplied_signature_skips_rehashing(tmp_path):
    audio = tmp_path / "track.wav"
    audio.write_bytes(b"version one")
    service, _loads = _service_counting_db_loads()
    signature = FileSignatureService.generate(str(audio))

    with patch.object(FileSignatureService, "generate", side_effect=AssertionError("rehashed")):
        service.load_fingerprint(TRACK_ID, str(audio), file_signature=signature)

    # A later lookup that computes the signature itself shares the entry.
    assert service.load_fingerprint(TRACK_ID, str(audio)) is service.load_fingerprint(
        TRACK_ID, str(audio), file_signature=signature
    )
    assert len(service.cache) == 1
