"""
Compressed inputs are decoded to disk, not RAM (#5739)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

``master_file`` used to read the whole FFmpeg decode into one ndarray and re-save it, so a
multi-hour mp3 cost gigabytes. ``decode_to_wav`` leaves the decode on disk for the chunk loop;
``wav_sanitize`` keeps the finite/range guarantee the in-memory ``saver.save()`` gave (#5532).

:copyright: (C) 2024 Auralis Team
:license: AGPL-3.0-or-later (dual-licensed, see LICENSE / COMMERCIAL_LICENSE.md)
"""

import shutil
import subprocess
import tracemalloc

import numpy as np
import pytest
import soundfile as sf

from auralis.io.loaders import decode_to_wav, load_with_ffmpeg
from auralis.io.wav_sanitize import sanitize_wav_in_place

needs_ffmpeg = pytest.mark.skipif(
    shutil.which("ffmpeg") is None or shutil.which("ffprobe") is None, reason="ffmpeg not installed"
)
SR = 44100


def _make_mp3(path, seconds: float) -> None:
    t = np.arange(int(SR * seconds)) / SR
    tone = (0.3 * np.sin(2 * np.pi * 440 * t)).astype(np.float32)
    wav = path.with_suffix(".src.wav")
    sf.write(str(wav), np.column_stack([tone, tone]), SR)
    subprocess.run(["ffmpeg", "-nostdin", "-loglevel", "error", "-y", "-i", str(wav), str(path)], check=True)
    wav.unlink()


@needs_ffmpeg
def test_decode_to_wav_leaves_a_float32_wav_with_the_same_samples_as_the_in_memory_load(tmp_path):
    src = tmp_path / "song.mp3"
    _make_mp3(src, 3.0)

    wav = decode_to_wav(src, str(tmp_path))

    assert wav.exists() and wav.suffix == ".wav"
    assert sf.info(str(wav)).subtype == "FLOAT"
    streamed, sr = sf.read(str(wav), dtype="float32")
    in_memory, sr_mem = load_with_ffmpeg(src, str(tmp_path))
    assert sr == sr_mem == SR
    np.testing.assert_array_equal(streamed, in_memory)


@needs_ffmpeg
def test_decode_to_wav_does_not_hold_the_decode_in_memory(tmp_path):
    src = tmp_path / "long.mp3"
    _make_mp3(src, 60.0)  # 60 s stereo float32 is ~21 MB if it were loaded

    tracemalloc.start()
    try:
        wav = decode_to_wav(src, str(tmp_path))
        _, peak = tracemalloc.get_traced_memory()
    finally:
        tracemalloc.stop()

    assert sf.info(str(wav)).frames == pytest.approx(60 * SR, rel=0.02)
    assert peak < 4 * 1024 * 1024, f"decode_to_wav traced {peak / 1e6:.1f} MB of Python allocations"


@needs_ffmpeg
def test_a_failed_decode_leaves_no_file_behind(tmp_path):
    src = tmp_path / "broken.mp3"
    src.write_bytes(b"not an mp3 at all")
    out = tmp_path / "out"
    out.mkdir()

    with pytest.raises(Exception):
        decode_to_wav(src, str(out))

    assert list(out.iterdir()) == []


def test_sanitize_repairs_non_finite_and_out_of_range_samples_across_blocks(tmp_path):
    audio = np.full((5000, 2), 0.25, dtype=np.float32)
    audio[10, 0] = np.nan
    audio[3000, 1] = np.inf
    audio[4500, 0] = 7.5
    audio[4600, 1] = -7.5
    wav = tmp_path / "bad.wav"
    sf.write(str(wav), audio, SR, subtype="FLOAT")

    assert sanitize_wav_in_place(wav, block_frames=1000) is True

    fixed, _ = sf.read(str(wav), dtype="float32")
    assert fixed.shape == audio.shape
    assert fixed[10, 0] == 0.0 and fixed[3000, 1] == 0.0
    assert fixed[4500, 0] == 1.0 and fixed[4600, 1] == -1.0
    assert np.all(fixed[:10] == 0.25)  # untouched samples are bit-identical
    assert list(tmp_path.iterdir()) == [wav], "the .repaired sibling must not linger"


def test_sanitize_leaves_a_clean_file_untouched(tmp_path):
    wav = tmp_path / "clean.wav"
    sf.write(str(wav), np.full((3000, 2), 0.5, dtype=np.float32), SR, subtype="FLOAT")
    before = wav.stat().st_mtime_ns

    assert sanitize_wav_in_place(wav, block_frames=1000) is False
    assert wav.stat().st_mtime_ns == before
