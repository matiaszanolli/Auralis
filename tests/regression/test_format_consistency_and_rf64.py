"""
Regression tests: audio-format list consistency (#4109) and RF64 WAV
chunk-size sentinel handling (#4112).

#4109: the scanner, unified loader, file-type checker, and backend upload
allowlist used to maintain four divergent extension lists. They now all derive
from the single source of truth ``auralis.io.formats``. AIFF/AU were scanned but
rejected by the loader (silent fingerprint failure); they are now decodable.

#4112: ``_get_wav_declared_size`` returned ``chunk_size + 8`` unconditionally,
so a legacy RF64/overflow WAV using the ``0xFFFFFFFF`` size sentinel reported a
~4 GB declared size and was wrongly rejected as truncated.

:copyright: (C) 2024 Auralis Team
:license: GPLv3
"""

import struct
import tempfile
from pathlib import Path

import numpy as np
import soundfile as sf

from auralis.io.formats import AUDIO_EXTENSIONS, FFMPEG_FORMATS, SUPPORTED_FORMATS


class TestFormatListConsistency:
    """All format lists derive from the single source of truth (#4109)."""

    def test_scanner_matches_canonical(self):
        from auralis.library.scanner.config import AUDIO_EXTENSIONS as SCAN

        assert SCAN == AUDIO_EXTENSIONS

    def test_loader_supported_matches_canonical(self):
        from auralis.io.unified_loader import SUPPORTED_FORMATS as SF

        assert set(SF) == AUDIO_EXTENSIONS

    def test_ffmpeg_formats_subset_of_supported(self):
        assert FFMPEG_FORMATS <= set(SUPPORTED_FORMATS)

    def test_aiff_au_are_decodable(self):
        # The bug: scanned but not in SUPPORTED_FORMATS -> ERROR_UNSUPPORTED_FORMAT.
        assert {'.aiff', '.aif', '.au'} <= set(SUPPORTED_FORMATS)
        # AIFF/AU use libsndfile, not FFmpeg.
        assert {'.aiff', '.aif', '.au'}.isdisjoint(FFMPEG_FORMATS)

    def test_video_drm_containers_excluded(self):
        # No working decode path -> must not be scanned.
        assert {'.mp4', '.m4p', '.webm'}.isdisjoint(AUDIO_EXTENSIONS)

    def test_checker_is_superset_of_scanner(self):
        from auralis.utils.checker import is_audio_file

        for ext in AUDIO_EXTENSIONS:
            assert is_audio_file(f"track{ext}"), f"checker omits scanner format {ext}"

    def test_checker_no_longer_omits_aac_au(self):
        from auralis.utils.checker import is_audio_file

        assert is_audio_file("track.aac")
        assert is_audio_file("track.au")

    def test_backend_upload_allowlist_matches_canonical(self):
        import sys

        backend = str(Path(__file__).resolve().parents[2] / "auralis-web" / "backend")
        if backend not in sys.path:
            sys.path.insert(0, backend)
        from routers.processing_api import _ALLOWED_AUDIO_EXTENSIONS

        assert _ALLOWED_AUDIO_EXTENSIONS == AUDIO_EXTENSIONS


class TestAiffAuEndToEnd:
    """AIFF and AU files load through unified_loader.load_audio (#4109)."""

    def test_aiff_au_load(self):
        from auralis.io.unified_loader import load_audio

        sr = 44100
        sig = (0.1 * np.sin(2 * np.pi * 440 * np.arange(sr) / sr)).astype("float32")
        stereo = np.column_stack([sig, sig])
        for ext in (".aiff", ".au"):
            with tempfile.NamedTemporaryFile(suffix=ext, delete=False) as tf:
                path = tf.name
            try:
                sf.write(path, stereo, sr)
                audio, out_sr = load_audio(path)
                assert out_sr == sr
                assert audio.shape[0] == sr
                assert audio.dtype == np.float32
            finally:
                Path(path).unlink(missing_ok=True)


class TestRF64ChunkSizeSentinel:
    """_get_wav_declared_size handles the 0xFFFFFFFF overflow sentinel (#4112)."""

    def _write_header(self, path: Path, chunk_size: int) -> None:
        # 12-byte RIFF/WAVE header with a controlled chunk-size field.
        path.write_bytes(b"RIFF" + struct.pack("<I", chunk_size) + b"WAVE")

    def test_overflow_sentinel_returns_none(self):
        from auralis.io.loaders.soundfile_loader import _get_wav_declared_size

        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "rf64.wav"
            self._write_header(p, 0xFFFFFFFF)
            assert _get_wav_declared_size(p) is None

    def test_normal_header_returns_declared_size(self):
        from auralis.io.loaders.soundfile_loader import _get_wav_declared_size

        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "normal.wav"
            self._write_header(p, 1000)
            assert _get_wav_declared_size(p) == 1008  # chunk_size + 8

    def test_genuinely_truncated_wav_still_rejected(self):
        from auralis.utils.logging import Code, ModuleError
        from auralis.io.loaders.soundfile_loader import load_with_soundfile

        # Declare a 100 MB file but provide only the 12-byte header (<10% complete).
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "truncated.wav"
            self._write_header(p, 100 * 1024 * 1024)
            try:
                load_with_soundfile(p)
                assert False, "expected truncation rejection"
            except ModuleError as e:
                assert str(Code.ERROR_TRUNCATED_FILE) in str(e) or "truncated" in str(e).lower()
