"""
Regression guard for stream-coroutine closure binding (#3829).

The three inner stream coroutines in routers/system.py are defined inside the
WS receive loop and used to close over the loop locals (`track_id`, `preset`,
`intensity`, `force`, `start_position`/`position`, `enhancement_enabled`,
`ws_id`) by reference. A later message reassigning those names could leak into
an in-flight task's except/finally path and misattribute an error to the wrong
track. The fix snapshots each captured local as a default argument so each task
instance owns immutable copies.

These coroutines are deeply-nested closures with no import seam and the race is
impractical to drive deterministically, so this is a structural test: it parses
system.py and asserts each coroutine declares the captured names as
default-bound parameters. It fails if anyone reverts to a bare closure.
"""

import ast
from pathlib import Path

SYSTEM_PY = (
    Path(__file__).parent.parent.parent
    / "auralis-web"
    / "backend"
    / "routers"
    / "system.py"
)


def _defaulted_params(coroutine_name: str) -> set[str]:
    """Return the set of parameter names that carry a default value for the
    named async coroutine in system.py."""
    tree = ast.parse(SYSTEM_PY.read_text())
    for node in ast.walk(tree):
        if isinstance(node, ast.AsyncFunctionDef) and node.name == coroutine_name:
            args = node.args
            positional = args.posonlyargs + args.args
            num_defaults = len(args.defaults)
            # Defaults bind to the trailing N positional params.
            defaulted = {a.arg for a in positional[len(positional) - num_defaults:]} if num_defaults else set()
            # kwonly args with non-None defaults also count.
            for a, d in zip(args.kwonlyargs, args.kw_defaults):
                if d is not None:
                    defaulted.add(a.arg)
            return defaulted
    raise AssertionError(f"coroutine {coroutine_name!r} not found in system.py")


def test_stream_audio_snapshots_loop_locals():
    defaulted = _defaulted_params("stream_audio")
    for name in ("track_id", "preset", "intensity", "force", "start_position", "ws_id"):
        assert name in defaulted, (
            f"stream_audio must bind '{name}' as a default arg to avoid the "
            f"closure-reassignment leak (#3829); got {sorted(defaulted)}"
        )


def test_stream_normal_snapshots_loop_locals():
    defaulted = _defaulted_params("stream_normal")
    for name in ("track_id", "start_position", "ws_id"):
        assert name in defaulted, (
            f"stream_normal must bind '{name}' as a default arg (#3829); "
            f"got {sorted(defaulted)}"
        )


def test_stream_from_position_snapshots_loop_locals():
    defaulted = _defaulted_params("stream_from_position")
    for name in (
        "track_id",
        "preset",
        "intensity",
        "position",
        "enhancement_enabled",
        "ws_id",
    ):
        assert name in defaulted, (
            f"stream_from_position must bind '{name}' as a default arg (#3829); "
            f"got {sorted(defaulted)}"
        )
