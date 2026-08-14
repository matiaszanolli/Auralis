"""
Byte-based pre-decode OOM guard — issue #4875.

Every pre-decode guard in the loader stack checked only duration against
`MAX_DURATION_SECONDS`. That constant's own comment justifies 7200 s as
"2 hours of stereo float32 at 96 kHz ≈ 5.3 GB — a safe upper bound", but the
guard never read sample rate or channel count, so the arithmetic was an
assumption about the input rather than a property of it.

The same 7200 s at 192 kHz stereo decodes to ~10.3 GiB, and at 192 kHz 5.1 to
~31 GiB — both waved through by a duration-only check. For a mastering tool,
high-resolution masters are squarely in the expected input domain.

Both values were already available at guard time (`sf.info()` carries
`samplerate`/`channels`; the FFmpeg path reads them from ffprobe into
`source_sample_rate`/`source_channels`), so the fix costs no extra probing.

:copyright: (C) 2024 Auralis Team
:license: GPLv3, see LICENSE for more details.
"""

import importlib

import pytest

from auralis.io.loader import (
    MAX_DECODED_BYTES,
    MAX_DURATION_SECONDS,
    estimated_decoded_bytes,
    oversize_decode_detail,
)

GIB = 1024 ** 3


class TestEstimate:
    def test_matches_duration_times_rate_times_channels_times_four(self):
        assert estimated_decoded_bytes(10, 44100, 2) == 10 * 44100 * 2 * 4

    def test_mono_and_stereo_differ_by_exactly_two(self):
        mono = estimated_decoded_bytes(60, 48000, 1)
        stereo = estimated_decoded_bytes(60, 48000, 2)
        assert stereo == 2 * mono

    def test_zero_channels_is_treated_as_one(self):
        """A malformed probe must not estimate zero bytes and slip through."""
        assert estimated_decoded_bytes(60, 48000, 0) == 60 * 48000 * 1 * 4

    def test_negative_duration_does_not_produce_a_negative_estimate(self):
        assert estimated_decoded_bytes(-5, 48000, 2) == 0


class TestCeiling:
    def test_the_profile_the_duration_cap_was_tuned_for_is_still_allowed(self):
        """2 h / 96 kHz / stereo ~ 5.15 GiB — the documented 'safe upper bound'.

        If this starts failing, the new ceiling has begun rejecting inputs the
        old guard deliberately accepted.
        """
        assert oversize_decode_detail(7200, 96000, 2) is None

    @pytest.mark.parametrize(
        "duration,rate,channels",
        [
            (7200, 44100, 2),   # 2 h CD-rate stereo
            (7200, 48000, 2),   # 2 h 48 kHz stereo
            (600, 192000, 2),   # short high-res
            (3600, 96000, 2),   # 1 h 96 kHz stereo
        ],
    )
    def test_ordinary_and_high_res_short_files_pass(self, duration, rate, channels):
        assert oversize_decode_detail(duration, rate, channels) is None

    @pytest.mark.parametrize(
        "duration,rate,channels,label",
        [
            (7199, 192000, 2, "the issue's 192 kHz stereo case (~10.3 GiB)"),
            (7200, 192000, 6, "192 kHz 5.1 near the cap (~31 GiB)"),
            (7000, 384000, 2, "DXD-rate stereo"),
        ],
    )
    def test_high_rate_or_multichannel_near_the_cap_is_rejected(
        self, duration, rate, channels, label
    ):
        detail = oversize_decode_detail(duration, rate, channels)
        assert detail is not None, f"{label} slipped through"
        assert "exceeds maximum decoded size" in detail

    def test_detail_reports_the_actual_numbers(self):
        detail = oversize_decode_detail(7199, 192000, 2)
        assert "GiB" in detail
        assert "192000 Hz" in detail
        assert "2ch" in detail

    def test_all_these_cases_are_under_the_duration_cap(self):
        """The point of the issue: duration alone would have admitted them."""
        for duration, rate, channels in [(7199, 192000, 2), (7200, 192000, 6)]:
            assert duration <= MAX_DURATION_SECONDS
            assert oversize_decode_detail(duration, rate, channels) is not None


class TestEnvOverride:
    """CONSISTENCY: overridable like AURALIS_MAX_DURATION_SECONDS (#3758)."""

    def test_ceiling_is_overridable(self, monkeypatch):
        monkeypatch.setenv("AURALIS_MAX_DECODED_BYTES", str(32 * GIB))
        import auralis.io.loader as loader_module

        reloaded = importlib.reload(loader_module)
        try:
            assert reloaded.MAX_DECODED_BYTES == 32 * GIB
            # Previously rejected, now permitted by explicit operator opt-in.
            assert reloaded.oversize_decode_detail(7199, 192000, 2) is None
        finally:
            monkeypatch.delenv("AURALIS_MAX_DECODED_BYTES", raising=False)
            importlib.reload(reloaded)

    def test_garbage_override_falls_back_to_the_default(self, monkeypatch):
        monkeypatch.setenv("AURALIS_MAX_DECODED_BYTES", "not-a-number")
        import auralis.io.loader as loader_module

        reloaded = importlib.reload(loader_module)
        try:
            assert reloaded.MAX_DECODED_BYTES == 6 * GIB
        finally:
            monkeypatch.delenv("AURALIS_MAX_DECODED_BYTES", raising=False)
            importlib.reload(reloaded)

    def test_default_is_six_gib(self):
        assert MAX_DECODED_BYTES == 6 * GIB


class TestSoundfileGuardWiring:
    """SIBLING: the guard has to actually fire at the call site, pre-decode."""

    @staticmethod
    def _source(tmp_path):
        """A non-RIFF file, so the WAV truncation heuristic is skipped and the
        size guard is what decides."""
        target = tmp_path / "source.flac"
        target.write_bytes(b"fLaC" + b"\x00" * 64)
        return target

    @staticmethod
    def _info(rate, channels, duration=7000.0):
        class FakeInfo:
            pass

        FakeInfo.duration = duration
        FakeInfo.samplerate = rate
        FakeInfo.channels = channels
        FakeInfo.frames = int(duration * rate)
        return FakeInfo()

    def test_rejects_before_reading(self, monkeypatch, tmp_path):
        import auralis.io.loaders.soundfile_loader as sfl
        from auralis.utils.logging import ModuleError

        read_called = {"n": 0}

        def fake_read(*_args, **_kwargs):
            read_called["n"] += 1
            raise AssertionError("sf.read must not run — that read IS the OOM")

        monkeypatch.setattr(sfl.sf, "info", lambda *_a, **_k: self._info(192000, 2))
        monkeypatch.setattr(sfl.sf, "read", fake_read)

        with pytest.raises(ModuleError, match="exceeds maximum decoded size"):
            sfl.load_with_soundfile(self._source(tmp_path))

        assert read_called["n"] == 0, "decode was attempted despite the guard"

    def test_ordinary_file_is_not_rejected_by_the_new_guard(self, monkeypatch, tmp_path):
        """No false positive for a normal 48 kHz stereo file near the cap.

        Reaching sf.read is the assertion: it means the guard let it through.
        """
        import auralis.io.loaders.soundfile_loader as sfl

        reached = {"n": 0}

        def fake_read(*_args, **_kwargs):
            reached["n"] += 1
            raise _Reached()

        monkeypatch.setattr(sfl.sf, "info", lambda *_a, **_k: self._info(48000, 2))
        monkeypatch.setattr(sfl.sf, "read", fake_read)

        # load_with_soundfile wraps any decode-stage exception in ModuleError,
        # so assert on the counter rather than the marker type: the counter is
        # what proves control got past the guard.
        from auralis.utils.logging import ModuleError

        with pytest.raises(ModuleError) as excinfo:
            sfl.load_with_soundfile(self._source(tmp_path))

        assert reached["n"] == 1, "the guard rejected a legitimate 48 kHz file"
        assert "exceeds maximum decoded size" not in str(excinfo.value)


class TestPlaybackLoaderGuardWiring:
    """#5104: the fourth call site #4875 never reached.

    `auralis/io/loader.py` *defines* the byte budget but `load()` never called
    it — and that is the loader `auralis/player/audio_file_manager.py` and
    `auralis/player/gapless_playback_engine.py` import directly, bypassing
    `unified_loader.load_audio` (which did carry the fix). So the one decode
    path on the playback thread was the one path without the guard.
    """

    # 6 GiB / (192000 Hz x 2ch x 4B) = 4194 s, so 5000 s of 192 kHz stereo is
    # ~7.15 GiB — comfortably over the byte budget and comfortably under the
    # 7200 s duration cap. (#5104's report quoted a ~55 min / "5.1 GiB" example;
    # that is 5.07 GB but only 4.72 GiB, i.e. actually within budget. The gap is
    # real, the illustrative figure conflated GB and GiB.)
    @staticmethod
    def _info(rate, channels, duration=5000.0):
        class FakeInfo:
            pass

        FakeInfo.duration = duration
        FakeInfo.samplerate = rate
        FakeInfo.channels = channels
        FakeInfo.frames = int(duration * rate)
        return FakeInfo()

    def test_rejects_high_res_before_reading(self, monkeypatch, tmp_path):
        """192 kHz stereo at ~83 min: under the duration cap, over the budget."""
        import auralis.io.loader as loader_module

        source = tmp_path / "source.wav"
        source.write_bytes(b"RIFF" + b"\x00" * 64)

        def fake_read(*_args, **_kwargs):
            raise AssertionError("sf.read must not run — that read IS the OOM")

        monkeypatch.setattr(
            loader_module.sf, "info", lambda *_a, **_k: self._info(192000, 2)
        )
        monkeypatch.setattr(loader_module.sf, "read", fake_read)

        with pytest.raises(RuntimeError, match="exceeds maximum decoded size"):
            loader_module.load(str(source))

    def test_ordinary_file_is_not_rejected(self, monkeypatch, tmp_path):
        """No false positive: 44.1 kHz stereo at the same duration is ~1.2 GiB.

        Reaching sf.read is the assertion — it means the guard let it through.
        """
        import auralis.io.loader as loader_module

        source = tmp_path / "source.wav"
        source.write_bytes(b"RIFF" + b"\x00" * 64)

        reached = {"n": 0}

        def fake_read(*_args, **_kwargs):
            reached["n"] += 1
            raise _Reached()

        monkeypatch.setattr(
            loader_module.sf, "info", lambda *_a, **_k: self._info(44100, 2)
        )
        monkeypatch.setattr(loader_module.sf, "read", fake_read)

        with pytest.raises(Exception) as excinfo:
            loader_module.load(str(source))

        assert reached["n"] == 1, "the guard rejected a legitimate 44.1 kHz file"
        assert "exceeds maximum decoded size" not in str(excinfo.value)

    def test_duration_cap_still_fires_first(self, monkeypatch, tmp_path):
        """The pre-existing #3300 duration check is unchanged by the addition."""
        import auralis.io.loader as loader_module

        source = tmp_path / "source.wav"
        source.write_bytes(b"RIFF" + b"\x00" * 64)

        monkeypatch.setattr(
            loader_module.sf,
            "info",
            lambda *_a, **_k: self._info(44100, 2, duration=99999.0),
        )
        monkeypatch.setattr(
            loader_module.sf,
            "read",
            lambda *_a, **_k: (_ for _ in ()).throw(AssertionError("must not read")),
        )

        with pytest.raises(RuntimeError, match="exceeds maximum duration"):
            loader_module.load(str(source))


class _Reached(Exception):
    """Marker: control reached the decode, i.e. the guard did not reject."""
