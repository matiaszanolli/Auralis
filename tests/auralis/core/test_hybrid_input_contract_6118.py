"""HybridProcessor enforces its (samples, channels) float contract (#6118)

validate_and_normalize_input converted only 1-D input and gated on shape[0] < MIN_SAMPLES. A
librosa-style (2, N) array therefore looked "too short" and came back unprocessed with a warning
about milliseconds; an int16 array died inside the EQ with an opaque dtype error; an (N, 1) mono
array is a supported shape (its channel count is preserved).
"""

import numpy as np
import pytest

from auralis.core.config import UnifiedConfig
from auralis.core.hybrid_processor import HybridProcessor
from auralis.core.hybrid_stage_dispatch import MIN_SAMPLES, validate_and_normalize_input


@pytest.fixture
def processor() -> HybridProcessor:
    return HybridProcessor(UnifiedConfig())


def _tone(frames: int) -> np.ndarray:
    return (np.sin(np.linspace(0, 200, frames)) * 0.2).astype(np.float32)


def test_channels_first_input_is_refused_by_name(processor):
    channels_first = np.stack([_tone(4096), _tone(4096)])  # (2, 4096), as librosa returns it

    with pytest.raises(ValueError, match="channels-first"):
        processor.process(channels_first)


def test_integer_input_is_refused_up_front(processor):
    pcm = (_tone(4096) * 32767).astype(np.int16)

    with pytest.raises(ValueError, match="float"):
        processor.process(np.column_stack([pcm, pcm]))


def test_three_dimensional_input_is_refused(processor):
    with pytest.raises(ValueError, match="shape"):
        processor.process(np.zeros((4, 4, 4), dtype=np.float32))


def test_column_mono_keeps_its_one_channel(processor):
    """(N, 1) mono is a supported shape whose channel count is preserved (invariant test)."""
    column = _tone(4096)[:, None]

    audio, early = validate_and_normalize_input(processor, column)

    assert audio.shape == (4096, 1)
    assert early is None


def test_a_genuinely_tiny_stereo_clip_is_still_handled_as_too_short():
    tiny = np.zeros((2, 2), dtype=np.float32)  # 2 samples of stereo, not channels-first

    audio, early = validate_and_normalize_input(_FakeProcessor(), tiny)  # type: ignore[arg-type]

    assert early is not None and early.shape == (2, 2)
    assert audio.shape == (2, 2)


def test_ordinary_stereo_and_1d_mono_pass_through_validation(processor):
    stereo = np.column_stack([_tone(MIN_SAMPLES * 2), _tone(MIN_SAMPLES * 2)])

    _, early_stereo = validate_and_normalize_input(processor, stereo)
    _, early_mono = validate_and_normalize_input(processor, _tone(MIN_SAMPLES * 2))

    assert early_stereo is None and early_mono is None


class _FakeProcessor:
    class config:  # noqa: N801 - mimics the attribute chain the warning reads
        internal_sample_rate = 44100
