"""Sub-MIN_SAMPLES audio passes through the backend pipeline unprocessed (#6194).

The backend pipeline was the last copy of the "minimum DSP buffer" guard that
still raised: the engine's `hybrid_stage_dispatch.validate_and_normalize_input()`
had replaced its `raise ValueError` with warn-and-return-unprocessed (#4520),
because the raise broke the pipeline's `len(output) == len(input)` invariant
for any buffer under ~23ms and the Rust FFT panics the guard defended against
are fixed at the source. One copy got the fix, the other did not.

Now the backend imports the engine's MIN_SAMPLES (one definition, one policy)
and `process_audio` returns short audio untouched instead of failing the
stream.
"""

import sys
from pathlib import Path
from unittest.mock import MagicMock

import numpy as np

_BACKEND = Path(__file__).resolve().parents[2] / "auralis-web" / "backend"
if str(_BACKEND) not in sys.path:
    sys.path.insert(0, str(_BACKEND))

import auralis.core.hybrid_stage_dispatch as stage_dispatch  # noqa: E402
from core.audio_processing_pipeline import (  # noqa: E402
    MIN_SAMPLES,
    AudioProcessingPipeline,
)


def test_backend_imports_the_engine_constant():
    """One MIN_SAMPLES definition — the backend module holds the engine's
    object, not a second typed copy that can drift."""
    assert MIN_SAMPLES is stage_dispatch.MIN_SAMPLES


def test_validate_audio_returns_short_buffer_instead_of_raising():
    """A 512-sample buffer is returned with the engine's short-buffer
    behaviour: unprocessed, sample count preserved."""
    short_stereo = np.ones((512, 2), dtype=np.float32)

    result = AudioProcessingPipeline.validate_audio(short_stereo)

    assert isinstance(result, np.ndarray)
    assert result.shape == (512, 2)
    np.testing.assert_array_equal(result, short_stereo)


def test_validate_audio_still_converts_short_mono_to_stereo():
    """Mono-to-stereo conversion runs before the length check (engine order),
    so even a short mono buffer keeps the (N, 2) shape callers index into."""
    short_mono = np.linspace(-0.5, 0.5, 512, dtype=np.float32)

    result = AudioProcessingPipeline.validate_audio(short_mono)

    assert result.shape == (512, 2)


def test_process_audio_returns_short_chunk_unprocessed_without_a_processor():
    """The per-chunk entry (chunk_render.py) must not fail the stream or run
    DSP on a sub-MIN_SAMPLES buffer: no processor is selected, the chunk comes
    back with the same length."""
    short_audio = np.ones((512, 2), dtype=np.float32)
    factory = MagicMock(name="processor_factory")

    result = AudioProcessingPipeline.process_audio(
        audio=short_audio,
        preset="adaptive",
        intensity=1.0,
        processor_factory=factory,
        track_id=1,
    )

    factory.get_or_create.assert_not_called()
    assert result.shape == (512, 2)
    np.testing.assert_array_equal(result, short_audio)


def test_long_audio_still_reaches_the_processor():
    """The pass-through must not swallow normal-length chunks."""
    normal_audio = np.ones((2048, 2), dtype=np.float32)
    processor = MagicMock(name="processor")
    processor.process.side_effect = lambda a: a.copy()
    factory = MagicMock(name="processor_factory")
    factory.get_or_create.return_value = processor

    AudioProcessingPipeline.process_audio(
        audio=normal_audio,
        preset="adaptive",
        intensity=1.0,
        processor_factory=factory,
        track_id=1,
    )

    factory.get_or_create.assert_called_once()
