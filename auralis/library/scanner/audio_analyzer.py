"""
Audio Analyzer
~~~~~~~~~~~~~

Audio file analysis and information extraction

:copyright: (C) 2024 Auralis Team
:license: AGPL-3.0-or-later (dual-licensed, see LICENSE / COMMERCIAL_LICENSE.md)
"""

from datetime import datetime
from pathlib import Path

import soundfile as sf

from ...io.formats import FFMPEG_FORMATS, SUPPORTED_FORMATS
from ...io.loader import oversize_probe_detail
from ...io.loaders.ffmpeg_probe import _probe_audio
from ...utils.logging import debug, warning
from ..scan_models import AudioFileInfo


class AudioAnalyzer:
    """
    Analyzes audio files to extract technical information

    Extracts:
    - Duration
    - Sample rate
    - Channel count
    - Format
    - File size
    """

    def extract_audio_info(self, file_path: str) -> AudioFileInfo | None:
        """
        Extract comprehensive audio file information

        Args:
            file_path: Path to audio file

        Returns:
            AudioFileInfo object or None if extraction fails
        """
        try:
            path = Path(file_path)
            file_stat = path.stat()

            info_obj = AudioFileInfo(
                filepath=file_path,
                filename=path.name,
                filesize=file_stat.st_size,
                modified_time=datetime.fromtimestamp(file_stat.st_mtime)
            )

            # Probe the way playback decodes (#6134): FFmpeg-routed formats
            # (MP3/OGG/OPUS/M4A/...) through ffprobe, so the stored duration and
            # format match the decoder, not libsndfile's own idea of the file
            # (which names an .opus file "OGG" and measures a VBR MP3 differently).
            # libsndfile stays the probe for its own formats and the fallback
            # when ffprobe yields nothing.
            if path.suffix.lower() in FFMPEG_FORMATS and self._probe_with_ffprobe(path, info_obj):
                pass
            else:
                try:
                    sf_info = sf.info(file_path)
                    info_obj.duration = sf_info.duration
                    info_obj.sample_rate = sf_info.samplerate
                    info_obj.channels = sf_info.channels
                    info_obj.format = sf_info.format
                except Exception as e:
                    debug(f"SoundFile analysis failed for {file_path}: {e}")
                    self._probe_with_ffprobe(path, info_obj)

            # Neither probe produced a duration or a sample rate: the file is undecodable, and an
            # AudioFileInfo with those unset used to be ingested as a zero-duration track while
            # the scan reported no failure. None makes the batch processor record it (#5567).
            if not info_obj.duration or not info_obj.sample_rate:
                warning(f"Could not probe {path.name}; not adding it to the library")
                return None

            # The scan stores whatever the container claims, and every later
            # consumer (chunk counting, seek geometry, the UI's duration)
            # trusts it. Apply the decode budget here so a forged or corrupt
            # header is refused at scan time rather than at playback (#5312).
            detail = oversize_probe_detail(
                info_obj.duration, info_obj.sample_rate, info_obj.channels
            )
            if detail:
                warning(f"Refusing {path.name} at scan time: {detail}")
                return None

            return info_obj

        except Exception as e:
            debug(f"Failed to extract info from {file_path}: {e}")
            return None

    @staticmethod
    def _probe_with_ffprobe(path: Path, info_obj: AudioFileInfo) -> bool:
        """Fill *info_obj* from ffprobe; True if it reported a duration."""
        probe = _probe_audio(path)
        if probe['duration'] is not None:
            info_obj.duration = probe['duration']
        if probe['sample_rate'] is not None:
            info_obj.sample_rate = probe['sample_rate']
        if probe['channels'] is not None:
            info_obj.channels = probe['channels']
        info_obj.format = SUPPORTED_FORMATS.get(path.suffix.lower(), path.suffix.lstrip('.').upper())
        return probe['duration'] is not None
