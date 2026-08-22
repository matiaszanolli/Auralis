"""
Per-chunk full-file decode amplification — issue #4737.

`ChunkOperations.load_chunk_from_file` opened the raw track path with
`sf.SoundFile(...)` and, on failure, fell back to decoding the WHOLE file via
`load_audio()` and slicing out the ~25 s it wanted. libsndfile cannot open
`.m4a`/`.aac`/`.wma` at all, so for those formats that fallback ran on *every*
chunk with no memoisation — ~60 full-track FFmpeg decodes for a 10-minute track,
each spawning a subprocess and allocating a large float transient, to extract
25 s. #4497 fixed the same amplification in the metadata probe; the chunk path
kept it.

The fix resolves the track to a seekable path once per processor. The decisive
assertion here is a *count*: N chunk reads must trigger at most ONE decode.

Note the trigger is capability, not extension. `FFMPEG_FORMATS` is
`{.aac,.m4a,.mp3,.ogg,.opus,.wma}`, but libsndfile 1.2.x opens MP3/OGG/FLAC
natively — converting on suffix would ADD a decode for `.mp3`, the dominant
library format, where there is none today. So the native formats are asserted
to convert zero times.

:copyright: (C) 2024 Auralis Team
:license: GPLv3, see LICENSE for more details.
"""

import sys
import wave
from pathlib import Path
from unittest.mock import patch

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "auralis-web" / "backend"))

from core.seekable_source import (  # noqa: E402
    SeekableSource,
    can_seek_natively,
    convert_to_temp_wav,
)


@pytest.fixture
def wav_file(tmp_path: Path) -> str:
    """A real, libsndfile-openable WAV."""
    path = tmp_path / "track.wav"
    frames = 44100 * 2
    data = (np.sin(2 * np.pi * 440 * np.arange(frames) / 44100) * 0.2 * 32767).astype("<i2")
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(44100)
        w.writeframes(data.tobytes())
    return str(path)


@pytest.fixture
def unopenable_file(tmp_path: Path) -> str:
    """Stands in for .m4a/.aac/.wma: a real file libsndfile cannot open."""
    path = tmp_path / "track.m4a"
    path.write_bytes(b"\x00\x00\x00\x20ftypM4A " + b"\x00" * 512)
    return str(path)


class TestCapabilityProbe:
    def test_wav_is_natively_seekable(self, wav_file):
        assert can_seek_natively(wav_file) is True

    def test_m4a_is_not_natively_seekable(self, unopenable_file):
        assert can_seek_natively(unopenable_file) is False

    def test_missing_file_is_not_seekable(self, tmp_path):
        assert can_seek_natively(str(tmp_path / "nope.wav")) is False


class TestNativeFormatsAreNotConverted:
    """The regression the naive suffix-based guard would have introduced."""

    def test_wav_resolves_to_itself_without_converting(self, wav_file):
        source = SeekableSource(wav_file)
        assert source.resolve() == wav_file
        assert source.converted is False

    def test_native_format_never_calls_load_audio(self, wav_file):
        with patch("auralis.io.unified_loader.load_audio") as mock_load:
            source = SeekableSource(wav_file)
            for _ in range(5):
                source.resolve()
            assert mock_load.call_count == 0

    def test_close_on_an_unconverted_source_is_a_noop(self, wav_file):
        source = SeekableSource(wav_file)
        source.resolve()
        source.close()
        source.close()  # idempotent


class TestConversionHappensAtMostOnce:
    """The defect: one decode per chunk instead of one per track."""

    def test_repeated_resolve_decodes_only_once(self, unopenable_file, tmp_path):
        calls = {"n": 0}
        fake_audio = np.zeros((44100, 2), dtype=np.float32)

        def fake_load_audio(path, *args, **kwargs):
            calls["n"] += 1
            return fake_audio, 44100

        with patch("auralis.io.unified_loader.load_audio", side_effect=fake_load_audio):
            source = SeekableSource(unopenable_file)
            # Stand-in for ~60 chunk reads of a 10-minute track.
            paths = {source.resolve() for _ in range(60)}

        assert calls["n"] == 1, f"decoded {calls['n']} times for 60 chunk reads"
        assert len(paths) == 1, "resolve() must be stable across calls"
        assert source.converted is True
        source.close()

    def test_converted_path_is_actually_seekable(self, unopenable_file):
        fake_audio = (np.random.default_rng(0).standard_normal((4410, 2)) * 0.1).astype(np.float32)

        with patch("auralis.io.unified_loader.load_audio", return_value=(fake_audio, 44100)):
            source = SeekableSource(unopenable_file)
            resolved = source.resolve()
            try:
                assert resolved != unopenable_file
                assert can_seek_natively(resolved), "the whole point is that this is seekable"
            finally:
                source.close()


class TestTempDirLifecycle:
    def test_close_removes_the_temp_dir(self, unopenable_file):
        fake_audio = np.zeros((4410, 2), dtype=np.float32)

        with patch("auralis.io.unified_loader.load_audio", return_value=(fake_audio, 44100)):
            source = SeekableSource(unopenable_file)
            resolved = Path(source.resolve())

        assert resolved.exists()
        source.close()
        assert not resolved.exists()
        assert not resolved.parent.exists(), "the temp dir itself must go, not just the WAV"

    def test_context_manager_closes(self, unopenable_file):
        fake_audio = np.zeros((4410, 2), dtype=np.float32)

        with patch("auralis.io.unified_loader.load_audio", return_value=(fake_audio, 44100)):
            with SeekableSource(unopenable_file) as source:
                resolved = Path(source.resolve())
                assert resolved.exists()
        assert not resolved.parent.exists()

    def test_failed_conversion_leaves_no_temp_dir(self, unopenable_file):
        """mkdtemp runs before the decode, so a decode failure must still clean up."""
        import tempfile

        before = set(Path(tempfile.gettempdir()).glob("auralis_seekable_*"))

        with patch("auralis.io.unified_loader.load_audio", side_effect=RuntimeError("ffmpeg died")):
            source = SeekableSource(unopenable_file)
            with pytest.raises(RuntimeError):
                source.resolve()

        after = set(Path(tempfile.gettempdir()).glob("auralis_seekable_*"))
        assert after == before, f"leaked {after - before}"

    def test_convert_to_temp_wav_returns_dir_and_file(self, unopenable_file):
        fake_audio = np.zeros((4410, 2), dtype=np.float32)

        with patch("auralis.io.unified_loader.load_audio", return_value=(fake_audio, 44100)):
            temp_dir, wav_path = convert_to_temp_wav(unopenable_file)

        try:
            # The dir is returned (not just the WAV) precisely so a partial
            # failure can be cleaned up — the #4365 lesson.
            assert Path(wav_path).parent == Path(temp_dir)
            assert Path(wav_path).exists()
        finally:
            import shutil

            shutil.rmtree(temp_dir, ignore_errors=True)


class TestProcessorIntegration:
    """The processor must own the source and release it on close()."""

    def test_processor_exposes_close(self):
        from core.chunked_processor import ChunkedAudioProcessor

        assert callable(getattr(ChunkedAudioProcessor, "close", None))

    def test_three_chunk_reads_of_an_m4a_decode_once(self, unopenable_file):
        """The issue's primary test plan: N chunks must cost ONE decode.

        Measured against the pre-fix file this reports 3 (one per chunk), each
        preceded by a 'Soundfile loading failed, using fallback' warning.
        """
        from core.chunked_processor import ChunkedAudioProcessor

        calls = {"n": 0}
        fake_audio = (
            np.random.default_rng(0).standard_normal((44100 * 40, 2)) * 0.1
        ).astype(np.float32)

        def counting_load_audio(*_args, **_kwargs):
            calls["n"] += 1
            return fake_audio, 44100

        meta = {"sample_rate": 44100, "channels": 2, "duration_seconds": 40.0}

        with patch("auralis.io.unified_loader.load_audio", side_effect=counting_load_audio), \
             patch("core.chunk_metadata.get_audio_info", return_value=meta):
            processor = ChunkedAudioProcessor(
                track_id=1, filepath=unopenable_file,
                preset=None, intensity=1.0, chunk_cache={},
            )
            calls["n"] = 0  # discount anything the metadata path did
            try:
                for index in range(3):
                    audio, _start, _end = processor.load_chunk(index)
                    assert len(audio) > 0
            finally:
                processor.close()

        assert calls["n"] == 1, (
            f"{calls['n']} full-file decodes for 3 chunk reads — the "
            "per-chunk amplification is back"
        )

    def test_close_does_not_touch_the_shared_hybrid_processor(self, wav_file):
        """close() must release only the temp dir — self.processor is shared."""
        from core.chunked_processor import ChunkedAudioProcessor

        proc = ChunkedAudioProcessor.__new__(ChunkedAudioProcessor)
        proc._source = SeekableSource(wav_file)

        sentinel = object()
        proc.processor = sentinel

        proc.close()

        assert proc.processor is sentinel, (
            "close() tore down the shared HybridProcessor — the ProcessorFactory "
            "LRU owns that, and another live ChunkedAudioProcessor may hold it"
        )


class TestEvictionClosesProcessors:
    """_remember_processor previously documented that it drops without closing.

    That was correct while a ChunkedAudioProcessor owned no resource. Once it
    can own a temp WAV, dropping without closing leaks the file for the process
    lifetime — so eviction must close, and must not let a cleanup failure break
    the LRU bound.
    """

    def _worker(self):
        from core.streamlined_worker import StreamlinedCacheWorker

        worker = StreamlinedCacheWorker.__new__(StreamlinedCacheWorker)
        from collections import OrderedDict

        worker._processor_cache = OrderedDict()
        worker._processor_build_locks = {}
        return worker

    def test_evicted_processor_is_closed(self):
        import core.streamlined_worker as sw

        worker = self._worker()
        closed = []

        class FakeProcessor:
            def __init__(self, tag):
                self.tag = tag

            def close(self):
                closed.append(self.tag)

        with patch.object(sw, "_PROCESSOR_CACHE_MAX", 2):
            for i in range(3):
                worker._remember_processor((i, None, 1.0), FakeProcessor(i))

        assert closed == [0], f"expected the LRU-evicted processor to be closed, got {closed}"

    def test_close_failure_does_not_break_the_lru_bound(self):
        import core.streamlined_worker as sw

        worker = self._worker()

        class ExplodingProcessor:
            def close(self):
                raise OSError("temp dir vanished")

        with patch.object(sw, "_PROCESSOR_CACHE_MAX", 2):
            for i in range(4):
                worker._remember_processor((i, None, 1.0), ExplodingProcessor())

        assert len(worker._processor_cache) == 2, (
            "a failing close() must not stop eviction — the cache would grow unbounded"
        )
