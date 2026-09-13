"""Converted temp WAVs are shared per file, not decoded per stream (#5402).

SeekableSource memoised its FFmpeg conversion on the instance, but every play,
seek and resume builds a fresh ChunkedAudioProcessor — and #5253 closes the old
one (deleting its WAV) before the next is built. So each seek of an
m4a/aac/wma track decoded the whole file again, and concurrent listeners each
paid their own decode. Conversions now live in a refcounted registry keyed on
the file signature, and the most recently released one is kept for the next
holder.
"""

import os
import sys
import threading
import time
from pathlib import Path
from unittest.mock import patch

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "auralis-web" / "backend"))

from core import seekable_source  # noqa: E402
from core.seekable_source import ConvertedWavRegistry, SeekableSource  # noqa: E402

FAKE_AUDIO = np.zeros((4410, 2), dtype=np.float32)


def _unopenable(tmp_path: Path, name: str = "track.m4a", payload: bytes = b"") -> str:
    """Stands in for .m4a/.aac/.wma: a real file libsndfile cannot open."""
    path = tmp_path / name
    path.write_bytes(b"\x00\x00\x00\x20ftypM4A " + payload + b"\x00" * 512)
    return str(path)


@pytest.fixture
def decodes():
    """Counts full-file decodes through the real conversion code."""
    calls: list[str] = []

    def fake_load_audio(path, *_args, **_kwargs):
        calls.append(path)
        return FAKE_AUDIO, 44100

    with patch("auralis.io.unified_loader.load_audio", side_effect=fake_load_audio):
        yield calls


@pytest.fixture(autouse=True)
def _no_leftover_conversions():
    yield
    seekable_source.converted_wavs.release_idle()


class TestSequentialStreamsOfOneTrack:
    def test_a_seek_reuses_the_previous_streams_conversion(self, tmp_path, decodes):
        """The issue's scenario: the old stream closes, then the new one resolves."""
        registry = ConvertedWavRegistry()
        track = _unopenable(tmp_path)

        first = SeekableSource(track, registry)
        first_path = first.resolve()
        first.close()

        second = SeekableSource(track, registry)
        assert second.resolve() == first_path
        assert Path(first_path).exists()
        assert len(decodes) == 1, f"decoded {len(decodes)} times across two streams"
        second.close()

    def test_two_processors_for_one_m4a_decode_once(self, tmp_path, decodes):
        """Test plan 1, end to end through ChunkedAudioProcessor and the global registry."""
        from core.chunked_processor import ChunkedAudioProcessor

        track = _unopenable(tmp_path)
        meta = {"sample_rate": 44100, "channels": 2, "duration_seconds": 0.1}
        paths = []
        with patch("core.chunk_metadata.get_audio_info", return_value=meta):
            for _ in range(2):  # play, then seek
                processor = ChunkedAudioProcessor(
                    track_id=1, filepath=track, preset=None, intensity=1.0, chunk_cache={}
                )
                try:
                    paths.append(processor._source.resolve())
                finally:
                    processor.close()

        assert len(decodes) == 1
        assert paths[0] == paths[1]


class TestConcurrentListeners:
    def test_concurrent_resolves_share_one_decode(self, tmp_path):
        registry = ConvertedWavRegistry()
        track = _unopenable(tmp_path)
        calls = []

        def slow_load_audio(path, *_args, **_kwargs):
            calls.append(path)
            time.sleep(0.05)  # hold the build while the other listener arrives
            return FAKE_AUDIO, 44100

        sources = [SeekableSource(track, registry) for _ in range(4)]
        results: list[str] = []
        with patch("auralis.io.unified_loader.load_audio", side_effect=slow_load_audio):
            threads = [threading.Thread(target=lambda s=s: results.append(s.resolve())) for s in sources]
            for t in threads:
                t.start()
            for t in threads:
                t.join()

        assert len(calls) == 1
        assert len(set(results)) == 1
        for source in sources:
            source.close()

    def test_the_wav_survives_while_any_holder_remains(self, tmp_path, decodes):
        registry = ConvertedWavRegistry(max_idle=0)
        track = _unopenable(tmp_path)
        a, b = SeekableSource(track, registry), SeekableSource(track, registry)
        path = Path(a.resolve())
        b.resolve()

        a.close()
        registry.release_idle()
        assert path.exists(), "deleted a WAV another stream is still reading"

        b.close()
        assert not path.parent.exists(), "the last holder's close must reclaim it (#5253)"


class TestBoundedRetention:
    def test_converting_another_track_drops_the_idle_one(self, tmp_path, decodes):
        registry = ConvertedWavRegistry(max_idle=1)
        first = SeekableSource(_unopenable(tmp_path, "a.m4a"), registry)
        first_dir = Path(first.resolve()).parent
        first.close()
        assert first_dir.exists()

        second = SeekableSource(_unopenable(tmp_path, "b.m4a"), registry)
        second.resolve()
        assert not first_dir.exists(), "a new track must not sit beside the old one's WAV"
        second.close()

    def test_release_idle_keeps_held_conversions(self, tmp_path, decodes):
        registry = ConvertedWavRegistry()
        held = SeekableSource(_unopenable(tmp_path), registry)
        path = Path(held.resolve())
        registry.release_idle()
        assert path.exists()
        held.close()
        registry.release_idle()
        assert not path.parent.exists()

    def test_shutdown_deletes_idle_and_stops_retaining(self, tmp_path, decodes):
        registry = ConvertedWavRegistry()
        idle = SeekableSource(_unopenable(tmp_path, "a.m4a"), registry)
        idle_dir = Path(idle.resolve()).parent
        idle.close()
        still_playing = SeekableSource(_unopenable(tmp_path, "b.m4a"), registry)
        playing_dir = Path(still_playing.resolve()).parent

        registry.shutdown()
        assert not idle_dir.exists()
        assert playing_dir.exists()

        still_playing.close()
        assert not playing_dir.exists(), "a stream released after shutdown must clean up"


class TestKeyedOnFileContent:
    def test_an_edited_file_is_converted_again(self, tmp_path, decodes):
        registry = ConvertedWavRegistry()
        track = _unopenable(tmp_path)
        first = SeekableSource(track, registry)
        first.resolve()
        first.close()

        Path(track).write_bytes(b"\x00\x00\x00\x20ftypM4A retagged" + b"\x00" * 900)
        os.utime(track, ns=(time.time_ns(), time.time_ns() + 10**9))

        second = SeekableSource(track, registry)
        second.resolve()
        assert len(decodes) == 2, "served a conversion of the file's previous content"
        second.close()


class TestFailedConversion:
    def test_a_failure_holds_nothing_and_the_next_attempt_retries(self, tmp_path):
        registry = ConvertedWavRegistry()
        track = _unopenable(tmp_path)

        with patch("auralis.io.unified_loader.load_audio", side_effect=RuntimeError("ffmpeg died")):
            with pytest.raises(RuntimeError):
                SeekableSource(track, registry).resolve()

        assert registry._conversions == {}

        with patch("auralis.io.unified_loader.load_audio", return_value=(FAKE_AUDIO, 44100)):
            source = SeekableSource(track, registry)
            assert Path(source.resolve()).exists()
            source.close()


class TestNormalStreamSharesTheRegistry:
    def test_normal_stream_holds_and_releases_through_the_registry(self):
        """SIBLING: stream_normal.py used its own per-stream convert_to_temp_wav."""
        import inspect

        from core import stream_normal

        source = inspect.getsource(stream_normal.stream_normal_audio)
        assert "converted_wavs.acquire" in source
        assert "converted_wavs.release" in source
        assert "convert_to_temp_wav" not in source
