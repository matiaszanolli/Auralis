"""A tiny final chunk no longer aborts the render (#5736).

When ``total_frames % (CHUNK_DURATION_SEC * sr)`` was 1 to ~12 samples, the
final chunk was rendered alone and the first zero-phase filter raised
"The length of the input vector x must be greater than padlen", deleting the
staged file. Two layers now stop that: the loop folds a remainder shorter than
MIN_FINAL_CHUNK_SAMPLES into the previous chunk, and every stage filter goes
through ``sosfiltfilt_safe`` so a short buffer degrades instead of raising.
"""

from pathlib import Path
from unittest.mock import MagicMock

import numpy as np
import pytest
import soundfile as sf

from auralis.core.dsp.harmonic_exciter import HarmonicExciter
from auralis.core.dsp.resonance_notcher import Notch, ResonanceNotcher
from auralis.core.dsp.transient_shaper import TransientShaper
from auralis.core.mastering_chunk_assembly import (
    MIN_FINAL_CHUNK_SAMPLES,
    count_chunks,
    next_core_samples,
)
from auralis.core.mastering_config import SimpleMasteringConfig
from auralis.core.processing.continuous_guards import _apply_spectral_tilt_correction
from auralis.core.simple_mastering import SimpleMasteringPipeline

SR = 8000
ONE_SECTION_PADLEN = 9  # sosfiltfilt_padlen of a single-section filter
CHUNK_SEC = 1


def _pipeline() -> SimpleMasteringPipeline:
    config = SimpleMasteringConfig()
    config.CHUNK_DURATION_SEC = CHUNK_SEC
    config.CROSSFADE_DURATION_SEC = 0.02  # same escape hatch as test_chunk_loop_sample_count_5511
    pipeline = SimpleMasteringPipeline(config=config)
    fp_service = MagicMock()
    fp_service.get_or_compute.return_value = {
        'lufs': -14.0, 'crest_db': 6.0, 'bass_mid_ratio': 0.8,
        'tempo_bpm': 120.0, 'spectral_centroid': 3000.0,
    }
    pipeline._fingerprint_service = fp_service
    return pipeline


def _write(path: Path, frames: int) -> None:
    t = np.arange(frames) / SR
    wave = (0.4 * np.sin(2 * np.pi * 440.0 * t)).astype(np.float32)
    sf.write(str(path), np.stack([wave, wave * 0.8], axis=1), SR, subtype='PCM_24')


@pytest.mark.parametrize("k", [1, 2, 5, 9, 12, 16, 60, 1023, 1024, 1500])
def test_master_file_succeeds_and_keeps_every_sample(tmp_path, k):
    src, out = tmp_path / "in.wav", tmp_path / "out.wav"
    _write(src, CHUNK_SEC * SR + k)

    _pipeline().master_file(str(src), str(out), verbose=False)

    assert sf.info(str(out)).frames == CHUNK_SEC * SR + k


class TestChunkPlanning:
    CHUNK = 1000

    def test_a_tiny_remainder_is_folded_into_the_previous_chunk(self):
        total = 2 * self.CHUNK + MIN_FINAL_CHUNK_SAMPLES - 1
        assert next_core_samples(self.CHUNK, total, self.CHUNK) == total - self.CHUNK
        assert count_chunks(total, self.CHUNK) == 2

    def test_a_remainder_at_the_minimum_is_still_its_own_chunk(self):
        total = 2 * self.CHUNK + MIN_FINAL_CHUNK_SAMPLES
        assert next_core_samples(self.CHUNK, total, self.CHUNK) == self.CHUNK
        assert count_chunks(total, self.CHUNK) == 3

    @pytest.mark.parametrize("total", [1, 999, 1000, 1001, 2000, 2001, 2500, 5000, 5001])
    def test_cores_tile_the_file_exactly(self, total):
        pos, cores = 0, []
        while pos < total:
            cores.append(next_core_samples(pos, total, self.CHUNK))
            pos += cores[-1]
        assert sum(cores) == total
        assert len(cores) == count_chunks(total, self.CHUNK)
        assert all(c > 0 for c in cores)


@pytest.mark.parametrize("n", [1, 2, 3, 5, 12, 15])
class TestStagesSurviveTinyBuffers:
    """Defence in depth: a stage called directly on a buffer at or below the pad."""

    @staticmethod
    def _audio(n):
        return (0.3 * np.random.default_rng(n).standard_normal((2, n))).astype(np.float32)

    def test_transient_shaper(self, n):
        audio = self._audio(n)
        out = TransientShaper.apply(audio, 44100, 200.0, 4000.0, 3.0)
        assert out.shape == audio.shape and out.dtype == audio.dtype
        np.testing.assert_array_equal(out, audio)  # nothing to shape

    def test_harmonic_exciter(self, n):
        audio = self._audio(n)
        out = HarmonicExciter.apply(audio, 44100, wet_db=-12.0)
        assert out.shape == audio.shape and out.dtype == audio.dtype
        np.testing.assert_array_equal(out, audio)  # no band, no harmonics

    def test_resonance_notcher(self, n):
        audio = self._audio(n)
        out = ResonanceNotcher.apply(audio, 44100, [Notch(freq_hz=3000.0, depth_db=-6.0)])
        assert out.shape == audio.shape and out.dtype == audio.dtype
        if n <= ONE_SECTION_PADLEN:  # longer buffers are long enough to filter
            np.testing.assert_array_equal(out, audio)

    def test_spectral_tilt_guard(self, n):
        audio = self._audio(n).T  # (samples, channels)
        out = _apply_spectral_tilt_correction(audio, 44100, 1.5)
        assert out.shape == audio.shape and out.dtype == audio.dtype
        if n <= ONE_SECTION_PADLEN:  # not tilted by a half-computed split
            np.testing.assert_array_equal(out, audio)


def test_no_unguarded_sosfiltfilt_call_remains_in_the_chunk_path():
    import re
    root = Path(__file__).resolve().parents[3] / "auralis"
    offenders = []
    for path in root.rglob("*.py"):
        if path.name == "filters.py":
            continue
        for line in path.read_text().splitlines():
            code = line.split("#")[0]
            if re.search(r"(?<![\w.])sosfiltfilt\(", code) and "def " not in code:
                offenders.append(f"{path.relative_to(root)}: {line.strip()}")
    # continuous_guards keeps one raw call behind an explicit length check.
    assert [o for o in offenders if "continuous_guards" not in o] == []
