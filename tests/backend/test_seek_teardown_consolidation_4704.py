"""
handle_seek clears the same registries as _cancel_prior_task (#4704).
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

``_cancel_prior_task`` pops ``active_tasks``, ``active_track_ids``,
``pause_events`` **and** ``flow_events`` under the lock before cancelling.
``handle_seek`` open-coded the same sequence but popped only ``active_tasks``,
leaving the other three pointing at the superseded stream's objects for the
whole cancel-and-await window.

Nothing broke, because seek re-registers all three a few lines later. The hazard
is a divergent copy of a lock-ordered teardown — the shape that produced #3828 /
#3522 / #4364. #4364 brought ``handle_stop`` into line; seek was the last
mid-stream outlier.

:copyright: (C) 2024 Auralis Team
:license: GPLv3, see LICENSE for more details.
"""

import ast
import inspect
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "auralis-web" / "backend"))

from ws_handlers import playback_commands  # noqa: E402

_HANDLERS = Path(__file__).parent.parent.parent / "auralis-web" / "backend" / "ws_handlers"

_REGISTRIES = ("active_tasks", "active_track_ids", "pause_events", "flow_events")


def _func_source(module_path: Path, name: str) -> str:
    tree = ast.parse(module_path.read_text())
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == name:
            return ast.get_source_segment(module_path.read_text(), node) or ""
    raise AssertionError(f"{name} not found in {module_path.name}")


class TestSeekDelegatesToTheHelper:
    def test_handle_seek_calls_cancel_prior_task(self):
        src = _func_source(_HANDLERS / "playback_commands.py", "handle_seek")
        assert "_cancel_prior_task(" in src, (
            "handle_seek no longer routes its teardown through the shared "
            "helper — the divergent copy is back"
        )

    def test_handle_seek_does_not_open_code_the_teardown(self):
        src = _func_source(_HANDLERS / "playback_commands.py", "handle_seek")
        # `active_tasks[ws_id] = task` (re-registration) is expected; a `.pop`
        # on the registries is the open-coded teardown this issue removed.
        offenders = [r for r in _REGISTRIES if f"{r}.pop(" in src]
        assert not offenders, (
            f"handle_seek pops {offenders} inline instead of delegating"
        )


class TestHelperClearsEveryRegistry:
    def test_cancel_prior_task_pops_all_four(self):
        src = inspect.getsource(playback_commands._cancel_prior_task)
        for registry in _REGISTRIES:
            assert f"{registry}.pop(" in src, (
                f"_cancel_prior_task no longer clears {registry} — seek and "
                f"play now inherit the superseded stream's objects"
            )

    def test_cancel_prior_task_leaves_stream_settings_alone(self):
        """#4742: seek reads that snapshot to inherit preset/intensity.

        Clearing it here would make a seek lose the running stream's settings —
        only handle_stop clears it, because a stop ends the stream outright.
        """
        src = inspect.getsource(playback_commands._cancel_prior_task)
        assert "active_stream_settings" not in src


class TestLockOrderingPreserved:
    """#3828: pop under the lock, cancel and await OUTSIDE it.

    Awaiting under `active_tasks_lock` is the original deadlock: stream_audio's
    finally block acquires the same lock for its own cleanup, which can never
    succeed while the awaiting task holds it.
    """

    def test_no_await_of_the_old_task_inside_the_lock(self):
        src = inspect.getsource(playback_commands._cancel_prior_task)
        tree = ast.parse(src.strip())

        offenders: list[int] = []
        for node in ast.walk(tree):
            if not isinstance(node, ast.AsyncWith):
                continue
            item_src = ast.dump(node.items[0])
            if "active_tasks_lock" not in item_src:
                continue
            for inner in ast.walk(node):
                if isinstance(inner, ast.Await):
                    offenders.append(inner.lineno)

        assert not offenders, (
            f"await found inside the active_tasks_lock block at line(s) "
            f"{offenders} — this reintroduces #3828's deadlock"
        )

    def test_the_cancel_happens_after_the_lock_block(self):
        src = inspect.getsource(playback_commands._cancel_prior_task)
        lock_line = next(
            i for i, l in enumerate(src.splitlines()) if "active_tasks_lock" in l
        )
        cancel_line = next(
            i for i, l in enumerate(src.splitlines()) if ".cancel()" in l
        )
        assert cancel_line > lock_line


class TestTeardownIsNoLongerDuplicatedMidStream:
    """CONSISTENCY: the mid-stream teardown should have one expression."""

    def test_only_the_helper_expresses_it_in_playback_commands(self):
        source = (_HANDLERS / "playback_commands.py").read_text()
        tree = ast.parse(source)
        popping_funcs = set()
        for node in ast.walk(tree):
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            seg = ast.get_source_segment(source, node) or ""
            if any(f"{r}.pop(" in seg for r in _REGISTRIES[1:]):
                popping_funcs.add(node.name)
        assert popping_funcs == {"_cancel_prior_task"}, (
            f"the mid-stream teardown is expressed in {sorted(popping_funcs)}; "
            "it should live only in _cancel_prior_task"
        )

    @pytest.mark.parametrize(
        "module,func",
        [("playback_control.py", "handle_stop"), ("connection.py", "teardown_connection")],
    )
    def test_documented_deviations_explain_themselves(self, module, func):
        """The two remaining copies must say why they are not the helper."""
        src = _func_source(_HANDLERS / module, func)
        assert "#4704" in src, (
            f"{func} duplicates the teardown without the #4704 note explaining "
            "why it is deliberately not routed through _cancel_prior_task"
        )
