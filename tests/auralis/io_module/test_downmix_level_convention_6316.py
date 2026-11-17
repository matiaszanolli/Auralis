"""One downmix level convention for every container (#6316).

The native BS.775 downmix (FLAC/WAV/AIFF) rescaled its result to the input
peak whenever the matrix sum exceeded it; `ffmpeg -ac 2` (M4A/OGG) applies no
rescale. The same 5.1 mix therefore loaded up to ~4.5 dB quieter from FLAC
(Ancestral: -21.3 vs -16.8 dB RMS), and because loudness measurement and the
fingerprint windows downmix per buffer, a 5.1 track's measured level moved
with each window's centre/surround content.
"""

import shutil
import subprocess

import numpy as np
import pytest
import soundfile as sf

from auralis.io.processing import downmix_to_stereo
from auralis.io.saver import save

SR = 48000


def _music_like_51(seconds: float = 1.0) -> np.ndarray:
    """Correlated L/R/C so the matrix sum passes the input peak (and full scale)."""
    t = np.arange(int(SR * seconds)) / SR
    tone = np.sin(2 * np.pi * 220 * t).astype(np.float32)
    audio = np.zeros((len(t), 6), dtype=np.float32)
    audio[:, 0] = audio[:, 1] = 0.6 * tone
    audio[:, 2] = 0.6 * tone
    audio[:, 4] = audio[:, 5] = 0.3 * np.roll(tone, 37)
    return audio


def _rms_db(x: np.ndarray) -> float:
    return float(20 * np.log10(np.sqrt(np.mean(x.astype(np.float64) ** 2))))


@pytest.mark.skipif(shutil.which("ffmpeg") is None, reason="ffmpeg required")
def test_native_and_ffmpeg_downmix_load_the_same_mix_at_the_same_level(tmp_path):
    audio = _music_like_51()
    src, dst = tmp_path / "in51.wav", tmp_path / "out.wav"
    sf.write(str(src), audio, SR, subtype="FLOAT")
    subprocess.run(
        ["ffmpeg", "-y", "-v", "error", "-i", str(src), "-af", "channelmap=channel_layout=5.1",
         "-ac", "2", "-c:a", "pcm_f32le", str(dst)],
        check=True,
    )
    ffmpeg_out, _ = sf.read(str(dst), dtype="float32")
    native = downmix_to_stereo(audio)

    assert abs(_rms_db(native) - _rms_db(ffmpeg_out)) < 0.05
    np.testing.assert_allclose(native, ffmpeg_out, atol=1e-4)


def test_a_window_downmixes_to_the_same_samples_as_the_whole_buffer():
    """Per-window measurement sees the level the whole-file load does, whatever
    the window's channel balance (a centre-only passage was not rescaled while
    the full mix around it was)."""
    audio = _music_like_51()
    audio[:4800] = 0.0
    audio[:4800, 2] = 0.5  # a centre-only passage: its sum stays under its own peak
    whole = downmix_to_stereo(audio)
    np.testing.assert_allclose(downmix_to_stereo(audio[:4800]), whole[:4800], atol=1e-7)
    np.testing.assert_allclose(downmix_to_stereo(audio[4800:9600]), whole[4800:9600], atol=1e-7)


def test_float_output_keeps_a_sum_past_full_scale():
    out = downmix_to_stereo(_music_like_51())
    assert float(np.max(np.abs(out))) > 1.0  # 0.6 + 0.707*0.6 + 0.707*0.3 ~ 1.24


def test_integer_input_is_clamped_to_its_range_not_wrapped():
    audio = np.zeros((10, 6), dtype=np.int16)
    audio[:, 0] = audio[:, 2] = audio[:, 4] = 30000
    out = downmix_to_stereo(audio)
    assert out.dtype == np.int16
    assert int(out[0, 0]) == np.iinfo(np.int16).max
    assert int(out[0, 1]) == round(30000 / np.sqrt(2))


def test_saver_keeps_float_overs_and_clips_pcm(tmp_path):
    audio = np.full((100, 2), 1.25, dtype=np.float32)
    save(str(tmp_path / "f.wav"), audio, SR, subtype="FLOAT")
    save(str(tmp_path / "p.wav"), audio, SR, subtype="PCM_24")
    as_float, _ = sf.read(str(tmp_path / "f.wav"), dtype="float32")
    as_pcm, _ = sf.read(str(tmp_path / "p.wav"), dtype="float32")
    assert float(as_float.max()) == pytest.approx(1.25)
    assert float(as_pcm.max()) <= 1.0
