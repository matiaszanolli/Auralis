"""
FFmpeg intermediate decode preserves more than 16 bits of precision (#5317).
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

``load_with_ffmpeg`` hardcoded its intermediate WAV to ``pcm_s16le``
regardless of the source's actual bit depth, silently truncating 24-bit
ALAC-in-M4A / WMA Lossless sources to ~96 dB of dynamic range before any DSP
or fingerprinting ran. ``load_with_soundfile`` (called right after FFmpeg)
always reads the temp WAV back as float32 (``dtype="float32"`` at
soundfile_loader.py:108) regardless of its on-disk sample format, so
upgrading the intermediate codec to ``pcm_f32le`` loses nothing and needs no
``bits_per_raw_sample`` probe.

:copyright: (C) 2024 Auralis Team
:license: AGPL-3.0-or-later (dual-licensed, see LICENSE / COMMERCIAL_LICENSE.md)
"""

import shutil
import subprocess
import tempfile
from pathlib import Path

import numpy as np
import pytest
import soundfile as sf

from auralis.io.loaders.ffmpeg_loader import load_with_ffmpeg

_HAS_FFMPEG = shutil.which("ffmpeg") is not None and shutil.which("ffprobe") is not None
needs_ffmpeg = pytest.mark.skipif(not _HAS_FFMPEG, reason="ffmpeg/ffprobe not installed")


class TestCommandConstruction:
    """Unit test: the emitted FFmpeg command upgrades the codec, once."""

    @staticmethod
    def _captured_cmd(monkeypatch):
        import auralis.io.loaders.ffmpeg_loader as mod

        seen = {}

        def fake_run(cmd, timeout=None, cancel_event=None):
            seen["cmd"] = cmd
            raise RuntimeError("stop-after-capture")

        monkeypatch.setattr(mod, "check_ffmpeg", lambda: True)
        monkeypatch.setattr(mod, "check_ffprobe", lambda: True)
        monkeypatch.setattr(
            mod, "_probe_audio",
            lambda p: {"duration": 10.0, "sample_rate": 48000, "channels": 2},
        )
        monkeypatch.setattr(mod, "_run_ffmpeg_cancellable", fake_run)

        source = Path(tempfile.mkstemp(suffix=".m4a")[1])
        try:
            with pytest.raises(Exception):
                load_with_ffmpeg(source)
        finally:
            source.unlink(missing_ok=True)
        return seen.get("cmd", [])

    def test_intermediate_codec_is_float32_not_16bit(self, monkeypatch):
        cmd = self._captured_cmd(monkeypatch)
        assert "pcm_s16le" not in cmd, "still truncating to 16-bit (#5317)"
        assert "-acodec" in cmd
        assert cmd[cmd.index("-acodec") + 1] == "pcm_f32le"


@needs_ffmpeg
class TestRealBitDepthPreservation:
    """Integration test: a real ALAC-in-M4A source keeps sub-16-bit detail."""

    @pytest.fixture(scope="class")
    def alac_m4a(self, tmp_path_factory):
        """A 24-bit ALAC-in-M4A fixture carrying a tone below the 16-bit
        quantization step (2**-17 full-scale, half of pcm_s16le's 2**-15
        step), so only a >16-bit-precision decode can reproduce it.
        """
        tmp_dir = tmp_path_factory.mktemp("bitdepth5317")
        sr = 48000
        n = int(sr * 2.0)
        t = np.arange(n) / sr
        amp = 2 ** -17
        tone = (amp * np.sin(2 * np.pi * 997 * t)).astype(np.float32)

        src_wav = tmp_dir / "src24.wav"
        sf.write(str(src_wav), tone, sr, subtype="PCM_24")

        m4a = tmp_dir / "src24.m4a"
        result = subprocess.run(
            ["ffmpeg", "-hide_banner", "-loglevel", "error",
             "-i", str(src_wav), "-c:a", "alac", str(m4a), "-y"],
            capture_output=True, timeout=30,
        )
        if result.returncode != 0 or not m4a.exists():
            pytest.skip(f"ALAC encode unavailable in this ffmpeg build: {result.stderr!r}")
        return m4a, amp, sr, n

    def test_output_retains_more_than_16_bit_precision(self, alac_m4a, tmp_path):
        m4a, amp, sr, n = alac_m4a
        audio, decoded_sr = load_with_ffmpeg(m4a, str(tmp_path))
        assert decoded_sr == sr

        mono = audio.mean(axis=1) if audio.ndim == 2 else audio
        t = np.arange(min(len(mono), n)) / sr
        ideal = (amp * np.sin(2 * np.pi * 997 * t)).astype(np.float32)
        got = mono[: len(ideal)]

        rms_ideal = float(np.sqrt(np.mean(ideal ** 2)))
        rms_err = float(np.sqrt(np.mean((got - ideal) ** 2)))

        # A pcm_s16le intermediate quantizes this signal into noise: measured
        # empirically at ratio ~3.45 (error bigger than the signal itself).
        # A pcm_f32le intermediate reproduces it cleanly: measured ~0.013.
        # 1.0 is a wide, safe line between the two regimes.
        assert rms_err / rms_ideal < 1.0, (
            f"sub-16-bit detail was destroyed: rms_ideal={rms_ideal:.3e} "
            f"rms_err={rms_err:.3e} (16-bit truncation would land here)"
        )
