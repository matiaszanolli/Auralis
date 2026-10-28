"""A short non-finite buffer fails fast like a long one (#5191).

validate_and_normalize_input returned any buffer under MIN_SAMPLES untouched *before* the
NaN/Inf validation ran, so a corrupted short buffer came back from process() as if it were audio
while the same corruption in a longer buffer raised.
"""

import numpy as np
import pytest

from auralis.core.config import UnifiedConfig
from auralis.core.hybrid_processor import HybridProcessor
from auralis.utils.logging import ModuleError


@pytest.fixture
def processor() -> HybridProcessor:
    return HybridProcessor(UnifiedConfig())


def _buffer(frames: int, bad: float) -> np.ndarray:
    audio = (np.random.default_rng(1).standard_normal((frames, 2)) * 0.1).astype(np.float32)
    audio[frames // 2, 0] = bad
    return audio


@pytest.mark.parametrize("bad", [np.nan, np.inf, -np.inf])
@pytest.mark.parametrize("frames", [64, 2048])
def test_non_finite_input_raises_whatever_its_length(processor, frames, bad):
    with pytest.raises(ModuleError, match="NaN or Inf"):
        processor.process(_buffer(frames, bad))


def test_a_finite_short_buffer_still_comes_back_untouched(processor):
    audio = (np.random.default_rng(2).standard_normal((64, 2)) * 0.1).astype(np.float32)

    result = processor.process(audio)

    np.testing.assert_array_equal(result, audio)
    assert result is not audio
