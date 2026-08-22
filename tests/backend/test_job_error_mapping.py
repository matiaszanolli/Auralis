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
