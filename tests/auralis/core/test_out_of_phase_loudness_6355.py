"""
Out-of-phase stereo gets the same master gain as in-phase stereo (#6355)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

The fingerprint measured `lufs` and `crest_db` on (L+R)/2. As the channels'
correlation went to -1 that mix cancelled: an exact anti-phase pair read -120
LUFS, streaming planned the maximum +24 dB lift and a whole-file job attenuated
it by ~24 dB. Loudness and crest are now measured on the channels (power-mean
RMS, loudest channel's peak), which, like the BS.1770 meter, does not depend
on inter-channel correlation.

Same material at correlations 1, 0, -0.8 and -1: R = rho*L + sqrt(1-rho^2)*N
keeps R at L's level for every rho.
"""

import numpy as np
import pytest

from auralis.analysis.fingerprint.audio_fingerprint_analyzer import AudioFingerprintAnalyzer
from auralis.core.config import UnifiedConfig
from auralis.core.hybrid_processor import HybridProcessor
from auralis.core.processing.mastering_targets import generate_targets_from_fingerprint
from auralis.dsp.utils.adaptive import calculate_loudness_units

SR = 44100
RHOS = (1.0, 0.0, -0.8, -1.0)


def _pair(rho: float, seconds: float = 10.0) -> np.ndarray:
    rng = np.random.default_rng(6355)
    n = int(SR * seconds)
    left = rng.standard_normal(n) * 0.08
    noise = rng.standard_normal(n) * 0.08
    right = rho * left + np.sqrt(max(0.0, 1.0 - rho * rho)) * noise
    return np.stack([left, right], axis=1).astype(np.float32)


@pytest.fixture(scope="module")
def fingerprints():
    analyzer = AudioFingerprintAnalyzer()
    return {rho: analyzer.analyze(_pair(rho), SR) for rho in RHOS}


def test_an_anti_phase_pair_reads_its_channels_loudness_not_silence(fingerprints):
    in_phase, anti_phase = fingerprints[1.0], fingerprints[-1.0]
    assert anti_phase["lufs"] > -60.0
    assert anti_phase["lufs"] == pytest.approx(in_phase["lufs"], abs=1.0)
    assert anti_phase["crest_db"] == pytest.approx(in_phase["crest_db"], abs=1.0)


def test_loudness_does_not_depend_on_correlation(fingerprints):
    readings = [fingerprints[rho]["lufs"] for rho in RHOS]
    assert max(readings) - min(readings) < 0.5


def test_the_streaming_plan_gives_every_correlation_the_same_gain(fingerprints):
    gains = {}
    for rho, fp in fingerprints.items():
        targets = generate_targets_from_fingerprint(fp)
        gains[rho] = targets["target_lufs"] - targets["source_lufs"]
    assert gains[-1.0] == pytest.approx(gains[0.0], abs=2.0)
    assert max(gains.values()) - min(gains.values()) < 3.0, gains


def test_a_whole_file_job_gives_every_correlation_the_same_gain():
    def realised_gain(rho: float) -> float:
        audio = _pair(rho)
        processor = HybridProcessor(UnifiedConfig())
        out = processor.process(audio.copy())
        assert out is not None and out.shape == audio.shape
        # A level change shows on the channels; the metered loudness of an anti-phase
        # pair is the K-weighted channel sum, which ignores correlation as well.
        return calculate_loudness_units(out, SR) - calculate_loudness_units(audio, SR)

    gains = {rho: realised_gain(rho) for rho in RHOS}
    assert gains[-1.0] == pytest.approx(gains[0.0], abs=2.0)
    assert max(gains.values()) - min(gains.values()) < 3.0, gains
