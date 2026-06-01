"""
Regression guard for the WebM encoder removal + router rename (#3876).

The WebM encoder was dead (no shipped route called `encode_to_webm_opus`; the
streaming path serves WAV). It was deleted and `routers/webm_streaming.py` was
renamed to `routers/wav_streaming.py` to match the wire format. These tests
pin that state so the dead code can't silently creep back and the router keeps
its accurate name.
"""

import importlib
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "auralis-web" / "backend"))


def test_webm_encoder_module_is_gone():
    """The dead encoder module must not be importable."""
    with pytest.raises(ModuleNotFoundError):
        importlib.import_module("encoding.webm_encoder")


def test_encoding_package_drops_webm_exports():
    """encoding/__init__.py must no longer re-export WebM symbols."""
    import encoding

    assert "encode_to_webm_opus" not in encoding.__all__
    assert "WebMEncoderError" not in encoding.__all__
    assert not hasattr(encoding, "encode_to_webm_opus")
    # WAV encoder stays.
    assert "encode_to_wav" in encoding.__all__


def test_router_module_renamed_to_wav_streaming():
    """The router lives at wav_streaming with the WAV-named factory; the old
    webm_streaming module is gone."""
    wav_streaming = importlib.import_module("routers.wav_streaming")
    assert hasattr(wav_streaming, "create_wav_streaming_router")
    assert not hasattr(wav_streaming, "create_webm_streaming_router")

    with pytest.raises(ModuleNotFoundError):
        importlib.import_module("routers.webm_streaming")


def test_processing_engine_still_categorizes_errors():
    """Removing the dead WebMEncoderError block must not break error
    categorization (the WAV encoder error entry remains)."""
    import core.processing_engine as pe

    # WAVEncoderError entry is still registered.
    assert any(
        exc_type.__name__ == "WAVEncoderError" for exc_type, _ in pe._ERROR_CATEGORIES
    )
    # A representative error still maps to a safe message.
    assert pe._safe_error_message(ValueError("bad")) == "Invalid audio data or parameters"
