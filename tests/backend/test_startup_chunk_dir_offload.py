"""
Regression: lifespan chunk-dir cleanup offloaded via asyncio.to_thread (#4754)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

create_lifespan's startup phase clears the whole chunk-cache directory (up to
512 MB of cached WAVs) via shutil.rmtree so stale chunks from a previous
process aren't served under old presets. That call used to run directly on
the event loop during lifespan startup; it must now be offloaded.

:copyright: (C) 2024 Auralis Team
:license: GPLv3
"""

import sys
from pathlib import Path
from unittest.mock import patch

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "auralis-web" / "backend"))

from config.limits import CHUNK_TEMP_DIRNAME  # noqa: E402
from config.startup import create_lifespan  # noqa: E402

pytestmark = pytest.mark.asyncio


def _minimal_deps():
    """HAS_AURALIS/HAS_PROCESSING/HAS_STREAMLINED_CACHE all False so the
    lifespan's startup phase does nothing beyond the chunk-dir cleanup and
    the (separately tested) leftover-stream-temp sweep before reaching
    `yield` — no library DB, processing engine, or cache worker needed."""
    return {
        'HAS_AURALIS': False,
        'HAS_PROCESSING': False,
        'HAS_STREAMLINED_CACHE': False,
        'HAS_SIMILARITY': False,
        'manager': None,
        'globals': {},
    }


class FakeApp:
    """Stand-in for the FastAPI app object the lifespan context manager
    receives — unused by the startup phase under test."""


async def test_chunk_dir_rmtree_offloaded_via_to_thread(tmp_path):
    chunk_dir = tmp_path / CHUNK_TEMP_DIRNAME
    chunk_dir.mkdir()
    (chunk_dir / "stale_chunk.wav").write_bytes(b"\x00")

    lifespan = create_lifespan(_minimal_deps())

    with (
        patch("tempfile.gettempdir", return_value=str(tmp_path)),
        patch("config.startup.reclaim_leftover_stream_temps"),  # unrelated sweep, quieted
        patch("shutil.rmtree") as mock_rmtree,
        patch("asyncio.to_thread", wraps=__import__("asyncio").to_thread) as mock_to_thread,
    ):
        async with lifespan(FakeApp()):
            pass

    assert mock_rmtree.called, "rmtree was never invoked — test didn't reach the cleanup"
    to_thread_calls_with_rmtree = [
        call for call in mock_to_thread.call_args_list if call.args and call.args[0] is mock_rmtree
    ]
    assert to_thread_calls_with_rmtree, (
        "chunk_dir shutil.rmtree must be offloaded via asyncio.to_thread, not "
        "called directly on the event loop during lifespan startup (#4754)"
    )


async def test_chunk_dir_recreated_after_clearing(tmp_path):
    """Behavior must be unchanged by the offload: the directory is cleared
    then immediately recreated so subsequent chunk writes still succeed."""
    chunk_dir = tmp_path / CHUNK_TEMP_DIRNAME
    chunk_dir.mkdir()
    (chunk_dir / "stale_chunk.wav").write_bytes(b"\x00")

    lifespan = create_lifespan(_minimal_deps())

    with (
        patch("tempfile.gettempdir", return_value=str(tmp_path)),
        patch("config.startup.reclaim_leftover_stream_temps"),
    ):
        async with lifespan(FakeApp()):
            pass

    assert chunk_dir.exists()
    assert list(chunk_dir.iterdir()) == []


async def test_skipped_entirely_when_chunk_dir_absent(tmp_path):
    """No chunk_dir on disk (fresh install / already-cleared) — must not
    attempt rmtree at all, and must not raise."""
    lifespan = create_lifespan(_minimal_deps())

    with (
        patch("tempfile.gettempdir", return_value=str(tmp_path)),
        patch("config.startup.reclaim_leftover_stream_temps"),
        patch("shutil.rmtree") as mock_rmtree,
    ):
        async with lifespan(FakeApp()):
            pass

    mock_rmtree.assert_not_called()
