"""WAV output past RIFF's 4 GiB limit is written as RF64 and read back (#6357).

libsndfile does not promote a WAV to RF64 by itself: past 4 GiB it writes ``RIFF`` with size
0xFFFFFFFF and the frames beyond the 32-bit size are on disk but unreadable (a 540M-frame
PCM_32 write read back as 536,870,911 frames). ``wav_container`` picks RF64 from the planned
size and ``verify_written_frames`` makes a short read-back raise. Every libsndfile WAV writer
uses both: saver.save (also the backend's seekable temp WAV), the streamed-decode sanitiser,
and the offline render. The writer tests shrink the limit so a tiny file crosses it.
"""

import sys
from pathlib import Path
from unittest.mock import patch

import numpy as np
import pytest
import soundfile as sf

from auralis.io import formats
from auralis.io.formats import verify_written_frames, wav_container

SR = 44100
_SMALL_LIMIT = 1000  # bytes: a few hundred frames cross it


def _container_tag(path: Path) -> bytes:
    return path.read_bytes()[:4]


@pytest.mark.parametrize(("frames", "channels", "subtype", "expected"), [
    (536_870_911, 2, "PCM_32", "RF64"),  # the audit's 4.3 GB PCM_32 write
    (715_827_882, 2, "PCM_24", "RF64"),  # 4 GiB at 24-bit stereo, past the header headroom
    (700_000_000, 2, "PCM_24", "WAV"),  # 4.2 GB: still fits RIFF
    (1_000_000, 2, "FLOAT", "WAV"),
    (600_000_000, 1, "SOMETHING_NEW", "RF64"),  # unknown subtype: 8 bytes, errs toward RF64
])
def test_wav_container_picks_rf64_only_past_the_riff_limit(frames, channels, subtype, expected):
    assert wav_container("WAV", frames, channels, subtype) == expected


def test_other_containers_are_left_alone():
    assert wav_container("FLAC", 10**10, 2, "PCM_24") == "FLAC"
    assert wav_container(None, 10**10, 2, "PCM_24") is None


def test_a_short_read_back_raises(tmp_path):
    path = tmp_path / "short.wav"
    sf.write(str(path), np.zeros((100, 2), np.float32), SR, subtype="PCM_16")

    verify_written_frames(path, 100)
    with pytest.raises(OSError, match="reads back 100 of 101 frames"):
        verify_written_frames(path, 101)


def test_saver_writes_rf64_past_the_limit_and_reads_back_whole(tmp_path):
    from auralis.io.saver import save

    audio = (0.1 * np.random.default_rng(0).standard_normal((4000, 2))).astype(np.float32)
    path = tmp_path / "out.wav"
    with patch.object(formats, "_RIFF_DATA_LIMIT_BYTES", _SMALL_LIMIT):
        save(str(path), audio, SR, subtype="PCM_24")

    assert _container_tag(path) == b"RF64"
    assert sf.info(str(path)).frames == 4000


def test_saver_below_the_limit_still_writes_riff(tmp_path):
    from auralis.io.saver import save

    path = tmp_path / "out.wav"
    save(str(path), np.zeros((4000, 2), np.float32), SR, subtype="PCM_16")

    assert _container_tag(path) == b"RIFF"


def test_saver_raises_when_the_file_reads_back_short(tmp_path):
    from auralis.io.saver import save

    path = tmp_path / "out.wav"
    with (
        patch("auralis.io.saver.verify_written_frames", side_effect=OSError("reads back 1 of 2")),
        pytest.raises(RuntimeError, match="reads back 1 of 2"),
    ):
        save(str(path), np.zeros((2, 2), np.float32), SR, subtype="PCM_16")


def test_the_sanitiser_rewrites_a_large_decode_as_rf64(tmp_path):
    from auralis.io.wav_sanitize import sanitize_wav_in_place

    audio = np.full((4000, 2), 0.25, np.float32)
    audio[10, 0] = np.nan
    path = tmp_path / "decoded.wav"
    sf.write(str(path), audio, SR, format="WAV", subtype="FLOAT")

    with patch.object(formats, "_RIFF_DATA_LIMIT_BYTES", _SMALL_LIMIT):
        assert sanitize_wav_in_place(path, block_frames=1000) is True

    assert _container_tag(path) == b"RF64"
    assert sf.info(str(path)).frames == 4000


def test_the_offline_render_writes_rf64_past_the_limit(tmp_path):
    sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "auralis" / "core"))
    from test_ffmpeg_pretranscode_saver_5532 import _identity_process, _make_pipeline

    tone = (0.2 * np.sin(2 * np.pi * 220 * np.arange(3 * SR) / SR)).astype(np.float32)
    src = tmp_path / "in.wav"
    sf.write(str(src), np.column_stack([tone, tone]), SR, subtype="PCM_16")
    out = tmp_path / "out.wav"

    pipeline = _make_pipeline()
    with (
        patch.object(formats, "_RIFF_DATA_LIMIT_BYTES", _SMALL_LIMIT),
        patch.object(pipeline, "_process", side_effect=_identity_process),
    ):
        pipeline.master_file(str(src), str(out), verbose=False)

    assert _container_tag(out) == b"RF64"
    assert sf.info(str(out)).frames == 3 * SR


def test_the_backend_seekable_temp_wav_is_rf64_past_the_limit(tmp_path):
    """converted_wav_registry's libsndfile route writes through saver.save, so it carries the RF64
    choice and the read-back; it used a bare sf.write with format="WAV"."""
    import shutil

    sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "auralis-web" / "backend"))
    from core.converted_wav_registry import convert_to_temp_wav

    tone = (0.2 * np.sin(2 * np.pi * 220 * np.arange(SR) / SR)).astype(np.float32)
    src = tmp_path / "in.flac"
    sf.write(str(src), np.column_stack([tone, tone]), SR, subtype="PCM_16")

    with patch.object(formats, "_RIFF_DATA_LIMIT_BYTES", _SMALL_LIMIT):
        temp_dir, wav_path = convert_to_temp_wav(str(src))
    try:
        assert _container_tag(Path(wav_path)) == b"RF64"
        assert sf.info(wav_path).frames == SR
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)
