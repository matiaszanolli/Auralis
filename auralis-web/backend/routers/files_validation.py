"""
Uploaded-file content sniffing (split from files.py, #5831).

:copyright: (C) 2024 Auralis Team
:license: AGPL-3.0-or-later (dual-licensed, see LICENSE / COMMERCIAL_LICENSE.md)
"""



# Magic byte signatures for supported audio formats (issue #2415).
# NOTE: every extension in formats.SUPPORTED_FORMATS must be recognised here or
# well-formed uploads are silently rejected (#4498). The prefix list covers the
# formats with a fixed leading signature; AIFF (FORM…AIFF/AIFC) and MP4/M4A/AAC
# (ftyp at offset 4) need the two-part checks in _has_valid_audio_magic().
# tests/backend/test_upload_magic_bytes.py::test_every_supported_format_is_recognised
# guards this against future drift.
_AUDIO_MAGIC: tuple[bytes, ...] = (
    b'\xff\xfb', b'\xff\xf3', b'\xff\xf2',  # MP3 (sync word variants)
    b'\xff\xf1', b'\xff\xf9',                # AAC (ADTS, MPEG-4 / MPEG-2)
    b'ID3',                                  # MP3 with ID3 tag
    b'RIFF',                                 # WAV
    b'fLaC',                                 # FLAC
    b'OggS',                                 # OGG/Vorbis/Opus
    b'.snd',                                 # AU (Sun/NeXT)
    # WMA / ASF — 16-byte ASF header-object GUID (#4498)
    b'\x30\x26\xb2\x75\x8e\x66\xcf\x11\xa6\xd9\x00\xaa\x00\x62\xce\x6c',
)


def _has_valid_audio_magic(data: bytes) -> bool:
    """Return True if the first bytes match a known audio container."""
    if len(data) < 8:
        return False
    # MP4/M4A/AAC: 4-byte box size then ASCII 'ftyp'
    if data[4:8] == b'ftyp':
        return True
    # AIFF/AIFC: 'FORM' then the form-type 'AIFF'/'AIFC' at offset 8 (#4498)
    if data[0:4] == b'FORM' and data[8:12] in (b'AIFF', b'AIFC'):
        return True
    return any(data.startswith(m) for m in _AUDIO_MAGIC)
