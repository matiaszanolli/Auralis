"""get_or_compute writes a .25d sidecar for FFmpeg-only containers too (#6330).

The sidecar metadata came from soundfile.info, which cannot open .m4a/.aac/.wma/.mp3, so the service logged
"Skipping .25d sidecar" and never cached those formats while the backend extractor did. The header is now read
with ffprobe for those extensions.
"""

from unittest.mock import MagicMock, patch

import pytest

from auralis.analysis.fingerprint.fingerprint_service import FingerprintService
from auralis.analysis.fingerprint.schema import DIMENSION_NAMES


def _service(tmp_path) -> FingerprintService:
    service = FingerprintService.__new__(FingerprintService)
    service._load_from_database = MagicMock(return_value=None)
    service._load_from_file_cache = MagicMock(return_value=None)
    service._save_to_database = MagicMock()
    service._compute_fingerprint = MagicMock(return_value={name: 0.5 for name in DIMENSION_NAMES})
    return service


@pytest.mark.parametrize("suffix", [".m4a", ".aac", ".wma", ".mp3"])
def test_ffmpeg_formats_get_a_sidecar_stamped_from_ffprobe(tmp_path, suffix):
    audio_path = tmp_path / f"song{suffix}"
    audio_path.write_bytes(b"x")
    service = _service(tmp_path)

    with patch("auralis.io.loaders.ffmpeg_probe._probe_audio", return_value={"duration": 187.5, "sample_rate": 44100}), \
            patch("auralis.analysis.fingerprint.fingerprint_service.FingerprintStorage") as storage:
        service.get_or_compute(audio_path)

    storage.save.assert_called_once()
    saved = storage.save.call_args.args[1]
    assert saved["_metadata"] == {"sample_rate": 44100, "duration": 187.5}


def test_an_unprobeable_ffmpeg_file_still_skips_the_sidecar_without_failing(tmp_path):
    audio_path = tmp_path / "song.m4a"
    audio_path.write_bytes(b"x")
    service = _service(tmp_path)

    with patch("auralis.io.loaders.ffmpeg_probe._probe_audio", return_value={"duration": None, "sample_rate": None}), \
            patch("auralis.analysis.fingerprint.fingerprint_service.FingerprintStorage") as storage:
        result = service.get_or_compute(audio_path)

    assert result is not None
    storage.save.assert_not_called()
