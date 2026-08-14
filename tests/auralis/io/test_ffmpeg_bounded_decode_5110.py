"""
FFmpeg decodes only the requested window (#5110).
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

``compute_windowed_fingerprint`` needs a 90 s body window plus two 30 s probes.
The libsndfile branch seeks via ``librosa.load(..., offset, duration)`` and the
pre-loaded branch crops before resampling — but the FFmpeg branch (``.mp3``,
``.m4a``, ``.aac``, ``.ogg``, ``.wma``, ``.opus``) decoded the entire file,
resampled the entire buffer, and only then cropped to 150 s. Up to ~50x the
necessary CPU for a 2-hour file with a peak footprint in the GB range, multiplied
by ``FingerprintExtractionQueue``'s concurrency — and the formats affected are
the ones most libraries are made of.

``load_with_ffmpeg`` now takes ``offset``/``duration`` mapping to ``-ss``/``-t``.
The seek-accuracy tests below matter because a coarse seek on a VBR source would
shift the analysed window and change fingerprint values for already-indexed
tracks (which would require a ``FINGERPRINT_ALGORITHM_VERSION`` bump).

:copyright: (C) 2024 Auralis Team
:license: GPLv3, see LICENSE for more details.
"""

import shutil
import tempfile
from pathlib import Path

import numpy as np
import pytest

from auralis.io.loaders.ffmpeg_loader import load_with_ffmpeg

_MEDIA = Path(__file__).parent.parent.parent / "input_media"
_HAS_FFMPEG = shutil.which("ffmpeg") is not None and shutil.which("ffprobe") is not None

needs_ffmpeg = pytest.mark.skipif(not _HAS_FFMPEG, reason="ffmpeg/ffprobe not installed")


def _sample_mp3():
    for candidate in sorted(_MEDIA.glob("*.mp3")):
        return candidate
    return None


class TestCommandConstruction:
    """-ss must precede -i (input seeking), -t must follow it."""

    @staticmethod
    def _captured_cmd(monkeypatch, **kwargs):
        import auralis.io.loaders.ffmpeg_loader as mod

        seen = {}

        class _Result:
            returncode = 0
            stderr = ""

        def fake_run(cmd, timeout=None, cancel_event=None):
            seen["cmd"] = cmd
            raise RuntimeError("stop-after-capture")

        monkeypatch.setattr(mod, "check_ffmpeg", lambda: True)
        monkeypatch.setattr(mod, "check_ffprobe", lambda: True)
        monkeypatch.setattr(
            mod, "_probe_audio",
            lambda p: {"duration": 600.0, "sample_rate": 44100, "channels": 2},
        )
        monkeypatch.setattr(mod, "_run_ffmpeg_cancellable", fake_run)

        source = Path(tempfile.mkstemp(suffix=".mp3")[1])
        try:
            with pytest.raises(Exception):
                load_with_ffmpeg(source, **kwargs)
        finally:
            source.unlink(missing_ok=True)
        return seen.get("cmd", [])

    def test_no_window_requested_emits_no_ss_or_t(self, monkeypatch):
        """Backward compatibility: every existing caller is unaffected."""
        cmd = self._captured_cmd(monkeypatch)
        assert "-ss" not in cmd
        assert "-t" not in cmd

    def test_offset_is_placed_before_input(self, monkeypatch):
        cmd = self._captured_cmd(monkeypatch, offset=300.0)
        assert "-ss" in cmd, cmd
        assert cmd.index("-ss") < cmd.index("-i"), (
            "-ss after -i is output seeking: ffmpeg would decode and discard "
            "everything ahead of the window, defeating the point"
        )

    def test_duration_is_placed_after_input(self, monkeypatch):
        cmd = self._captured_cmd(monkeypatch, duration=90.0)
        assert "-t" in cmd
        assert cmd.index("-t") > cmd.index("-i")

    def test_zero_offset_is_not_emitted(self, monkeypatch):
        """offset=0 is a full-file read; no need for a redundant -ss 0."""
        cmd = self._captured_cmd(monkeypatch, offset=0.0)
        assert "-ss" not in cmd


@needs_ffmpeg
class TestRealBoundedDecode:
    @pytest.fixture(scope="class")
    def mp3(self):
        path = _sample_mp3()
        if path is None:
            pytest.skip("no .mp3 fixture available")
        return path

    def test_bounded_decode_returns_only_the_window(self, mp3, tmp_path):
        audio, sr = load_with_ffmpeg(mp3, str(tmp_path), offset=5.0, duration=10.0)
        got = len(audio) / sr
        assert got == pytest.approx(10.0, abs=0.5), (
            f"asked for 10 s, got {got:.2f} s"
        )

    def test_bounded_decode_is_shorter_than_the_full_file(self, mp3, tmp_path):
        full, sr_full = load_with_ffmpeg(mp3, str(tmp_path))
        windowed, sr_win = load_with_ffmpeg(
            mp3, str(tmp_path), offset=5.0, duration=10.0
        )
        assert sr_win == sr_full
        assert len(windowed) < len(full)

    def test_truncation_guard_does_not_false_trip(self, mp3, tmp_path):
        """The guard compares against the full file duration by default.

        A bounded read is legitimately far shorter, so without the #5110
        adjustment it raised ERROR_TRUNCATED_FILE on every windowed decode.
        """
        audio, sr = load_with_ffmpeg(mp3, str(tmp_path), offset=1.0, duration=3.0)
        assert len(audio) > 0

    def test_window_matches_the_same_span_of_a_full_decode(self, mp3, tmp_path):
        """Seek accuracy: a bounded read must equal the full read's same span.

        If this drifts, fingerprints computed the new way would not be
        comparable with already-stored rows and FINGERPRINT_ALGORITHM_VERSION
        would need bumping.
        """
        offset, dur = 5.0, 5.0
        full, sr = load_with_ffmpeg(mp3, str(tmp_path))
        windowed, sr_w = load_with_ffmpeg(
            mp3, str(tmp_path), offset=offset, duration=dur
        )
        assert sr_w == sr

        start = int(offset * sr)
        expected = full[start:start + len(windowed)]
        mono_w = windowed.mean(axis=1) if windowed.ndim == 2 else windowed
        mono_e = expected.mean(axis=1) if expected.ndim == 2 else expected
        n = min(len(mono_w), len(mono_e))
        assert n > sr, "window too short to compare meaningfully"

        # Compare RMS rather than sample-exact: an MP3 decoder may start a
        # bounded decode on a different frame boundary. What must not change is
        # the energy of the analysed span, which is what the fingerprint reads.
        rms_w = float(np.sqrt(np.mean(mono_w[:n] ** 2)))
        rms_e = float(np.sqrt(np.mean(mono_e[:n] ** 2)))
        assert rms_w == pytest.approx(rms_e, rel=0.15), (
            f"bounded-window RMS {rms_w:.5f} vs full-decode span {rms_e:.5f} — "
            "the seek landed somewhere materially different"
        )


@needs_ffmpeg
class TestWindowedFingerprintUsesBoundedDecode:
    """WIRING: the fingerprint path must actually request the windows."""

    def test_ffmpeg_branch_requests_bounded_spans(self, monkeypatch, tmp_path):
        import auralis.analysis.fingerprint.windowed_compute as wc

        mp3 = _sample_mp3()
        if mp3 is None:
            pytest.skip("no .mp3 fixture available")

        calls = []
        real = wc_load = __import__(
            "auralis.io.loaders", fromlist=["load_with_ffmpeg"]
        ).load_with_ffmpeg

        def recording(path, temp_folder=None, **kwargs):
            calls.append(kwargs)
            return real(path, temp_folder, **kwargs)

        monkeypatch.setattr(
            "auralis.io.loaders.load_with_ffmpeg", recording, raising=False
        )

        class _Analyzer:
            def analyze(self, audio, sr):
                return {f"d{i}": 0.5 for i in range(25)}

        wc.compute_windowed_fingerprint(_Analyzer(), mp3)

        assert calls, "the FFmpeg branch never called load_with_ffmpeg"
        assert all(
            c.get("duration") is not None for c in calls
        ), f"an unbounded full-file decode was issued: {calls}"
