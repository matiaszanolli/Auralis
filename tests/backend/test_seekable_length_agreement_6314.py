"""libsndfile opening an MP3 is not libsndfile reading all of it (#6314).

`can_seek_natively` used to ask only "does `sf.SoundFile` open this?". For an MP3
without a usable Xing header (header-less VBR, files joined with `cat`) it does
open — and then sizes the file from the first frame and stops there, while FFmpeg
decodes the whole file. The enhanced stream read such files in place and served
silence for everything past libsndfile's length. For the FFmpeg formats the
decision now also requires libsndfile's length to match ffprobe's.
"""

import shutil
import subprocess
import sys
from pathlib import Path
from unittest.mock import patch

import pytest
import soundfile as sf

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "auralis-web" / "backend"))

from core import seekable_source  # noqa: E402
from core.seekable_source import SeekableSource, can_seek_natively  # noqa: E402

pytestmark = pytest.mark.skipif(
    shutil.which("ffmpeg") is None or shutil.which("ffprobe") is None,
    reason="needs ffmpeg/ffprobe to build MP3 fixtures",
)

SECONDS = 6


@pytest.fixture(autouse=True)
def _fresh_state():
    seekable_source._ffprobe_duration.cache_clear()
    yield
    seekable_source.converted_wavs.release_idle()


def _encode_mp3(path: Path) -> None:
    subprocess.run(
        ["ffmpeg", "-nostdin", "-loglevel", "error", "-f", "lavfi",
         "-i", f"sine=frequency=440:duration={SECONDS}", "-ac", "2",
         "-c:a", "libmp3lame", "-b:a", "128k", str(path)],
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


def test_the_fixture_really_reproduces_the_libsndfile_shortfall(joined_mp3):
    """Guards the guard: if libsndfile ever reads this fully, the tests below prove nothing."""
    assert sf.info(joined_mp3).duration < SECONDS * 1.5


def test_a_healthy_mp3_is_still_read_in_place(healthy_mp3):
    assert can_seek_natively(healthy_mp3) is True
    source = SeekableSource(healthy_mp3)
    assert source.resolve() == healthy_mp3
    assert source.converted is False


def test_a_joined_mp3_is_not_read_in_place(joined_mp3):
    assert can_seek_natively(joined_mp3) is False


def test_a_joined_mp3_resolves_to_a_wav_that_carries_the_whole_file(joined_mp3):
    with SeekableSource(joined_mp3) as source:
        resolved = source.resolve()
        assert source.converted is True
        assert resolved != joined_mp3
        assert sf.info(resolved).duration == pytest.approx(SECONDS * 2, abs=0.2)


def test_a_wav_never_asks_ffprobe(tmp_path):
    """libsndfile is the reference decoder for native formats: no probe, no cost."""
    wav = tmp_path / "tone.wav"
    sf.write(str(wav), [[0.0, 0.0]] * 4410, 44100)
    with patch.object(seekable_source, "get_audio_info", side_effect=AssertionError("probed")):
        assert can_seek_natively(str(wav)) is True


def test_an_ffprobe_failure_keeps_the_in_place_read(healthy_mp3):
    """With nothing to compare against, behaviour is what it was before the check."""
    with patch.object(seekable_source, "get_audio_info", return_value={"error": "boom"}):
        assert can_seek_natively(healthy_mp3) is True


def test_the_probe_runs_once_per_file_content(joined_mp3):
    with patch.object(
        seekable_source, "get_audio_info", return_value={"duration_seconds": SECONDS * 2.0}
    ) as probe:
        for _ in range(3):
            can_seek_natively(joined_mp3)
    assert probe.call_count == 1


def test_a_failed_probe_is_retried_not_cached(healthy_mp3):
    with patch.object(seekable_source, "get_audio_info", return_value={"error": "transient"}) as probe:
        can_seek_natively(healthy_mp3)
        can_seek_natively(healthy_mp3)
    assert probe.call_count == 2
