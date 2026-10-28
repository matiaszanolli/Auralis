"""Route handlers validate DB-sourced paths off the event loop (#5972).

validate_file_path() resolves the path, scans every allowed directory (each registered scan
folder included) and stats the file. Called directly in an `async def` it ran all of that on the
loop thread -- up to 1000 times in one uninterrupted loop for batch metadata updates.
"""

import ast
import asyncio
import sys
import threading
from pathlib import Path
from unittest.mock import patch

import pytest

_BACKEND = Path(__file__).resolve().parents[2] / "auralis-web" / "backend"
sys.path.insert(0, str(_BACKEND))

from routers import metadata_deps  # noqa: E402


def _direct_calls_in_async_defs(path: Path) -> list[int]:
    """Lines where `validate_file_path(...)` is called directly inside an async function."""
    tree = ast.parse(path.read_text())
    lines = []
    for func in ast.walk(tree):
        if not isinstance(func, ast.AsyncFunctionDef):
            continue
        for node in ast.walk(func):
            if (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Name)
                and node.func.id == "validate_file_path"
            ):
                lines.append(node.lineno)
    return lines


@pytest.mark.parametrize("path", sorted((_BACKEND / "routers").glob("*.py")), ids=lambda p: p.name)
def test_no_router_calls_validate_file_path_directly_in_a_coroutine(path):
    assert _direct_calls_in_async_defs(path) == []


@pytest.mark.asyncio
async def test_the_single_track_validation_runs_on_a_worker_thread():
    seen: list[threading.Thread] = []

    def fake_validate(filepath):
        seen.append(threading.current_thread())
        return Path(filepath)

    with patch.object(metadata_deps, "validate_file_path", fake_validate):
        result = await metadata_deps._validate_track_filepath(1, "/music/a.flac")

    assert result == "/music/a.flac"
    assert seen and seen[0] is not threading.main_thread()
    assert asyncio.get_running_loop() is not None
