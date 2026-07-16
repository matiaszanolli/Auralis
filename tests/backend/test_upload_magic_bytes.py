"""
Regression: upload magic-byte gate accepts every supported format (#4498)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

The magic-byte allowlist (_AUDIO_MAGIC / _has_valid_audio_magic) recognised no
signatures for AIFF / AU / WMA (and raw ADTS AAC), so well-formed uploads of
those formats — all advertised as decodable in formats.SUPPORTED_FORMATS and
accepted by the extension check — were rejected at the content gate.
"""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "auralis-web" / "backend"))

from routers.files import _has_valid_audio_magic
from auralis.io.formats import SUPPORTED_FORMATS

# A minimal valid leading header for one representative encoding per extension.
# Padded to >= 16 bytes so the 16-byte WMA GUID / AIFF offset-12 checks have data.
_PAD = b"\x00" * 16
_SAMPLE_HEADERS: dict[str, bytes] = {
    ".wav":  b"RIFF\x00\x00\x00\x00WAVE" + _PAD,
    ".flac": b"fLaC\x00\x00\x00\x00" + _PAD,
    ".aiff": b"FORM\x00\x00\x00\x00AIFF" + _PAD,
    ".aif":  b"FORM\x00\x00\x00\x00AIFC" + _PAD,   # AIFC variant
    ".au":   b".snd\x00\x00\x00\x18" + _PAD,
    ".mp3":  b"ID3\x04\x00\x00\x00\x00\x00\x00" + _PAD,
    ".m4a":  b"\x00\x00\x00\x20ftypM4A " + _PAD,
    ".aac":  b"\xff\xf1\x50\x80\x00\x1f\xfc" + _PAD,  # ADTS syncword
    ".ogg":  b"OggS\x00\x02\x00\x00" + _PAD,
    ".wma":  b"\x30\x26\xb2\x75\x8e\x66\xcf\x11\xa6\xd9\x00\xaa\x00\x62\xce\x6c" + _PAD,
    ".opus": b"OggS\x00\x02\x00\x00" + _PAD,   # Opus lives in an Ogg container
}


@pytest.mark.parametrize("ext,header", sorted(_SAMPLE_HEADERS.items()))
def test_representative_header_accepted(ext, header):
    assert _has_valid_audio_magic(header), (
        f"{ext} header rejected by the magic-byte gate (#4498)"
    )


def test_every_supported_format_is_recognised():
    """CONSISTENCY: every SUPPORTED_FORMATS extension must have a magic sample
    that the gate accepts, so the two lists cannot drift apart again."""
    missing = [ext for ext in SUPPORTED_FORMATS if ext not in _SAMPLE_HEADERS]
    assert not missing, (
        f"SUPPORTED_FORMATS gained {missing} with no magic coverage — add a "
        "signature to _AUDIO_MAGIC/_has_valid_audio_magic and a sample here"
    )
    for ext in SUPPORTED_FORMATS:
        assert _has_valid_audio_magic(_SAMPLE_HEADERS[ext]), (
            f"{ext} is in SUPPORTED_FORMATS but its content is rejected (#4498)"
        )


def test_garbage_still_rejected():
    """The gate must not turn into a pass-all — random bytes are rejected."""
    assert not _has_valid_audio_magic(b"not audio at all!!" + _PAD)
    assert not _has_valid_audio_magic(b"")
