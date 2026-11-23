"""An FFmpeg decode is bounded by policy, not by the file's declared duration (#6511).

The duration cap, the decoded-size cap and the free-space check were all computed from ffprobe's
declared duration, and the decode ran unbounded: a file whose header under-reported its real length
wrote gigabytes of WAV before anything noticed. The decode now runs with -t (a margin over the
declared length, never past MAX_DURATION_SECONDS) and -fs (the decoded-size cap), and a result that
ran into either is removed and rejected. The lying header is simulated by patching the probe.
"""

import shutil
import subprocess
from pathlib import Path

import pytest

from auralis.io.loaders import ffmpeg_loader
from auralis.io.loaders.ffmpeg_command import build_ffmpeg_cmd
from auralis.io.loaders.ffmpeg_decode_bounds import decode_cap_seconds
from auralis.io.loaders.ffmpeg_stream_decode import decode_to_wav
from auralis.utils.logging import ModuleError

pytestmark = pytest.mark.skipif(shutil.which("ffmpeg") is None, reason="needs ffmpeg")


@pytest.fixture
def ogg_60s(tmp_path):
    path = tmp_path / "real-60s.ogg"
    subprocess.run(
        ["ffmpeg", "-nostdin", "-loglevel", "error", "-f", "lavfi", "-i", "sine=frequency=440:duration=60",
         "-ar", "8000", "-c:a", "libvorbis", str(path)],
        check=True,
    )
    return path


def _decoded_wavs(folder: Path) -> list[Path]:
    return [p for p in folder.iterdir() if p.suffix == ".wav"]


def test_a_header_declaring_far_less_than_the_stream_is_refused_and_cleaned_up(ogg_60s, tmp_path, monkeypatch):
    real_probe = ffmpeg_loader._probe_or_fail
    monkeypatch.setattr(ffmpeg_loader, "_probe_or_fail", lambda p: (0.5, *real_probe(p)[1:]))  # "0.5 s": cap 30.6 s
    work = tmp_path / "work"
    work.mkdir()

    with pytest.raises(ModuleError, match="runs past"):
        decode_to_wav(ogg_60s, str(work))

    assert _decoded_wavs(work) == []


def test_an_honest_file_decodes_whole(ogg_60s, tmp_path):
    work = tmp_path / "work"
    work.mkdir()

    wav = decode_to_wav(ogg_60s, str(work))

    import soundfile as sf
    assert abs(sf.info(str(wav)).duration - 60.0) < 0.2


def test_the_argv_carries_both_bounds():
    cap = decode_cap_seconds(100.0, None)
    argv = build_ffmpeg_cmd("in.ogg", Path("out.wav"), 44100, 2, None, cap, ["-fs", "123"])

    assert argv[argv.index("-t") + 1] == f"{cap:.6f}" and cap == pytest.approx(155.0)
    assert argv[argv.index("-fs") + 1] == "123"
    assert decode_cap_seconds(None, None) == decode_cap_seconds(10**9, None)  # unknown length: the policy cap
    assert decode_cap_seconds(100.0, 7.5) == 7.5  # a windowed decode keeps its window
