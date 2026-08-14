"""
Non-finite fingerprint dimensions never reach storage — issue #5103.

Regression of #2531. That issue's fix added a sanitize-and-count block to
``AudioFingerprintAnalyzer.analyze()``; ``871356f7`` ("route fingerprinting
through in-process Rust engine") replaced that analyzer wholesale without
porting the guard, and nothing downstream re-checked:

  * ``_prepare_for_storage()`` validates dimension **count** only
  * ``FingerprintRepository.upsert()`` validates column **names** only
  * the read-time ``_band_pct_valid()`` check inspects only the 7 band
    percentages, so a NaN ``lufs`` reads back as "valid" forever

The Rust layer cannot catch it either: ``estimate_lufs()``'s silence
early-return is ``if rms < 1e-10`` and ``NaN < 1e-10`` is false in IEEE-754,
so NaN flows past it and ``.clamp(-120.0, 0.0)`` is a no-op on NaN.

The guard is reinstated at ``compute_windowed_fingerprint()`` — the single
choke point every persistence path converges on (DB row, .25d sidecar, and
mastering-target selection).

:copyright: (C) 2024 Auralis Team
:license: GPLv3, see LICENSE for more details.
"""

import math

import numpy as np
import pytest

from auralis.analysis.fingerprint.windowed_compute import _sanitize_non_finite


class TestSanitizeNonFinite:
    def test_nan_is_replaced_with_zero(self):
        fp = {"lufs": float("nan"), "crest_db": 12.0}
        replaced = _sanitize_non_finite(fp, "track.flac")
        assert replaced == ["lufs"]
        assert fp["lufs"] == 0.0
        assert fp["crest_db"] == 12.0

    @pytest.mark.parametrize("bad", [float("inf"), float("-inf"), float("nan")])
    def test_every_non_finite_form_is_caught(self, bad):
        fp = {"lufs": bad}
        assert _sanitize_non_finite(fp, "t") == ["lufs"]
        assert fp["lufs"] == 0.0

    def test_numpy_scalars_are_caught(self):
        """The Rust engine's values arrive as numpy floats, not Python floats."""
        fp = {
            "lufs": np.float64("nan"),
            "crest_db": np.float32("inf"),
            "bass_pct": np.float64(0.25),
        }
        assert sorted(_sanitize_non_finite(fp, "t")) == ["crest_db", "lufs"]
        assert fp["lufs"] == 0.0
        assert fp["crest_db"] == 0.0
        assert fp["bass_pct"] == pytest.approx(0.25)

    def test_finite_fingerprint_is_untouched(self):
        fp = {"lufs": -14.5, "crest_db": 9.0, "bass_pct": 0.3}
        before = dict(fp)
        assert _sanitize_non_finite(fp, "t") == []
        assert fp == before

    def test_all_dimensions_non_finite(self):
        fp = {f"d{i}": float("nan") for i in range(25)}
        assert len(_sanitize_non_finite(fp, "t")) == 25
        assert all(v == 0.0 for v in fp.values())

    def test_non_numeric_values_are_left_alone(self):
        """Metadata keys must survive — only numeric dimensions are candidates."""
        fp = {"lufs": float("nan"), "source_path": "/music/a.flac", "ok": True}
        assert _sanitize_non_finite(fp, "t") == ["lufs"]
        assert fp["source_path"] == "/music/a.flac"
        assert fp["ok"] is True

    def test_bools_are_not_coerced_to_zero(self):
        """bool is a subclass of int; a False flag must not be 'sanitized'."""
        fp = {"flag": False}
        assert _sanitize_non_finite(fp, "t") == []
        assert fp["flag"] is False

    def test_replacement_is_logged_with_the_dimension_names(self, caplog):
        fp = {"lufs": float("nan"), "crest_db": float("inf")}
        with caplog.at_level("WARNING"):
            _sanitize_non_finite(fp, "poisoned.flac")
        assert "poisoned.flac" in caplog.text
        assert "crest_db" in caplog.text and "lufs" in caplog.text

    def test_clean_fingerprint_logs_nothing(self, caplog):
        with caplog.at_level("WARNING"):
            _sanitize_non_finite({"lufs": -14.0}, "clean.flac")
        assert caplog.text == ""

    def test_mutates_in_place_and_returns_names(self):
        """Callers rely on in-place mutation — the return value is diagnostic."""
        fp = {"lufs": float("nan")}
        result = _sanitize_non_finite(fp, "t")
        assert isinstance(result, list)
        assert fp["lufs"] == 0.0


class TestWiring:
    """WIRING: the guard has to actually run on the live compute path."""

    def test_compute_windowed_fingerprint_sanitizes(self, monkeypatch, tmp_path):
        import auralis.analysis.fingerprint.windowed_compute as wc

        poisoned = {f"d{i}": 0.5 for i in range(25)}
        poisoned["d0"] = float("nan")
        poisoned["d1"] = float("inf")

        class FakeAnalyzer:
            def analyze(self, audio, sr):
                return dict(poisoned)

        source = tmp_path / "a.wav"
        source.write_bytes(b"RIFF" + b"\x00" * 64)

        # Bypass decoding entirely: hand the pre-loaded-audio branch a buffer.
        audio = np.zeros((2, 44100 * 2), dtype=np.float64)
        result = wc.compute_windowed_fingerprint(
            FakeAnalyzer(), source, audio, 44100
        )

        assert result is not None, "guard must not reject the whole fingerprint"
        assert all(
            math.isfinite(v) for v in result.values() if isinstance(v, (int, float))
        ), f"non-finite value survived to the caller: {result}"
        assert result["d0"] == 0.0
        assert result["d1"] == 0.0

    def test_clean_fingerprint_passes_through_unchanged(self, monkeypatch, tmp_path):
        import auralis.analysis.fingerprint.windowed_compute as wc

        clean = {f"d{i}": 0.5 for i in range(25)}

        class FakeAnalyzer:
            def analyze(self, audio, sr):
                return dict(clean)

        source = tmp_path / "a.wav"
        source.write_bytes(b"RIFF" + b"\x00" * 64)

        audio = np.zeros((2, 44100 * 2), dtype=np.float64)
        result = wc.compute_windowed_fingerprint(
            FakeAnalyzer(), source, audio, 44100
        )

        assert result is not None
        for key, value in clean.items():
            assert result[key] == pytest.approx(value)
