"""Direct unit tests for core.job_error_mapping (#4250 follow-up).

_safe_error_message and its two mapping tables were extracted out of
processing_engine.py so they're importable/testable without pulling in the
rest of the engine. Broader coverage via the processing_engine re-export
lives in test_processing_engine.py::TestSafeErrorMessage and
test_atomic_cache_writes_4576.py; this file pins the module's own contract.
"""

import sys
from pathlib import Path

_BACKEND = Path(__file__).resolve().parents[2] / "auralis-web" / "backend"
if str(_BACKEND) not in sys.path:
    sys.path.insert(0, str(_BACKEND))

from auralis.utils.logging import Code, ModuleError  # noqa: E402
from core.encoding import WAVEncoderError  # noqa: E402
from core.job_error_mapping import _safe_error_message  # noqa: E402


def test_wav_encoder_error_maps_to_encoding_failed():
    assert _safe_error_message(WAVEncoderError("disk full")) == "Audio encoding failed"


def test_file_not_found_maps_to_specific_message():
    assert _safe_error_message(FileNotFoundError()) == "Audio file not found"


def test_generic_os_error_maps_to_read_failure():
    assert _safe_error_message(OSError("boom")) == "Audio file could not be read"


def test_unmapped_exception_falls_back_to_generic_message():
    assert _safe_error_message(RuntimeError("weird")) == "An unexpected error occurred during processing"


def test_module_error_matches_by_code_prefix():
    exc = ModuleError(f"{Code.ERROR_FFMPEG_NOT_FOUND}: ffmpeg missing from PATH")
    assert _safe_error_message(exc) == "Audio decoder unavailable on server"


def test_module_error_with_unrecognized_code_falls_back():
    exc = ModuleError("totally-unknown-code: detail")
    assert _safe_error_message(exc) == "Audio file could not be processed"


def test_raw_exception_text_is_never_returned():
    """The mapped category must never leak the original message (server-side
    only) — this is the entire point of the mapping layer."""
    secret = "/home/user/private/path/track.wav: permission denied by uid 1000"
    message = _safe_error_message(PermissionError(secret))
    assert secret not in message


# --- libsndfile failures on the normal-stream path (#5957) ---------------------------------
# stream_normal opens FLAC/WAV/AIFF with sf.SoundFile directly. LibsndfileError is a
# RuntimeError, so it used to fall through to the generic default for every bad file.


def _real_libsndfile_error(tmp_path, name, content):
    import soundfile as sf

    path = tmp_path / name
    if content is not None:
        path.write_bytes(content)
    try:
        sf.SoundFile(str(path))
    except sf.LibsndfileError as exc:
        return exc
    raise AssertionError("expected libsndfile to reject the file")


def test_missing_file_is_reported_as_not_found_or_unopenable(tmp_path):
    exc = _real_libsndfile_error(tmp_path, "gone.flac", None)
    assert _safe_error_message(exc, default="Audio streaming failed") == "Audio file not found or could not be opened"


def test_empty_and_garbage_files_are_reported_as_corrupted(tmp_path):
    for name, content in (("empty.flac", b""), ("junk.flac", b"not audio at all" * 40)):
        exc = _real_libsndfile_error(tmp_path, name, content)
        assert _safe_error_message(exc, default="Audio streaming failed") == "Audio file is corrupted or unsupported"


def test_malformed_wav_is_reported_as_corrupted(tmp_path):
    exc = _real_libsndfile_error(tmp_path, "bad.wav", b"RIFF\x00\x00\x00\x00WAVEjunk" * 3)
    assert _safe_error_message(exc, default="Audio streaming failed") == "Audio file is corrupted or unsupported"


def test_libsndfile_message_never_leaks_the_path(tmp_path):
    exc = _real_libsndfile_error(tmp_path, "secret_name.flac", None)
    assert str(tmp_path) not in _safe_error_message(exc)


def test_queue_status_counts_interrupted_jobs_in_their_own_bucket_5496():
    """#5496: a restored/interrupted job inflated `total` without appearing in any bucket."""
    from collections import namedtuple

    from core.processing_engine import ProcessingEngine, ProcessingStatus

    engine = ProcessingEngine.__new__(ProcessingEngine)
    Job = namedtuple("Job", "status")
    engine.jobs = {
        1: Job(ProcessingStatus.INTERRUPTED),
        2: Job(ProcessingStatus.COMPLETED),
        3: Job(ProcessingStatus.QUEUED),
    }
    engine._worker = type("W", (), {"active_job_count": 0})()
    engine.max_concurrent_jobs = 2
    engine.max_queue_size = 10
    engine.job_queue = type("Q", (), {"full": lambda self: False})()

    status = engine.get_queue_status()

    assert status["interrupted"] == 1
    buckets = ["queued", "processing", "completed", "failed", "cancelled", "interrupted"]
    assert sum(status[b] for b in buckets) == status["total"] == 3
