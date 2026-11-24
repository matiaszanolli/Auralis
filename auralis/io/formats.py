"""
Audio Format Registry
~~~~~~~~~~~~~~~~~~~~~~

Single source of truth for the audio extensions Auralis can decode. The
scanner, the unified loader, and
the upload allowlist all derive their extension sets from here so the lists
never drift apart again (#4109).

:copyright: (C) 2024 Auralis Team
:license: AGPL-3.0-or-later (dual-licensed, see LICENSE / COMMERCIAL_LICENSE.md)
"""

import os

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


# RIFF's size field is 32 bits; libsndfile does not promote a WAV past it to RF64 by itself, it
# writes 0xFFFFFFFF and the frames beyond 4 GiB become unreadable (#6357). 64 KiB of headroom
# covers the header and any metadata chunks.
_RIFF_DATA_LIMIT_BYTES = 0xFFFFFFFF - (1 << 16)
_SUBTYPE_BYTES = {"PCM_S8": 1, "PCM_U8": 1, "PCM_16": 2, "PCM_24": 3, "PCM_32": 4, "FLOAT": 4, "DOUBLE": 8}


def wav_container(format_name: str | None, frames: int, channels: int, subtype: str) -> str | None:
    """``format_name``, or ``RF64`` for a WAV whose data would pass RIFF's 4 GiB limit (#6357).

    An unknown subtype counts as 8 bytes a sample, so a guess errs toward RF64.
    """
    if format_name != "WAV":
        return format_name
    data_bytes = frames * channels * _SUBTYPE_BYTES.get(subtype.upper(), 8)
    return "RF64" if data_bytes > _RIFF_DATA_LIMIT_BYTES else format_name


def verify_written_frames(path: str | os.PathLike[str], expected: int) -> None:
    """Raise OSError unless the file at ``path`` reads back ``expected`` frames.

    libsndfile reports no error when a container cannot hold what was written; the read-back is
    the only way a writer learns its output is short (#6357).
    """
    import soundfile as sf  # lazy: the registry above is imported where soundfile is not needed

    written = sf.info(os.fspath(path)).frames
    if written != expected:
        raise OSError(f"{os.path.basename(os.fspath(path))} reads back {written} of {expected} frames written")


def soundfile_format_name(path: str | os.PathLike[str]) -> str | None:
    """libsndfile's format name for *path*'s extension, or None when it is not a native format.

    ``.aif`` is accepted everywhere Auralis reads audio but libsndfile only knows the name AIFF,
    so output paths go through this instead of upper-casing the suffix (#6319). A ``Path`` is
    accepted like a string: saver.save() callers pass both.
    """
    path = os.fspath(path)
    suffix = "." + path.rsplit(".", 1)[-1].lower() if "." in path else ""
    return SOUNDFILE_FORMATS.get(suffix)
