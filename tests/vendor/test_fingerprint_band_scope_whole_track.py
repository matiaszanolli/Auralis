"""The band shares and bass/mid ratio describe the whole input, not its first 30 s.

frequency_analysis.rs read only the first 30 s as "a representative sample" and
fingerprint_compute.rs's bass/mid ratio did the same. That was tolerable while the
fingerprint analysed a 90 s window from the middle of the track; once it analyses the
whole track (v13) the first 30 s are the intro. A real record with a quiet, bass-less
opening read bass 0.000 / mid 0.894.
"""

import numpy as np
import pytest

from auralis.analysis.fingerprint.audio_fingerprint_analyzer import AudioFingerprintAnalyzer

SR = 22050


def _tone(freq: float, seconds: float, level: float) -> np.ndarray:
    t = np.arange(int(seconds * SR)) / SR
    return (level * np.sin(2 * np.pi * freq * t)).astype(np.float32)


def _stereo(mono: np.ndarray) -> np.ndarray:
    return np.ascontiguousarray(np.stack([mono, mono], axis=1))


@pytest.fixture(scope="module")
def analyzer():
    return AudioFingerprintAnalyzer()


def test_music_after_a_quiet_bassless_intro_is_not_missed(analyzer):
    """35 s of a quiet 3 kHz tone, then 35 s of a loud 100 Hz tone."""
    intro_then_music = np.concatenate([_tone(3000.0, 35.0, 0.02), _tone(100.0, 35.0, 0.5)])

    fp = analyzer.analyze(_stereo(intro_then_music), SR)

    assert fp["sub_bass_pct"] + fp["bass_pct"] > 0.9, "the loud half of the track was ignored"
    assert fp["bass_mid_ratio"] > 0.0


def test_the_end_of_the_track_counts_as_much_as_the_start(analyzer):
    head_only_view = analyzer.analyze(_stereo(_tone(3000.0, 35.0, 0.3)), SR)
    whole = analyzer.analyze(
        _stereo(np.concatenate([_tone(3000.0, 35.0, 0.3), _tone(100.0, 35.0, 0.3)])), SR
    )

    # Equal-level halves: the bass half must show up roughly as strongly as the 3 kHz half.
    assert head_only_view["sub_bass_pct"] + head_only_view["bass_pct"] < 0.01
    assert whole["sub_bass_pct"] + whole["bass_pct"] == pytest.approx(0.5, abs=0.15)


def test_removing_the_tail_changes_the_bands(analyzer):
    """A head-only analysis returns identical bands however much follows the first 30 s."""
    music = np.concatenate([_tone(3000.0, 35.0, 0.3), _tone(100.0, 35.0, 0.3)])

    whole = analyzer.analyze(_stereo(music), SR)
    head = analyzer.analyze(_stereo(music[: 40 * SR]), SR)

    assert whole["bass_pct"] != pytest.approx(head["bass_pct"], abs=0.05) or (
        whole["sub_bass_pct"] != pytest.approx(head["sub_bass_pct"], abs=0.05)
    )
    assert whole["bass_mid_ratio"] != pytest.approx(head["bass_mid_ratio"], abs=0.5)


def test_a_short_clip_still_analyses(analyzer):
    fp = analyzer.analyze(_stereo(_tone(440.0, 2.0, 0.3)), SR)

    assert sum(fp[f"{b}_pct"] for b in
               ("sub_bass", "bass", "low_mid", "mid", "upper_mid", "presence", "air")) == pytest.approx(1.0, abs=0.01)
