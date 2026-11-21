"""Chunk geometry follows the decoded length for header-less VBR / joined MP3s (#6448).

#6314 routes a file whose libsndfile length disagrees with ffprobe's through an FFmpeg temp WAV, so
the samples read are right. But ``load_audio_metadata`` still took ``total_duration`` (hence
``total_chunks``, ``audio_stream_start.total_duration`` and the seek clamp) from ffprobe, which is
exactly what is untrustworthy for these files: an over-estimate streamed tail chunks past real EOF
as silence and ended a late seek in an empty "completed" stream; an under-estimate never streamed
the real tail. A joined MP3 has the right libsndfile-vs-ffprobe disagreement; ffprobe's own
estimate for it is close, so the tests make it lie in each direction, as the audit measured.
"""
import shutil
import subprocess
import sys
from pathlib import Path
from unittest.mock import patch

import pytest
import soundfile as sf

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "auralis-web" / "backend"))

from core import chunk_metadata, converted_wav_registry, seekable_probe  # noqa: E402
from core.chunk_boundaries import chunk_for_position, content_chunk_count  # noqa: E402
from core.chunk_metadata import load_audio_metadata  # noqa: E402
from core.chunked_processor import ChunkedAudioProcessor  # noqa: E402
from core.seekable_source import SeekableSource  # noqa: E402

pytestmark = pytest.mark.skipif(
    shutil.which("ffmpeg") is None or shutil.which("ffprobe") is None,
    reason="needs ffmpeg/ffprobe to build MP3 fixtures",
)

SECONDS = 6  # one half of the joined file
DECODED = SECONDS * 2.0  # what FFmpeg decodes from the joined file


@pytest.fixture(autouse=True)
def _fresh_state():
    seekable_probe._ffprobe_duration.cache_clear()
    yield
    converted_wav_registry.converted_wavs.release_idle()


def _encode_mp3(path: Path) -> None:
    subprocess.run(
        ["ffmpeg", "-nostdin", "-loglevel", "error", "-f", "lavfi", "-i", f"sine=frequency=440:duration={SECONDS}",
         "-ac", "2", "-c:a", "libmp3lame", "-b:a", "128k", str(path)],
        check=True,
    )


@pytest.fixture
def healthy_mp3(tmp_path: Path) -> str:
    path = tmp_path / "healthy.mp3"
    _encode_mp3(path)
    return str(path)


@pytest.fixture
def joined_mp3(tmp_path: Path, healthy_mp3: str) -> str:
    """Two valid MP3s concatenated: libsndfile reads only the first one's length."""
    path = tmp_path / "joined.mp3"
    data = Path(healthy_mp3).read_bytes()
    path.write_bytes(data + data)
    return str(path)


def _ffprobe_says(seconds: float):
    """core.chunk_metadata's view of the file, with the container duration replaced."""
    real = chunk_metadata.get_audio_info

    def _info(path: str):
        return {**real(path), "duration_seconds": seconds}

    return patch.object(chunk_metadata, "get_audio_info", side_effect=_info)


def test_the_fixture_really_disagrees_with_libsndfile(joined_mp3):
    assert sf.info(joined_mp3).duration < SECONDS * 1.5  # guards the guard


@pytest.mark.parametrize("lie", [DECODED + 18.0, DECODED - 3.0], ids=["over-estimate", "under-estimate"])
def test_metadata_is_sized_from_the_decoded_wav_not_the_container_estimate(joined_mp3, lie):
    with _ffprobe_says(lie), SeekableSource(joined_mp3) as source:
        meta = load_audio_metadata(joined_mp3, source)
        decoded = sf.info(source.resolve()).duration

    assert meta.total_duration == pytest.approx(decoded)
    assert meta.total_duration == pytest.approx(DECODED, abs=0.2)
    assert meta.total_chunks == content_chunk_count(decoded)
    assert meta.total_duration != pytest.approx(lie, abs=1.0)


def test_without_a_source_the_probe_stays_decode_free(joined_mp3):
    with _ffprobe_says(30.0):
        meta = load_audio_metadata(joined_mp3)

    assert meta.total_duration == 30.0


def test_a_healthy_mp3_is_not_converted_to_size_it(healthy_mp3):
    with SeekableSource(healthy_mp3) as source:
        meta = load_audio_metadata(healthy_mp3, source)

        assert source.converted is False
    assert meta.total_duration == pytest.approx(SECONDS, abs=0.2)


def test_a_conversion_failure_keeps_the_probed_length(joined_mp3):
    with _ffprobe_says(30.0), SeekableSource(joined_mp3) as source, \
            patch.object(source, "resolve", side_effect=RuntimeError("ffmpeg missing")):
        meta = load_audio_metadata(joined_mp3, source)

    assert meta.total_duration == 30.0


@pytest.fixture(params=[DECODED + 18.0, DECODED - 3.0], ids=["over-estimate", "under-estimate"])
def processor_with_a_lying_probe(request, joined_mp3):
    with _ffprobe_says(request.param):
        processor = ChunkedAudioProcessor(track_id=1, filepath=joined_mp3, preset=None, intensity=1.0, chunk_cache={})
    yield processor
    processor.close()


def test_every_decoded_sample_is_streamed_and_nothing_else(processor_with_a_lying_probe):
    processor = processor_with_a_lying_probe
    decoded_frames = sf.info(processor._source.resolve()).frames

    emitted = [processor.process_chunk(i)[1].shape[0] for i in range(processor.total_chunks)]

    assert processor.total_duration == pytest.approx(DECODED, abs=0.2)
    assert all(n > 0 for n in emitted), f"a chunk past the real end emitted nothing: {emitted}"
    assert abs(sum(emitted) - decoded_frames) <= 2


def test_a_seek_into_the_final_seconds_delivers_audio(processor_with_a_lying_probe):
    processor = processor_with_a_lying_probe
    position = processor.total_duration - 1.0

    index, _offset, _effective = chunk_for_position(
        position, processor.total_chunks, total_duration=processor.total_duration
    )
    _path, audio = processor.process_chunk(index)

    assert index < processor.total_chunks
    assert audio.shape[0] > 0
