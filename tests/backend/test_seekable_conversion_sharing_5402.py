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
    """Counts full-file decodes through the real conversion code.

    FFmpeg formats are streamed to a WAV on disk by decode_to_wav (#6166); anything else goes
    through load_audio. Both are faked, and both count.
    """
    import soundfile as sf

    calls: list[str] = []

    def fake_load_audio(path, *_args, **_kwargs):
        calls.append(path)
        return FAKE_AUDIO, 44100

    def fake_decode_to_wav(path, temp_folder, cancel_event=None):
        calls.append(str(path))
        out = Path(temp_folder) / "decoded.wav"
        sf.write(str(out), FAKE_AUDIO, 44100, subtype="FLOAT")
        return out

    with patch("auralis.io.unified_loader.load_audio", side_effect=fake_load_audio), \
         patch("auralis.io.loaders.decode_to_wav", side_effect=fake_decode_to_wav):
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

        def slow_decode(path, temp_folder, cancel_event=None):
            import soundfile as sf

            calls.append(str(path))
            time.sleep(0.05)  # hold the build while the other listener arrives
            out = Path(temp_folder) / "decoded.wav"
            sf.write(str(out), FAKE_AUDIO, 44100, subtype="FLOAT")
            return out

        sources = [SeekableSource(track, registry) for _ in range(4)]
        results: list[str] = []
        with patch("auralis.io.loaders.decode_to_wav", side_effect=slow_decode):
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

        with patch("auralis.io.loaders.decode_to_wav", side_effect=RuntimeError("ffmpeg died")):
            with pytest.raises(RuntimeError):
                SeekableSource(track, registry).resolve()

        assert registry._conversions == {}

        import soundfile as sf

        def good_decode(path, temp_folder, cancel_event=None):
            out = Path(temp_folder) / "decoded.wav"
            sf.write(str(out), FAKE_AUDIO, 44100, subtype="FLOAT")
            return out

        with patch("auralis.io.loaders.decode_to_wav", side_effect=good_decode):
            source = SeekableSource(track, registry)
            assert Path(source.resolve()).exists()
            source.close()


class TestNormalStreamSharesTheRegistry:
    def test_normal_stream_holds_and_releases_through_the_registry(self):
        """SIBLING: stream_normal.py used its own per-stream convert_to_temp_wav."""
        import inspect

        from core import stream_normal

        source = inspect.getsource(stream_normal.stream_normal_audio)
        assert "acquire_conversion(" in source and "converted_wavs" in source
        assert "converted_wavs.release" in source
        assert "convert_to_temp_wav" not in source


class TestConversionIsBoundedByFreeSpace:
    """#6166: a conversion that cannot fit in the temp root is refused before any decode."""

    def test_a_file_that_cannot_fit_is_refused_without_decoding(self, tmp_path, decodes):
        from auralis.io.loaders import ffmpeg_space

        track = _unopenable(tmp_path)
        free = type("Usage", (), {"free": 1024 ** 3})()

        # decode_to_wav is faked by the fixture, so the guard under test is the one the real
        # decode_to_wav runs: here its probe and the disk are stood in for.
        with patch.object(ffmpeg_space.shutil, "disk_usage", return_value=free), \
             pytest.raises(OSError, match="Not enough free space"):
            ffmpeg_space.require_decode_space(str(tmp_path), 3600.0, 96000, 2)  # ~2.6 GiB as float32

        # and the libsndfile branch's guard shares it
        info = {"duration_seconds": 3600.0, "sample_rate": 96000, "channels": 2}
        with patch.object(seekable_source, "get_audio_info", return_value=info), \
             patch.object(ffmpeg_space.shutil, "disk_usage", return_value=free), \
             pytest.raises(OSError, match="Not enough free space"):
            seekable_source._require_free_space(track, str(tmp_path))
        assert decodes == [], "the decode ran although the file could not fit"

    def test_a_file_that_fits_is_converted_without_reading_it_into_memory(self, tmp_path, decodes):
        track = _unopenable(tmp_path)
        info = {"duration_seconds": 1.0, "sample_rate": 44100, "channels": 2}

        with patch.object(seekable_source, "get_audio_info", return_value=info), \
             patch("auralis.io.unified_loader.load_audio", side_effect=AssertionError("read the decode into memory")):
            temp_dir, wav_path = seekable_source.convert_to_temp_wav(track)

        try:
            assert Path(wav_path).name == "seekable.wav" and Path(wav_path).exists()
            assert decodes == [track]  # went through decode_to_wav (a path in, a path out), not load_audio
        finally:
            import shutil

            shutil.rmtree(temp_dir, ignore_errors=True)


def test_a_real_mp3_converts_to_the_same_samples_load_audio_would_produce(tmp_path):
    """No fakes: ffmpeg writes the seekable WAV (#6166) and its samples equal the in-memory decode's."""
    import shutil
    import subprocess

    import soundfile as sf

    if shutil.which("ffmpeg") is None or shutil.which("ffprobe") is None:
        pytest.skip("ffmpeg not installed")
    from auralis.io.unified_loader import load_audio

    tone = (0.3 * np.sin(2 * np.pi * 440 * np.arange(44100) / 44100)).astype(np.float32)
    src_wav = tmp_path / "src.wav"
    sf.write(str(src_wav), np.column_stack([tone, tone]), 44100)
    mp3 = tmp_path / "song.mp3"
    subprocess.run(["ffmpeg", "-nostdin", "-loglevel", "error", "-y", "-i", str(src_wav), str(mp3)], check=True)

    temp_dir, wav_path = seekable_source.convert_to_temp_wav(str(mp3))
    try:
        converted, rate = sf.read(wav_path, dtype="float32")
        expected, expected_rate = load_audio(str(mp3))
        assert rate == expected_rate
        np.testing.assert_array_equal(converted, expected)
        assert sf.info(wav_path).subtype == "FLOAT"
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)
