"""Route handlers validate DB-sourced paths off the event loop (#5972), and no coroutine touches the disk (#6494).

validate_file_path() resolves the path, scans every allowed directory (each registered scan
folder included) and stats the file. Called directly in an `async def` it ran all of that on the
loop thread -- up to 1000 times in one uninterrupted loop for batch metadata updates.

#5972 left the same blocking calls inline elsewhere: the artwork GET (once per album tile)
resolved, checked and stat'ed its file on the loop, as did the job download, job execution,
both upload routes and the startup temp sweep. Every backend coroutine is now scanned.
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


# Path methods that hit the disk (not str-shared names like replace), and the modules whose calls all do.
_BLOCKING_PATH_METHODS = {
    "resolve", "exists", "stat", "lstat", "is_file", "is_dir", "is_symlink", "mkdir", "unlink", "rmdir",
    "iterdir", "glob", "rglob", "read_bytes", "read_text", "write_bytes", "write_text", "touch",
    "rename", "samefile", "readlink", "chmod",
}
_BLOCKING_MODULES = {"os", "os.path", "shutil"}


def _own_nodes(func: ast.AsyncFunctionDef):
    """The coroutine's own nodes: a nested def or lambda is a callable handed to a thread, not loop code."""
    stack = list(ast.iter_child_nodes(func))
    while stack:
        node = stack.pop()
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda)):
            continue
        yield node
        stack.extend(ast.iter_child_nodes(node))


def _blocking_fs_calls_in_coroutines(path: Path) -> list[str]:
    found = []
    for func in ast.walk(ast.parse(path.read_text())):
        if not isinstance(func, ast.AsyncFunctionDef):
            continue
        for node in _own_nodes(func):
            if not (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)):
                continue  # to_thread(p.stat) passes an attribute: only a CALL runs on the loop
            if node.func.attr in _BLOCKING_PATH_METHODS or ast.unparse(node.func.value) in _BLOCKING_MODULES:
                found.append(f"{func.name}:{node.lineno} {ast.unparse(node)[:60]}")
    return found


_SCANNED = sorted(
    p for d in ("routers", "services", "core", "config") for p in (_BACKEND / d).rglob("*.py")
)


@pytest.mark.parametrize("path", _SCANNED, ids=lambda p: str(p.relative_to(_BACKEND)))
def test_no_backend_coroutine_calls_the_filesystem_on_the_loop(path):
    assert _blocking_fs_calls_in_coroutines(path) == []


def test_the_scan_sees_an_inline_call_and_not_an_offloaded_one(tmp_path):
    probe = tmp_path / "probe.py"
    probe.write_text(
        "async def bad(p):\n    return p.stat()\n"
        "async def good(p):\n    return await asyncio.to_thread(p.stat)\n"
        "async def nested(p):\n    def work():\n        return p.exists()\n    return await asyncio.to_thread(work)\n"
    )
    assert _blocking_fs_calls_in_coroutines(probe) == ["bad:2 p.stat()"]


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
