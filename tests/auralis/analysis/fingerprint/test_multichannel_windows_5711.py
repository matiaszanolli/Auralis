"""
Regression: multichannel windows share one stereo downmix (#5711)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

For WAV/FLAC/AIFF the body window kept channels 0 and 1 of a >2-channel file
(dropping Center, LFE and surrounds) while the 30 s probes were an all-channel
mean (including the LFE), so the LUFS/crest median mixed two different signals
and a Center-only mix fingerprinted as near-silence. Every window now goes
through ``stereo_window``: BS.775 for canonical 5.1/7.1, as the FFmpeg branch
already did via ``-ac 2``.
"""

import numpy as np
import pytest
import soundfile as sf

from auralis.analysis.fingerprint.windowed_loading import (
    crop_preloaded_windows,
    load_librosa_windows,
)
from auralis.analysis.fingerprint.windows import FINGERPRINT_SAMPLE_RATE, stereo_window

SR = FINGERPRINT_SAMPLE_RATE
SECONDS = 40
FRAMES = SR * SECONDS
CENTER, LFE = 2, 3


def _rms(a: np.ndarray) -> float:
    return float(np.sqrt(np.mean(np.asarray(a, dtype=np.float64) ** 2)))


def _noise(frames: int = FRAMES, seed: int = 0) -> np.ndarray:
    return (np.random.default_rng(seed).standard_normal(frames) * 0.2).astype(np.float32)


def _surround_file(path, channel: int, channels: int = 6):
    data = np.zeros((FRAMES, channels), dtype=np.float32)
    data[:, channel] = _noise()
    sf.write(path, data, SR, subtype="FLOAT")
    return path


def _probe_mono_rms(probe: np.ndarray) -> float:
    return _rms(probe.mean(axis=0) if probe.ndim == 2 else probe)


class TestStereoWindow:
    def test_mono_and_stereo_pass_through_unchanged(self):
        stereo = np.random.default_rng(1).standard_normal((2, 1000)).astype(np.float32)
        mono = stereo[0]

        assert stereo_window(stereo) is stereo
        assert stereo_window(mono) is mono

    def test_center_reaches_both_outputs(self):
        window = np.zeros((6, 1000), dtype=np.float32)
        window[CENTER] = 0.5

        out = stereo_window(window)

        assert out.shape == (2, 1000)
        assert _rms(out) > 0.3

    def test_lfe_is_dropped(self):
        window = np.zeros((6, 1000), dtype=np.float32)
        window[LFE] = 0.5

        assert _rms(stereo_window(window)) == 0.0

    def test_a_layout_that_the_count_does_not_identify_keeps_its_first_two_channels(self):
        window = np.random.default_rng(2).standard_normal((4, 1000)).astype(np.float32)

        np.testing.assert_array_equal(stereo_window(window), window[:2])


class TestLibsndfileWindows:
    def test_a_center_only_mix_is_not_silent(self, tmp_path):
        audio, _, probes = load_librosa_windows(_surround_file(tmp_path / "c.wav", CENTER))

        assert audio.shape[0] == 2
        assert _rms(audio) > 0.05
        assert all(_probe_mono_rms(p) > 0.05 for p in probes)

    def test_body_and_probes_agree_about_the_same_content(self, tmp_path):
        audio, _, probes = load_librosa_windows(_surround_file(tmp_path / "c.wav", CENTER))

        body = _rms(audio.mean(axis=0))
        for probe in probes:
            assert _probe_mono_rms(probe) == pytest.approx(body, rel=0.15)

    def test_lfe_content_reaches_neither_the_body_nor_the_probes(self, tmp_path):
        audio, _, probes = load_librosa_windows(_surround_file(tmp_path / "lfe.wav", LFE))

        assert _rms(audio) < 1e-6
        assert all(_probe_mono_rms(p) < 1e-6 for p in probes)

    def test_a_quad_file_does_not_raise_and_yields_two_channels(self, tmp_path):
        audio, _, probes = load_librosa_windows(_surround_file(tmp_path / "quad.wav", 0, channels=4))

        assert audio.shape[0] == 2
        assert all(p.ndim == 1 or p.shape[0] <= 2 for p in probes)

    def test_stereo_probes_match_librosa_mono_load(self, tmp_path):
        import librosa

        stereo = np.stack([_noise(seed=3), _noise(seed=4)], axis=1)
        path = tmp_path / "stereo.wav"
        sf.write(path, stereo, SR, subtype="FLOAT")

        _, _, probes = load_librosa_windows(path)
        expected, _ = librosa.load(str(path), sr=SR, mono=True, offset=SECONDS * 0.25 - 0.0, duration=30.0)

        assert _probe_mono_rms(probes[0]) == pytest.approx(_rms(expected), rel=0.05)


class TestPreloadedBuffer:
    def test_matches_the_file_path_for_the_same_content(self, tmp_path):
        path = _surround_file(tmp_path / "c.wav", CENTER)
        file_audio, _, file_probes = load_librosa_windows(path)
        raw, sr = sf.read(path, dtype="float32")

        buf_audio, _, buf_probes = crop_preloaded_windows(raw.T, sr)

        assert buf_audio.shape[0] == file_audio.shape[0] == 2
        assert _rms(buf_audio) == pytest.approx(_rms(file_audio), rel=0.05)
        for a, b in zip(buf_probes, file_probes):
            assert _probe_mono_rms(a) == pytest.approx(_probe_mono_rms(b), rel=0.05)


def test_the_fingerprint_of_a_center_only_mix_is_not_the_silent_floor(tmp_path):
    from auralis.analysis.fingerprint.audio_fingerprint_analyzer import AudioFingerprintAnalyzer
    from auralis.analysis.fingerprint.windowed_compute import compute_windowed_fingerprint

    fingerprint = compute_windowed_fingerprint(
        AudioFingerprintAnalyzer(), _surround_file(tmp_path / "c.wav", CENTER)
    )

    assert fingerprint is not None
    assert fingerprint["lufs"] > -40.0
