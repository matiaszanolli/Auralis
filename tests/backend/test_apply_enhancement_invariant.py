"""Regression tests for AudioProcessingPipeline.apply_enhancement (#4371).

The intensity blend must preserve the sample-count invariant
(len(output) == len(input)). If a processor ever returns a
different-length array, the blend must fail loudly rather than silently
truncating to min_len and masking a gapless glitch.
"""

import sys
from pathlib import Path

import numpy as np
import pytest

# Backend package is rooted at auralis-web/backend
_BACKEND = Path(__file__).resolve().parents[2] / "auralis-web" / "backend"
if str(_BACKEND) not in sys.path:
    sys.path.insert(0, str(_BACKEND))

from core.audio_processing_pipeline import AudioProcessingPipeline  # noqa: E402


class _ShorterProcessor:
    """Processor that violates the sample-count invariant."""

    def __init__(self, drop: int = 10) -> None:
        self.drop = drop

    def process(self, audio: np.ndarray) -> np.ndarray:
        return audio[: -self.drop].copy()


class _IdentityProcessor:
    def process(self, audio: np.ndarray) -> np.ndarray:
        return audio.copy()


def _make_audio(n: int = 1000) -> np.ndarray:
    return np.linspace(-0.5, 0.5, n, dtype=np.float32).reshape(-1, 1)


def test_length_mismatch_raises_instead_of_truncating() -> None:
    audio = _make_audio()
    with pytest.raises(ValueError, match="does not match input"):
        AudioProcessingPipeline.apply_enhancement(
            audio, _ShorterProcessor(), intensity=0.5
        )


def test_matching_length_blends_and_preserves_samples() -> None:
    audio = _make_audio()
    out = AudioProcessingPipeline.apply_enhancement(
        audio, _IdentityProcessor(), intensity=0.5
    )
    assert len(out) == len(audio)
    assert isinstance(out, np.ndarray)
    # Identity processor + 50% blend == original audio
    np.testing.assert_allclose(out, audio, rtol=1e-6, atol=1e-6)
