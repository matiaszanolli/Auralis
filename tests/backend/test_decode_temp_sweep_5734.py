"""A decode WAV left by a killed FFmpeg decode is reclaimed at startup (#5734).

The intermediate WAV was `mkstemp(prefix='auralis_')` in the system temp root, and the startup sweep
only globbed the stream and seekable prefixes, so a SIGKILL or OOM mid-decode left it for good (on a
tmpfs /tmp, as RAM). It now has its own prefix and the sweep takes the files that are old enough not to
be a live decode.
"""

import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "auralis-web" / "backend"))

from config.startup.decode_temps import reclaim_leftover_decode_wavs  # noqa: E402

from auralis.io.loaders.decode_temp import DECODE_TEMP_PREFIX  # noqa: E402
from auralis.io.loaders.ffmpeg_loader import _temp_wav_path  # noqa: E402


def _age(path: Path, hours: float) -> None:
    stamp = time.time() - hours * 3600
    os.utime(path, (stamp, stamp))


def test_the_decoder_names_its_temp_wav_with_the_sweepable_prefix(tmp_path):
    wav = _temp_wav_path(str(tmp_path))

    assert wav.name.startswith(DECODE_TEMP_PREFIX)
    assert wav.suffix == ".wav"
    wav.unlink()


def test_an_old_orphaned_decode_wav_is_removed_and_a_fresh_one_is_left(tmp_path):
    old = tmp_path / f"{DECODE_TEMP_PREFIX}abc.wav"
    fresh = tmp_path / f"{DECODE_TEMP_PREFIX}def.wav"
    unrelated = tmp_path / "auralis_other.wav"
    for path in (old, fresh, unrelated):
        path.write_bytes(b"RIFF")
    _age(old, 3)
    _age(unrelated, 3)

    reclaimed = reclaim_leftover_decode_wavs(tmp_path, max_age_hours=1.0)

    assert reclaimed == 1
    assert not old.exists()
    assert fresh.exists(), "a decode that may still be running must not be deleted"
    assert unrelated.exists(), "only the decode prefix is swept"
