"""#5555 — non-UTF-8 bytes in ffmpeg's stderr must not fail a decodable file.

FFmpeg echoes input metadata and the input filename into stderr. A bare
``text=True`` capture decodes it strictly, so an ID3v1 (Latin-1) tag or a
filename with a raw non-UTF-8 byte raised UnicodeDecodeError, surfaced as
"FFmpeg conversion error: 'utf-8' codec can't decode ...".
"""

import shutil
import struct
import subprocess
import sys
import wave
from pathlib import Path

import numpy as np
import pytest

from auralis.io.loaders import ffmpeg_loader
from auralis.io.loaders.ffmpeg_loader import SUBPROCESS_TEXT_KWARGS, _run_ffmpeg_cancellable
from auralis.io.unified_loader import load_audio

needs_ffmpeg = pytest.mark.skipif(
    shutil.which("ffmpeg") is None or shutil.which("ffprobe") is None, reason="ffmpeg not installed"
)

LATIN1_STDERR = b"title : Caf\xe9 Cr\xe8me\n"


def test_text_kwargs_decode_leniently() -> None:
    assert SUBPROCESS_TEXT_KWARGS['text'] is True
    assert SUBPROCESS_TEXT_KWARGS['errors'] == 'replace'
    out = subprocess.run(
        [sys.executable, "-c", "import sys; sys.stderr.buffer.write(b'title : Caf\\xe9')"],
        capture_output=True,
        **SUBPROCESS_TEXT_KWARGS,
    )
    assert out.returncode == 0
    assert out.stderr.startswith("title : Caf")


@pytest.mark.parametrize("cancellable", [False, True])
def test_run_ffmpeg_survives_non_utf8_stderr(cancellable: bool) -> None:
    import threading

    cmd = [sys.executable, "-c", f"import sys; sys.stderr.buffer.write({LATIN1_STDERR!r})"]
    event = threading.Event() if cancellable else None
    result = _run_ffmpeg_cancellable(cmd, timeout=30, cancel_event=event)
    assert result.returncode == 0
    assert "Caf" in result.stderr


def _make_mp3_with_latin1_id3v1(path: Path) -> int:
    """A short sine MP3 with a hand-built ID3v1 block holding Latin-1 bytes."""
    wav = path.with_suffix(".wav")
    sr = 44100
    t = np.arange(sr) / sr
    pcm = (0.3 * np.sin(2 * np.pi * 440 * t) * 32767).astype("<i2")
    with wave.open(str(wav), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(sr)
        w.writeframes(pcm.tobytes())
    subprocess.run(
        ["ffmpeg", "-v", "error", "-y", "-i", str(wav), "-id3v2_version", "0", "-write_id3v1", "0", str(path)],
        check=True,
    )
    tag = b"TAG" + b"Caf\xe9 Cr\xe8me".ljust(30, b"\0") + b"\xe9".ljust(30, b"\0") + b"\0" * 30 + b"2024" + b"\0" * 30 + b"\xff"
    assert len(tag) == 128
    with open(path, "ab") as f:
        f.write(tag)
    return sr


@needs_ffmpeg
def test_load_audio_with_latin1_id3v1_tag(tmp_path: Path) -> None:
    mp3 = tmp_path / "tagged.mp3"
    _make_mp3_with_latin1_id3v1(mp3)
    audio, sr = load_audio(str(mp3))
    assert sr > 0
    assert audio.shape[0] > 0 and np.all(np.isfinite(audio))


@needs_ffmpeg
def test_load_audio_with_non_utf8_filename(tmp_path: Path) -> None:
    src = tmp_path / "plain.mp3"
    _make_mp3_with_latin1_id3v1(src)
    raw = bytes(tmp_path) + b"/Caf\xe9.mp3"
    import os

    try:
        os.link(bytes(src), raw)
    except OSError:
        pytest.skip("filesystem rejects non-UTF-8 filenames")
    audio, _sr = load_audio(os.fsdecode(raw))
    assert audio.shape[0] > 0
