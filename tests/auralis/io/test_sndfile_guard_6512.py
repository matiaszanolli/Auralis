"""Only the containers Auralis uses reach the bundled libsndfile (#6512).

soundfile 0.14.0 bundles libsndfile 1.2.2, with memory-safety CVEs in readers Auralis never needs
(IRCAM headers, IMA-ADPCM WAV). libsndfile picks its reader by content, and format= is ignored for
reads, so a hostile file named .wav reached them in-process. The guard wraps SoundFile's read-mode
open (sf.info/sf.read/sf.blocks go through it) and checks the header first.
"""

import io

import numpy as np
import pytest
import soundfile as sf

import auralis  # noqa: F401  (importing the package installs the guard)
from auralis.io.sndfile_guard import UnsupportedAudioContainer, refusal_reason


@pytest.mark.parametrize("fmt, ext", [("WAV", "wav"), ("FLAC", "flac"), ("AIFF", "aiff"), ("AU", "au"), ("RF64", "wav")])
def test_the_formats_auralis_reads_still_load(tmp_path, fmt, ext):
    path = tmp_path / f"a.{ext}"
    audio = np.linspace(-0.5, 0.5, 400, dtype="float32").reshape(200, 2)
    sf.write(str(path), audio, 44100, format=fmt, subtype="FLOAT" if fmt in ("WAV", "RF64", "AIFF", "AU") else None)

    assert sf.info(str(path)).frames == 200
    read, rate = sf.read(str(path), dtype="float32")
    assert rate == 44100 and read.shape == (200, 2)


def test_a_foreign_container_named_wav_is_refused_before_libsndfile_parses_it(tmp_path):
    path = tmp_path / "hostile.wav"
    sf.write(str(path), np.zeros((100, 1)), 8000, format="IRCAM")

    with pytest.raises(UnsupportedAudioContainer, match="not an audio container") as raised:
        sf.info(str(path))
    assert isinstance(raised.value, sf.LibsndfileError)  # existing libsndfile handlers catch it
    with pytest.raises(UnsupportedAudioContainer):
        sf.read(str(path))


def test_ima_adpcm_wav_is_refused(tmp_path):
    path = tmp_path / "adpcm.wav"
    sf.write(str(path), np.zeros((1000, 1)), 8000, format="WAV", subtype="IMA_ADPCM")

    with pytest.raises(UnsupportedAudioContainer, match="IMA-ADPCM"):
        with sf.SoundFile(str(path)):
            pass


def test_a_file_object_is_checked_and_its_position_kept(tmp_path):
    buffer = io.BytesIO()
    sf.write(buffer, np.zeros((50, 2)), 22050, format="WAV")
    buffer.seek(0)
    assert sf.info(buffer).frames == 50

    hostile = io.BytesIO()
    sf.write(hostile, np.zeros((50, 1)), 8000, format="IRCAM")
    hostile.seek(0)
    with pytest.raises(UnsupportedAudioContainer):
        sf.SoundFile(hostile)
    assert hostile.tell() == 0


def test_writing_is_not_checked(tmp_path):
    path = tmp_path / "out.wav"
    with sf.SoundFile(str(path), mode="w", samplerate=8000, channels=1, format="WAV") as out:
        out.write(np.zeros(10))
    assert sf.info(str(path)).frames == 10


@pytest.mark.parametrize("head", [b"OggS\x00\x02", b"ID3\x04\x00", bytes([0xFF, 0xFB, 0x90, 0x00])], ids=["ogg", "mp3-id3", "mp3-frame"])
def test_ogg_and_mpeg_headers_stay_allowed(head):
    assert refusal_reason(head + bytes(32)) is None
