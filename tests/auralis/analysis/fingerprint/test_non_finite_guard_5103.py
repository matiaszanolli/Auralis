"""
Non-finite fingerprint dimensions never reach storage — issues #5103, #6144.

Regression of #2531. That issue's fix added a sanitize-and-count block to
``AudioFingerprintAnalyzer.analyze()``; ``871356f7`` ("route fingerprinting
through in-process Rust engine") replaced that analyzer wholesale without
porting the guard, and nothing downstream re-checked:

  * ``_prepare_for_storage()`` validates dimension **count** only
  * ``FingerprintRepository.upsert()`` validates column **names** only
  * the read-time ``_band_pct_valid()`` check inspects only the 7 band
    percentages, so a NaN ``lufs`` reads back as "valid" forever

#5103 reinstated the guard as replace-with-0.0. #6144: that stored a plausible
but wrong row (LUFS 0.0, the loudest possible value) that was stamped current
and never recomputed. Non-finite input samples are now zeroed before the engine
runs, and a non-finite result is a failed extraction (``require_finite`` raises
``FingerprintUnavailable``; ``compute_windowed_fingerprint`` returns None).

:copyright: (C) 2024 Auralis Team
:license: AGPL-3.0-or-later (dual-licensed, see LICENSE / COMMERCIAL_LICENSE.md)
"""

import numpy as np
import pytest

from auralis.analysis.fingerprint.audio_fingerprint_analyzer import (
    FingerprintUnavailable,
    require_finite,
)


class TestRequireFinite:
    @pytest.mark.parametrize("bad", [float("inf"), float("-inf"), float("nan")])
    def test_every_non_finite_form_is_rejected(self, bad):
        with pytest.raises(FingerprintUnavailable, match="lufs"):
            require_finite({"lufs": bad, "crest_db": 12.0}, "track.flac")

    def test_numpy_scalars_are_checked(self):
        """The Rust engine's values arrive as numpy floats, not Python floats."""
        fp = {"lufs": np.float64("nan"), "crest_db": np.float32("inf"), "bass_pct": np.float64(0.25)}
        with pytest.raises(FingerprintUnavailable) as err:
            require_finite(fp, "t")
        assert "crest_db" in str(err.value) and "lufs" in str(err.value)
        assert "bass_pct" not in str(err.value)

    def test_the_label_names_the_source(self):
        with pytest.raises(FingerprintUnavailable, match="poisoned.flac"):
            require_finite({"lufs": float("nan")}, "poisoned.flac")

    def test_finite_fingerprint_passes_untouched(self):
        fp = {"lufs": -14.5, "crest_db": 9.0, "bass_pct": 0.3}
        before = dict(fp)
        require_finite(fp, "t")
        assert fp == before

    def test_metadata_and_bools_are_not_dimensions(self):
        fp = {"lufs": -14.0, "source_path": "/music/a.flac", "ok": True, "flag": False}
        require_finite(fp, "t")
        assert fp["source_path"] == "/music/a.flac" and fp["flag"] is False


class TestWiring:
    """WIRING: the guard has to actually run on the live compute path."""

    @staticmethod
    def _run(fingerprint, tmp_path):
        import auralis.analysis.fingerprint.windowed_compute as wc

        class FakeAnalyzer:
            def analyze(self, audio, sr):
                return dict(fingerprint)

        source = tmp_path / "a.wav"
        source.write_bytes(b"RIFF" + b"\x00" * 64)
        # Bypass decoding entirely: hand the pre-loaded-audio branch a buffer.
        audio = np.zeros((2, 44100 * 2), dtype=np.float64)
        return wc.compute_windowed_fingerprint(FakeAnalyzer(), source, audio, 44100)

    def test_compute_windowed_fingerprint_rejects_a_non_finite_result(self, tmp_path):
        poisoned = {f"d{i}": 0.5 for i in range(25)}
        poisoned["d0"] = float("nan")
        assert self._run(poisoned, tmp_path) is None

    def test_clean_fingerprint_passes_through_unchanged(self, tmp_path):
        clean = {f"d{i}": 0.5 for i in range(25)}
        result = self._run(clean, tmp_path)
        assert result is not None
        for key, value in clean.items():
            assert result[key] == pytest.approx(value)
