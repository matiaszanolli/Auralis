"""
Audio Format Registry
~~~~~~~~~~~~~~~~~~~~~~

Single source of truth for the audio extensions Auralis can decode. The
scanner, the unified loader, the file-type checker, and the upload allowlist
all derive their extension sets from here so the lists never drift apart
again (#4109).

:copyright: (C) 2024 Auralis Team
:license: GPLv3, see LICENSE for more details.
"""

# Extensions decoded natively by libsndfile (the soundfile path).
SOUNDFILE_FORMATS = {
    '.wav': 'WAV',
    '.flac': 'FLAC',
    '.aiff': 'AIFF',
    '.aif': 'AIFF',
    '.au': 'AU',
}

# Extensions that require FFmpeg transcoding before decode.
FFMPEG_FORMAT_NAMES = {
    '.mp3': 'MP3',
    '.m4a': 'M4A',
    '.aac': 'AAC',
    '.ogg': 'OGG',
    '.wma': 'WMA',
    '.opus': 'OPUS',  # fixes #2529
}

# Extension -> human-readable name for everything load_audio() accepts.
SUPPORTED_FORMATS = {**SOUNDFILE_FORMATS, **FFMPEG_FORMAT_NAMES}

# Set of extensions routed through the FFmpeg loader.
FFMPEG_FORMATS = set(FFMPEG_FORMAT_NAMES)

# Every extension the library scanner should ingest == everything we can
# decode. Note this deliberately excludes .mp4/.m4p/.webm (video/DRM
# containers with no working audio decode path — see #4109).
AUDIO_EXTENSIONS = set(SUPPORTED_FORMATS)
