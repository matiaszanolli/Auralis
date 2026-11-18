"""
A corrupt chunk-cache owner marker cannot stop startup (#6432)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

``claim_chunk_cache`` read the marker with ``read_text()`` inside ``except OSError``, so
non-UTF-8 bytes raised ``UnicodeDecodeError`` out of ``_cleanup_temp_directories`` and the
lifespan (which awaited it bare) aborted with "Application startup failed". The marker was
only rewritten after the read, so it never healed - and its name in the shared temp root is
predictable, so another local account could plant it.
"""

import sys
from pathlib import Path
from unittest.mock import patch

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "auralis-web" / "backend"))

from config.limits import CHUNK_TEMP_DIRNAME, CHUNK_TEMP_OWNER_FILENAME  # noqa: E402
from config.startup import create_lifespan  # noqa: E402
from config.startup.tempfiles import claim_chunk_cache  # noqa: E402

import os  # noqa: E402

CORRUPT = b"\xff\xfe\x80"


class FakeApp:
    """Unused by the startup phase under test."""


def _deps():
    return {
        'HAS_AURALIS': False,
        'HAS_PROCESSING': False,
        'HAS_STREAMLINED_CACHE': False,
        'HAS_SIMILARITY': False,
        'manager': None,
        'globals': {},
    }


def test_non_utf8_marker_is_overwritten_and_the_wipe_proceeds(tmp_path):
    marker = tmp_path / CHUNK_TEMP_OWNER_FILENAME
    marker.write_bytes(CORRUPT)

    assert claim_chunk_cache(tmp_path / CHUNK_TEMP_DIRNAME, marker) is True
    assert marker.read_text() == str(os.getpid())


@pytest.mark.asyncio
async def test_lifespan_starts_with_a_corrupt_marker(tmp_path):
    marker = tmp_path / CHUNK_TEMP_OWNER_FILENAME
    marker.write_bytes(CORRUPT)
    started = False

    with (
        patch("tempfile.gettempdir", return_value=str(tmp_path)),
        patch("config.startup.tempfiles.reclaim_leftover_stream_temps"),
    ):
        async with create_lifespan(_deps())(FakeApp()):
            started = True

    assert started
    assert marker.read_text() == str(os.getpid())


@pytest.mark.asyncio
async def test_lifespan_logs_and_continues_when_temp_cleanup_raises(caplog):
    started = False

    with patch("config.startup._cleanup_temp_directories", side_effect=ValueError("boom")):
        with caplog.at_level("WARNING", logger="config.startup"):
            async with create_lifespan(_deps())(FakeApp()):
                started = True

    assert started
    assert any("Temp directory cleanup failed: ValueError" in r.getMessage() for r in caplog.records)
