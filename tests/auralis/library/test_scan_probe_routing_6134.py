"""The scan probes FFmpeg-routed formats the way playback decodes them (#6134).

``sf.info`` was tried first for every extension, so an ``.opus`` file was stored
as format ``OGG`` and MP3 durations came from libsndfile while playback used FFmpeg.
"""

import shutil
import subprocess
from unittest.mock import patch

import pytest

from auralis.library.scanner.audio_analyzer import AudioAnalyzer

pytestmark = pytest.mark.skipif(
    shutil.which("ffmpeg") is None or shutil.which("ffprobe") is None,
    reason="ffmpeg/ffprobe not installed",
)


def _encode(path, codec_args):
    cmd = ["ffmpeg", "-nostdin", "-hide_banner", "-loglevel", "error", "-y",
           "-f", "lavfi", "-i", "sine=frequency=440:duration=1.5", *codec_args, str(path)]
    if subprocess.run(cmd, capture_output=True).returncode != 0:
        pytest.skip("this ffmpeg build cannot encode the format")


def test_opus_is_stored_as_opus_not_ogg(tmp_path):
    opus = tmp_path / "w.opus"
    _encode(opus, ["-c:a", "libopus"])

    info = AudioAnalyzer().extract_audio_info(str(opus))

    assert info is not None
    assert info.format == "OPUS"
    assert info.duration == pytest.approx(1.5, abs=0.1)


def test_mp3_duration_comes_from_ffprobe(tmp_path):
    mp3 = tmp_path / "w.mp3"
    _encode(mp3, ["-c:a", "libmp3lame"])

    with patch("auralis.library.scanner.audio_analyzer.sf.info") as sf_info:
        info = AudioAnalyzer().extract_audio_info(str(mp3))

    sf_info.assert_not_called()
    assert info is not None and info.format == "MP3"
    assert info.duration == pytest.approx(1.5, abs=0.1)


def test_wav_still_uses_libsndfile(tmp_path):
    wav = tmp_path / "w.wav"
    _encode(wav, ["-c:a", "pcm_s16le"])

    with patch("auralis.library.scanner.audio_analyzer._probe_audio") as probe:
        info = AudioAnalyzer().extract_audio_info(str(wav))

    probe.assert_not_called()
    assert info is not None and info.format == "WAV"


def test_ffprobe_without_a_duration_falls_back_to_libsndfile(tmp_path):
    mp3 = tmp_path / "w.mp3"
    _encode(mp3, ["-c:a", "libmp3lame"])
    empty = {"duration": None, "sample_rate": None, "channels": None}

    with patch("auralis.library.scanner.audio_analyzer._probe_audio", return_value=empty):
        info = AudioAnalyzer().extract_audio_info(str(mp3))

    assert info is not None
    assert info.duration == pytest.approx(1.5, abs=0.1)  # libsndfile decoded the MP3


def test_an_undecodable_file_is_a_failure_not_a_zero_duration_track(tmp_path):
    """#5567: when neither probe yields a duration or rate, the scan used to ingest the file anyway."""
    junk = tmp_path / "broken.flac"
    junk.write_bytes(b"this is not flac" * 64)

    assert AudioAnalyzer().extract_audio_info(str(junk)) is None
